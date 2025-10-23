# 🎯 Transfer 调度逻辑修复 - 快速总结

## 问题
**原来的错误**: 根据**数据库类型**决定测试策略
```python
if (origin_db is SQL) and (target_db is SQL):
    use semantic testing  # ❌ 错误假设
else:
    use crash testing     # ❌ 错误假设
```

**为什么错误**:
- Redis → MongoDB 被强制使用崩溃测试,但 `molt="semantic"` 要求语义测试
- 混淆了"数据库类型"和"测试策略"两个概念

## 修复
**现在的正确逻辑**: 根据**测试策略(molt)**决定
```python
molt = test_info.get("molt")

if molt in ["semantic", "norec", "tlp", "dqe", "pinolo"]:
    use semantic testing  # ✅ 语义等价测试
elif molt in ["crash", "hang", "fuzz", "stress"]:
    use crash testing     # ✅ 崩溃/稳定性测试
else:
    fallback to db type   # 向后兼容
```

## 文件修改
📄 `src/TransferLLM/TransferLLM.py` - `transfer_llm()` 函数

## 影响
✅ **修复前**: Redis → MongoDB + semantic 策略会错误地使用崩溃测试  
✅ **修复后**: 正确使用语义等价测试,能验证转换的正确性

## 测试
```bash
# 验证修复
python src/main.py --input Input/redis_semantic.jsonl --output test

# 检查是否使用语义测试(应该有 exec_equalities 字段)
jq '.TransferSqlExecEqualities' Output/test/TransferLLM/*.jsonl
```

## 设计原则
**分离关注点**:
- `molt` (测试策略) → 决定**如何测试**
- `a_db/b_db` (数据库类型) → 决定**语法映射**

---
**结论**: 测试策略应该由测试工具(molt)驱动,而不是数据库类型。修复后系统更加灵活和正确。
