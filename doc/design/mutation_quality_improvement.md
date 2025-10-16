# Redis → MongoDB 变异产物质量改进方案

## 📊 问题诊断结果

运行质量分析后发现:
```
Quality Rate: 0.00% (0/4 valid mutations)
Error Type: 100% 简化伪命令 (simple_command)
```

**示例问题**:
```json
// ❌ 当前生成的错误格式
{"cmd": "find kv", "category": "probe", "oracle": "value_read"}
{"cmd": "count kv", "category": "probe", "oracle": "cardinality_probe"}
{"cmd": "delete kv", "category": "inverse", "oracle": "noop"}

// ✅ 应该生成的正确格式
{"cmd": "{\"op\":\"findOne\",\"collection\":\"kv\",\"filter\":{\"_id\":\"mykey\"}}", 
 "category": "probe", "oracle": "value_read"}
```

## 🔧 已实施的修复

### 1. 新增专用 MongoDB Prompt
创建了 `MutationData/MutationLLMPrompt/semantic_mongodb.json`:
- ✅ 明确要求输出 MongoDB JSON 格式
- ✅ 提供完整的格式示例和约束
- ✅ 包含转义字符处理说明
- ✅ 强调 NO markdown / NO code blocks

### 2. 修改 MutateLLM.py
在 `run_muatate_llm_single_sql()` 中:
- ✅ 检测目标数据库类型 (MongoDB/Mongo)
- ✅ 自动切换到 `semantic_mongodb.json` prompt
- ✅ 调整用户消息格式,明确说明是"转换后的 MongoDB 操作"

### 3. 添加质量验证工具
创建了 `src/Tools/fix_mutation_quality.py`:
- ✅ 自动检测简化伪命令
- ✅ 验证 MongoDB JSON 格式
- ✅ 生成详细质量报告
- ✅ 按文件/错误类型统计

## 🚀 使用新方案

### 重新运行变异生成
确保你的代码调用变异时传递了正确的 `db_type`:

```python
# 在 translate_sqlancer.py 或类似文件中
mutate_result, mutate_cost = run_muatate_llm_single_sql(
    tool="sqlancer",
    client=openai_client,
    model_id=mutation_llm_model_id,
    mutate_name="semantic",
    oracle="semantic",
    db_type="mongodb",  # ⚠️ 关键:必须明确指定 mongodb
    sql=transferred_mongodb_cmd  # 传入转换后的 MongoDB JSON
)
```

### 验证新产物质量
```bash
python src/Tools/fix_mutation_quality.py <output_name>
```

期望结果: `Quality Rate: 90%+`

## 📋 Checklist - 下一步行动

### 立即行动 (优先级 P0)
- [ ] **检查 TransferLLM 调用点**: 确认传递给变异的 `db_type` 是 `"mongodb"` 而非 `"redis"`
  - 文件: `src/TransferLLM/translate_sqlancer.py` 行 270-290 附近
  
- [ ] **验证 TransferResult 格式**: 确保传给变异的 `sql` 参数是完整的 MongoDB JSON,不是 Redis 命令
  
- [ ] **清空旧产物重新生成**: 
  ```bash
  rm -rf Output/redis_demo_04/MutationLLM/*.jsonl
  # 重新运行你的 pipeline
  ```

### 短期优化 (优先级 P1)
- [ ] **添加 Prompt 温度控制**: 在调用 LLM 时设置 `temperature=0.1` 提高一致性
  
- [ ] **实现自动重试机制**: 如果生成的变异格式错误,自动用更严格的 prompt 重试一次
  
- [ ] **增强错误提示**: 在执行失败时打印具体的 JSON 解析错误位置

### 长期改进 (优先级 P2)
- [ ] **引入结构化输出**: 使用 OpenAI 的 JSON Schema mode (response_format)
  
- [ ] **微调专用模型**: 基于正确的 MongoDB 变异样本微调模型
  
- [ ] **添加后处理修复**: 自动识别并修复常见格式错误(如缺少转义)

## 🧪 测试方案

### 单元测试
创建 `tests/test_mutation_quality.py`:

```python
def test_mutation_format():
    """验证变异命令是有效的 MongoDB JSON"""
    sample_mutation = {
        "cmd": '{"op":"findOne","collection":"kv","filter":{"_id":"key1"}}',
        "category": "probe",
        "oracle": "value_read"
    }
    
    cmd = sample_mutation["cmd"]
    parsed = json.loads(cmd)
    assert "op" in parsed
    assert "collection" in parsed
    assert parsed["op"] in ["findOne", "find", "updateOne", ...]
```

### 集成测试
```bash
# 1. 运行小样本
python src/main.py --input Input/redis/small_test.jsonl --output test_output

# 2. 验证质量
python src/Tools/fix_mutation_quality.py test_output

# 3. 检查执行成功率
jq '.MutateSqlExecError' Output/test_output/MutationLLM/*.jsonl | grep -c "None"
```

## 📚 相关文档参考

- **设计文档**: `doc/design/redis_to_mongodb_conversion_summary.md`
  - 第 3 节: 命令转换策略
  - 第 8 节: 最小示例片段

- **Prompt 工程**: `MutationData/MutationLLMPrompt/semantic_mongodb.json`
  - STRICT OUTPUT FORMAT 部分
  - EXAMPLES 部分

- **执行器要求**: `src/Tools/DatabaseConnect/mongodb_executor.py` (推测路径)
  - 查看 `exec_mongodb_json()` 函数的输入格式要求

## 🎯 预期改进效果

| 指标 | 当前 | 目标 | 改进幅度 |
|------|------|------|---------|
| 格式正确率 | 0% | 95%+ | +95% |
| 执行成功率 | ~20% | 85%+ | +65% |
| Oracle 通过率 | N/A | 70%+ | - |
| 可疑 Bug 数 | 0 (因执行失败) | 预期 5-10 | - |

## ⚠️ 常见陷阱

1. **db_type 参数错误传递**
   - ❌ `db_type="redis"` (因为原始来源是 redis)
   - ✅ `db_type="mongodb"` (因为目标/执行是 mongodb)

2. **转义字符处理**
   - cmd 字段本身是字符串,内部包含 JSON,需要转义引号
   - 示例: `"cmd": "{\"op\":\"find\",...}"`

3. **Prompt 版本混淆**
   - 确保代码中没有硬编码 `semantic.json`,而是根据 db_type 动态选择

4. **LLM 输出清洗不足**
   - 可能返回 markdown 代码块: ```json\n{...}\n```
   - 需要添加清洗逻辑去除多余标记

## 🔍 调试技巧

### 打印中间产物
在 `MutateLLM.py` 的 `run_muatate_llm_single_sql` 中:
```python
print(f"[DEBUG] db_type={db_type}, is_mongodb_target={is_mongodb_target}")
print(f"[DEBUG] prompt_path={mutate_prompt_path}")
print(f"[DEBUG] response_content={response_content[:200]}...")
```

### 手动测试 Prompt
```python
from openai import OpenAI
client = OpenAI(api_key="...")

messages = [
    {"role": "system", "content": open("...semantic_mongodb.json").read()},
    {"role": "user", "content": 'Seed: {"op":"updateOne","collection":"kv",...}'}
]

response = client.chat.completions.create(model="gpt-4o-mini", messages=messages)
print(response.choices[0].message.content)
```

### 逐步验证
1. ✅ Prompt 文件存在且格式正确
2. ✅ MutateLLM.py 中的条件判断生效
3. ✅ LLM 返回包含 `{"mutations":[...]}`
4. ✅ cmd 字段是完整的 MongoDB JSON 字符串
5. ✅ 执行器能解析并执行

---

**最后建议**: 先用 1-2 个样本测试完整流程,确认质量达标后再批量运行。保留旧 prompt 作为备份(针对 SQL 场景仍然需要)。
