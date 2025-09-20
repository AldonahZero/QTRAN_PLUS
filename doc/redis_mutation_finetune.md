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

## 7.1 本次变更（审阅占位）
> 下面为建议在提交时填写的“前/后”统计对比，用以量化此次脚本改动或数据扩充的影响。

- 变更前（先运行旧脚本并记录）
  - 样本总数：__TODO__
  - 全部为 echo 的样本数：__TODO__
  - echo 比例：__TODO__
  - zset 相关样本/突变数：__TODO__

- 变更后（运行当前脚本并记录）
  - 样本总数：59
  - 全部为 echo 的样本数：8
  - echo 比例：13.6%
  - zset 相关样本/突变数（示例）：ZCARD:10, ZCOUNT:10, ZSCORE:10, ZRANK:10

这些统计是自动化分析脚本运行后得到的样例结果；在执行 review 提交时，可替换上面的“变更前”占位为真实旧数据，以便展示改动影响。

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

## 14. 升级路线（Roadmap）

| 阶段 | 目标 | 关键动作 | KPI（衡量指标） | 备注 |
|------|------|----------|----------------|------|
| Phase 0 (当前) | 建立初始结构化监督信号 | 基本分组 + probe/inverse/idempotent + KB_context 注入 | 样本数=59；echo 全部样本比 ≈13.6%；zset 4+核心探针齐备 | 已完成基础脚本与注释 |
| Phase 1 | 扩容 & 降 echo | 多 example/command；other 组模板化（EXISTS/TYPE/SCAN/DUMP）；统计自动化 | 样本数≥300；echo 全部样本比 <8%；各 group 样本数差距 <2x | 优先实现脚本参数化 --max-examples |
| Phase 2 | 引入执行验证信号 | 批量执行 mutations 记录返回 + oracle_pass 布尔；生成 stats.json | 样本数≥500；≥60% 样本含执行验证；oracle_pass 标记覆盖 100% 验证样本 | 需本地/容器 Redis 环境隔离 |
| Phase 3 | 序列上下文 & 复合语义 | multi-command 原始种子；链式 probe (长度→成员→顺序)；zset ordering 校验 | 带多轮/多命令样本占比≥30%；新增 oracle: ordering_consistent / reverse_consistent | 增加 system prompt 版本号 schema=v2 |
| Phase 4 | 负例与拒绝策略 | 加入危险/无意义变异案例 + should_reject；混入少量空 mutations | negative/拒绝类样本占比 5~10%；模型误输出破坏指令比例下降 | 需清晰标签防止模型过度保守 |
| Phase 5 | 质量迭代 & 去重 | 语义近似聚类去重；难例挖掘（失败/不稳定场景） | 去重后有效 token 占比≥90%；新增难例集合 N≥200 | 可用 SimHash/MinHash |
| Phase 6 | 统一跨方言协同 | 与 SQL→Redis 翻译样本联动；生成“翻译 + 变异 + 验证”组合样本 | 组合样本≥300；翻译后补变异覆盖率≥80% | 促进端到端迁移稳健性 |

### 14.1 关键技术细节建议
1. 多 example 扩容：修改 `build_redis_mutation_dataset.py` 中只取第一条 example 的逻辑，允许 `--max-examples-per-command N`（默认 1）。
2. 自动统计：新增脚本 `scripts/redis_mutation_stats.py` 产出 JSON：{ total_samples, echo_all_samples, echo_ratio, group_counts:{}, category_counts:{}, zset_probes:{}, avg_mutations_per_sample } 并在生成后更新文档 7.1。
3. other 组模板化：针对 EXISTS/DEL/COPY/SCAN：
  - EXISTS k → probe 存在性 + TYPE k → probe 类型；
  - SCAN cursor MATCH pattern COUNT n → 生成 pattern 变体 / COUNT 调整；
  - DEL k → 先 EXISTS/TYPE，再 DEL，再 EXISTS（二阶段 oracle: deletion_effect）。
4. 执行验证：
  - 运行时隔离：为每条样本随机前缀 key（如 prefix:runid:origkey）避免相互污染；
  - 记录执行：⟨cmd, return_raw, error_flag⟩；
  - 推导 oracle_pass：根据 category + 前后状态（例如 HLEN 变化, SCARD 差值, TTL 正值等）。
5. 序列上下文：
  - messages.user 中 Original 多行：第一行 //SETUP，其后种子命令；
  - 允许 assistant 输出 mutations 按序列数组（可能加 index）。
6. 负例策略：
  - 设计 should_reject 原因（破坏语义/跨 key/无效 TTL 等）；
  - 让模型学会返回空 mutations 或标注 rejection。
7. 语义去重：
  - 对 assistant.content JSON 正规化排序后 hash；
  - 统计 hash 冲突率，剔除重复。
8. 难例挖掘：
  - 从 SQL→Redis 翻译真实日志挑出失败/低质量翻译案例，手工或自动生成针对性 probe（例如多级嵌套结构 / 大基数集合）。
9. 跨方言协同：
  - 生成组合样本格式：messages: [ system(translator+mutator), user(SQL seed), assistant(翻译结果 JSON 含 redis cmds + probes) ]。

### 14.2 KPI 计算示例（公式）
```
echo_ratio = echo_all_samples / total_samples
avg_mutations_per_sample = sum(len(mutations_i)) / total_samples
zset_probe_coverage = (#出现的 distinct zset probe 类型) / (目标集合大小)
oracle_execution_coverage = (#含 oracle_pass 字段的 mutations) / (全部 mutations)
group_balance_ratio = max(group_counts.values()) / min(nonzero_group_counts.values())
```

### 14.3 版本化建议
- 在 assistant JSON 增加: {"schema":"v1"} → 未来执行验证/负例时升级为 v2/v3。
- system prompt 中注明支持的 schema 版本，避免旧模型混淆。

### 14.4 风险与缓解
| 风险 | 描述 | 缓解措施 |
|------|------|----------|
| 过拟合模板 | 模板重复导致模型机械生成 | 扩增参数扰动 + 语义去重 + 难例挖掘 |
| echo 残留 | other 组未完全模板化 | 分阶段替换 & 统计硬指标 gate |
| 执行污染 | 多样本共享 key 污染状态 | 随机前缀隔离 & teardown | 
| 负例误导 | 过多拒绝导致保守行为 | 控制负例占比 ≤10% 并加权训练 |
| token 膨胀 | 多轮上下文导致训练成本激增 | 控制 avg_mutations_per_sample ≤4, 去除冗余字段 |

### 14.5 快速优先级行动清单（可直接实施）
1. (Phase1) 增加脚本参数 --max-examples-per-command；写入新样本；生成 stats.json；更新 7.1。
2. (Phase1) 实现 other 组 EXISTS/TYPE/DEL/SCAN 基础模板，目标 echo_ratio <8%。
3. (Phase2) 编写 executor：对每条样本 mutations 执行 + 记录返回，产出 oracle_pass。
4. (Phase3) 增加多命令种子格式 & ordering_consistent oracle。
5. (Phase4+) 引入 should_reject/negative 样本并评估对主任务影响。

---
