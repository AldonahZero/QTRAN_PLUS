# Transfer 调度逻辑修复说明

## 🔴 原始问题

**错误的调度逻辑**:
```python
# ❌ 错误:根据数据库类型决定测试策略
if (origin_db in SQL_DIALECTS) and (target_db in SQL_DIALECTS):
    return transfer_llm_sql_semantic(...)  # 语义等价测试
else:
    return transfer_llm_nosql_crash(...)   # 崩溃测试
```

**问题**:
- Redis → MongoDB 被归类为 NoSQL,强制使用崩溃测试
- 但实际上 `molt="semantic"` 表示应该做**语义等价测试**
- 数据库类型 ≠ 测试策略

## ✅ 修复后的逻辑

**正确的调度逻辑**:
```python
# ✅ 正确:根据测试策略(molt)决定测试方法
molt = test_info.get("molt", "").lower()

if molt in SEMANTIC_STRATEGIES:  # semantic, norec, tlp, dqe, pinolo
    return transfer_llm_sql_semantic(...)  # 语义等价测试
elif molt in CRASH_STRATEGIES:  # crash, hang, fuzz, stress
    return transfer_llm_nosql_crash(...)   # 崩溃测试
else:
    # 回退到基于数据库类型的默认策略(向后兼容)
    ...
```

## 📊 测试策略分类

### 语义等价策略 (`SEMANTIC_STRATEGIES`)
这些策略关注**查询结果的正确性**:
- `semantic`: 语义等价测试
- `norec`: NoREC oracle (Non-optimizing Reference Engine Construction)
- `tlp`: TLP (Ternary Logic Partitioning)
- `dqe`: DQE (Differential Query Execution)
- `pinolo`: Pinolo oracle
- `pqs`: PQS (Pivoted Query Synthesis)

**适用场景**: SQL/NoSQL 都可以,只要目标是验证转换后的语义等价性

### 崩溃/稳定性策略 (`CRASH_STRATEGIES`)
这些策略关注**系统的稳定性**:
- `crash`: 崩溃检测
- `hang`: 挂起检测
- `fuzz`: 模糊测试
- `stress`: 压力测试

**适用场景**: 任何数据库,目标是发现导致崩溃/挂起的输入

## 🎯 实际案例

### 案例 1: Redis → MongoDB (molt=semantic)
```json
{
  "a_db": "redis",
  "b_db": "Memcached", 
  "molt": "semantic",
  "sql": "set mykey hello"
}
```

**旧逻辑**: 
- ❌ 检测到 NoSQL → 使用 `transfer_llm_nosql_crash`
- ❌ 执行崩溃检测,返回 `crash=false, hang=false`
- ❌ 无法验证语义等价性

**新逻辑**:
- ✅ 检测到 `molt=semantic` → 使用 `transfer_llm_sql_semantic`
- ✅ 生成 MongoDB 命令并验证结果等价性
- ✅ 返回 `exec_equalities=[True]`

### 案例 2: Redis Fuzzing (molt=fuzz)
```json
{
  "a_db": "redis",
  "b_db": "redis",
  "molt": "fuzz",
  "sql": "SET key1 <random_data>"
}
```

**新逻辑**:
- ✅ 检测到 `molt=fuzz` → 使用 `transfer_llm_nosql_crash`
- ✅ 执行崩溃检测
- ✅ 返回 `crash=false, hang=false` 或检测到的问题

### 案例 3: MySQL → PostgreSQL (molt=tlp)
```json
{
  "a_db": "mysql",
  "b_db": "postgres",
  "molt": "tlp",
  "sql": "SELECT * FROM t WHERE c1 > 10"
}
```

**新逻辑**:
- ✅ 检测到 `molt=tlp` → 使用 `transfer_llm_sql_semantic`
- ✅ 生成 PostgreSQL 命令并使用 TLP oracle 验证
- ✅ 返回 `exec_equalities=[True/False]`

## 🔄 向后兼容

如果 `test_info` 中**没有 `molt` 字段**(旧数据):
- 回退到基于数据库类型的默认策略
- SQL → SQL: 使用语义测试
- 涉及 NoSQL: 使用崩溃测试

## 📝 代码变更摘要

**文件**: `src/TransferLLM/TransferLLM.py`

**函数**: `transfer_llm()`

**修改**:
1. 添加策略集合定义:
   - `SEMANTIC_STRATEGIES`: 语义等价测试策略
   - `CRASH_STRATEGIES`: 崩溃/稳定性测试策略

2. 修改调度逻辑:
   ```python
   # 从 test_info 中获取 molt
   molt = test_info.get("molt", "").lower()
   
   # 根据 molt 决定策略
   if molt in SEMANTIC_STRATEGIES:
       return transfer_llm_sql_semantic(...)
   elif molt in CRASH_STRATEGIES:
       return transfer_llm_nosql_crash(...)
   else:
       # 向后兼容的回退逻辑
       ...
   ```

3. 更新文档字符串:
   - 说明调度依据是 `molt` 而非数据库类型

## 🧪 验证方法

### 单元测试
```python
def test_transfer_dispatch():
    # 测试 semantic 策略
    test_info = {"molt": "semantic", "sql": "..."}
    result = transfer_llm(..., test_info=test_info)
    # 应该调用 transfer_llm_sql_semantic
    
    # 测试 crash 策略
    test_info = {"molt": "crash", "sql": "..."}
    result = transfer_llm(..., test_info=test_info)
    # 应该调用 transfer_llm_nosql_crash
```

### 集成测试
```bash
# 使用 semantic 策略测试 Redis → MongoDB
python src/main.py --input Input/redis_semantic.jsonl --output test_semantic

# 检查是否使用了语义测试
jq '.TransferSqlExecEqualities' Output/test_semantic/TransferLLM/*.jsonl
# 应该看到 [true] 或 [false],而不是崩溃检测结果
```

## 💡 设计原则

**分离关注点 (Separation of Concerns)**:
- **测试策略 (molt)**: 决定**如何测试**(语义 vs 崩溃)
- **数据库类型 (a_db/b_db)**: 决定**语法/特性映射**

**示例**:
- Redis → MongoDB + molt=semantic: 使用语义测试,验证转换正确性
- Redis → Redis + molt=fuzz: 使用崩溃测试,发现稳定性问题
- MySQL → PostgreSQL + molt=tlp: 使用语义测试,采用 TLP oracle

## 📚 相关文档

- **SQLancer 测试策略**: 参考 SQLancer 的 oracle 分类
- **NoSQL 测试方法**: 参考 NoSQLFuzz 的测试策略
- **原始设计**: `doc/abstract.md` 中的测试流程说明

---

**总结**: 修复后,测试策略的选择由 `molt` 字段驱动,而非简单地根据数据库类型,使系统更灵活且符合测试工具的实际语义。
