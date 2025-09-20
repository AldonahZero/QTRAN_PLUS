# Redis 变异微调数据集设计与使用说明

## 1. 目标与背景
在将 SQL 查询转换迁移到 Redis 的过程中，出现了“语义丢失”问题：例如复杂的聚合 / 约束被简单替换为单个 HGET，导致后续 Oracle / 不变量无法判定。本数据集旨在通过**对 Redis 命令提供结构保持、可判定的变异模式**，让模型学会：
- 识别 key 对应的数据结构（string/hash/list/set/zset/ttl 元语义）；
- 生成包含 probe / inverse / idempotent / transform 等类型的高信号变异；
- 输出带 `category` 与 `oracle` 标签的 JSON，便于后续自动执行与差异判断；
- 降低“直接退化”一类的语义损失风险。

## 2. 数据来源
- 原始 Redis enriched examples 目录：`NoSQLFeatureKnowledgeBase/Redis/outputs/parsed_examples_enriched/`。
  每个命令文件（如 `HSET.json`）结构示例：
  ```json
  {
    "command": "HSET",
    "examples": [
      {"command": "HSET", "args": ["test", "key1", "val1"], "raw": "HSET test key1 val1", "expected_error": "redis client not available"}
    ]
  }
  ```
- 解析脚本：`src/MutationLlmModelFineTuning/build_redis_mutation_dataset.py`（自动生成训练 JSONL）。
- 输出文件：`MutationData/FineTuningTrainingData/redis_mutation.jsonl`。

## 3. 样本格式（OpenAI Fine-tune messages schema）
每行是一条 JSON，包含 messages 数组：
```json
{
  "messages": [
    {"role": "system", "content": "You are a Redis mutation synthesis assistant..."},
    {"role": "user", "content": "Original: HSET test key1 val1\nMeta: command=HSET group=hash args=[\"test\",\"key1\",\"val1\"]\nTask: Generate up to 4 mutations preserving semantics and return ONLY JSON."},
    {"role": "assistant", "content": "{\"mutations\":[{\"cmd\":\"HGET test key1\",\"category\":\"probe\",\"oracle\":\"same_field\"},...]}"}
  ]
}
```
assistant 的内容保证：
- 仅为一个 JSON（无 markdown 代码块、无解释文本）；
- 顶层键 `mutations`；
- 每个 mutation 项包含：
  - `cmd`: Redis 命令文本
  - `category`: 变异类别
  - `oracle`: 对应可判定不变量 / 断言标签

## 4. 变异类别（category）与 Oracle 标签（oracle）
| category | 含义 | 典型命令 | oracle 示例 |
|----------|------|----------|-------------|
| probe | 只读探针，获取状态 | GET / LLEN / SCARD / ZCARD / HEXISTS | value_read / length_probe / cardinality_probe / membership_true |
| idempotent_repeat | 重复执行不改变结果 | HSET 相同字段 / SADD 已存在成员 | same_field / cardinality_plus_one_or_same |
| inverse | 逆操作或回滚 | HDEL / SREM / LPOP | post_condition_empty / cardinality_minus_one_or_zero |
| value_transform | 控制性变换 | SET 覆盖 / GETRANGE 全量 | mutable_change / value_full_range |
| idempotent_extend | 增量插入一次 | LPUSH X / SADD member_mut | length_plus_one / cardinality_plus_one_or_same |
| expire_variant | TTL 相关 | EXPIRE / PERSIST | ttl_set / ttl_removed |
| echo | 无高价值（保留占位） | COPY / SCAN | noop |

Oracle 标签用于后续执行层自动构建断言，例如：
- `same_field`: HGET 结果与先前写入一致；
- `post_condition_empty`: 删除后 HEXISTS/EXISTS 应返回 0；
- `cardinality_plus_one_or_same`: SADD 后集合大小变化 ∈ {0,+1}；
- `length_plus_one`: LPUSH 后 LLEN = 旧值 +1；
- `ordering_consistent`（未来扩展）：ZRANGE 顺序与语义一致。

## 5. 结构识别与分组策略
脚本内部维护 `COMMAND_GROUPS`：
- string: GET / SET / INCR / ...
- hash: HGET / HSET / HDEL / ...
- list: LPUSH / LRANGE / LLEN / LPOP / ...
- set: SADD / SREM / SCARD / SISMEMBER / ...
- zset: ZADD / ZREM / ZCARD / ZRANGE / ...
- ttl: EXPIRE / TTL / PERSIST / EXPIREAT / PEXPIREAT
- other: 暂未专项模板（输出 echo）

不同 group 触发对应变异模板（见脚本 `build_mutations` 函数）。

## 6. 生成脚本核心逻辑
`build_redis_mutation_dataset.py`：
1. 遍历 enriched 目录所有命令文件。
2. 加载 JSON，取第一条 example（可扩展为多条）。
3. 根据命令映射到 group，调用 `build_mutations` 生成候选 mutation（最多 4 条）。
4. 组装 messages 并写入 JSONL。
5. 去重逻辑保证同一 cmd 不重复。

示例（hash）模板片段：
```python
def build_mutations(group, cmd, args):
    if group == 'hash':
        muts = [
          (f"HGET {key} {field}", 'probe', 'same_field'),
          (f"HEXISTS {key} {field}", 'probe', 'membership_true'),
          (f"HSET {key} {field} {value}", 'idempotent_repeat', 'same_field'),
          (f"HDEL {key} {field}", 'inverse', 'post_condition_empty'),
        ]
```

## 7. 当前输出统计
- 样本总数：59 条（覆盖 Redis 多类命令）。
- 结构性覆盖：string/hash/list/set/zset/ttl 均有；other 组暂为 echo。
- 每条至多 4 个 mutations，避免 token 膨胀。

## 8. 与“语义丢失”缓解的关系
通过在训练中让模型学习：
- 聚合/集合/序列类型需伴随 probe（长度、基数、成员、顺序）；
- 提供逆操作/回滚（如 HDEL/SREM/LPOP）→ 支撑构造不变量链；
使模型在面对复杂 SQL→Redis 转换时，更可能输出一组带检验性的命令（或引导后续阶段补全），而不是单个读取语句，降低语义降级。

## 9. 使用步骤（Fine-tuning）
```bash
# 1. 重新生成（可选）
python3 src/MutationLlmModelFineTuning/build_redis_mutation_dataset.py

# 2. 上传 & 微调（示例）
python3 src/MutationLlmModelFineTuning/FineTuning_MutationLLM.py \
  --api_key YOUR_KEY \
  --training_data_filename MutationData/FineTuningTrainingData/redis_mutation.jsonl \
  --suffix redis-mutation-v1

# 3. 查询任务状态
python3 src/MutationLlmModelFineTuning/FineTuning_MutationLLM.py \
  --api_key YOUR_KEY \
  --job_id ftjob-xxxxxxx
```

## 10. 未来改进方向
| 优先级 | 改进 | 说明 |
|--------|------|------|
| 高 | 扩展 other 组模板 | 为 BRPOP/SCAN/MGET/DEL 提供 probe + side-effect 变异 |
| 高 | 增加 zset ordering 验证 | ZRANGE vs ZREVRANGE + ZCOUNT 范围组合 |
| 中 | 引入序列上下文样本 | messages 多轮对话，模拟操作链变异 |
| 中 | 利用语义 KB 的 Define/Use | 基于 redis_semantic_kb.json 注入生命周期提示 |
| 中 | 负例样本 | 非法 key 变体 / 语义破坏命令，训练拒绝策略 |
| 低 | 多 example/多样本扩增 | 同一命令多参数形态覆盖 |
| 低 | 统计平衡 | 控制各 group 样本占比均衡 |

## 11. 兼容与风险提示
- echo 类样本较弱，过多会让模型倾向不变异 → 后续需补强或筛除。
- 没有引入真实执行结果特征（如成功/失败标签），不会直接学“错误过滤”，仅学结构模式；可在下一版引入真实执行标签。
- 如果未来 OpenAI fine-tune 要求更严格的 JSON schema，可再添加 schema version 字段：`{"schema":"v1", "mutations": [...]}`。

## 12. 快速验证（本地检查格式）
```python
import json, itertools
fn = 'MutationData/FineTuningTrainingData/redis_mutation.jsonl'
for i,l in enumerate(open(fn,'r',encoding='utf-8')):
    obj = json.loads(l)
    assert 'messages' in obj
    roles = [m['role'] for m in obj['messages']]
    assert roles == ['system','user','assistant']
    json.loads(obj['messages'][-1]['content'])  # 可解析
print('OK')
```

## 13. 结论
该数据集为“Redis 变异 + 语义保持”建立了初始可监督信号，解决了之前转换阶段缺乏可判定探针的问题。通过后续迭代增强命令覆盖、序列上下文与负例控制，可进一步支撑高质量的跨方言迁移与 Oracle 构造。

---
作者：自动生成
时间：最新运行时自动记录
