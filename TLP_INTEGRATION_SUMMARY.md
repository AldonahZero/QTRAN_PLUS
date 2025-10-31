# TLP Checker 集成总结

## 🎉 集成完成

TLP (Ternary Logic Partitioning) Oracle Checker 已成功集成到QTRAN的Oracle检查系统中。

---

## 📝 修改内容

### 1. Oracle检查逻辑扩展 (`src/TransferLLM/translate_sqlancer.py`)

**位置**: 第624-641行

```python
# 新增TLP Oracle专用检查分支
from src.Tools.OracleChecker.tlp_checker import is_tlp_mutation, check_tlp_oracle

is_tlp = bug.get("molt") == "tlp" or is_tlp_mutation(mutate_results[-1])

if is_tlp and len(mutate_results) >= 4:
    # 使用TLP专用checker验证不变式
    # TLP需要4个结果：original, tlp_true, tlp_false, tlp_null
    oracle_check_res = check_tlp_oracle(mutate_results[-4:])
    print(f"🔍 TLP Oracle Check: {oracle_check_res.get('end')} (bug_type: {oracle_check_res.get('bug_type')})")
    if oracle_check_res.get("details"):
        print(f"   Details: {oracle_check_res['details'].get('explanation', '')}")
```

**功能**:
- ✅ 自动识别TLP类型的变异
- ✅ 收集最近4个变异结果（original + 3个分区）
- ✅ 调用`check_tlp_oracle`验证TLP不变式
- ✅ 输出详细的检查结果和bug类型

---

### 2. NoSQL结果处理修复

**修改**: 扩展了NoSQL类型识别，支持MongoDB的`shell_result`类型

**Before**:
```python
is_kv_before = isinstance(before_result, dict) and str(
    before_result.get("type", "")
).startswith("kv_")
```

**After**:
```python
is_nosql_before = isinstance(before_result, dict) and "type" in before_result
is_nosql_after = isinstance(after_result, dict) and "type" in after_result

is_kv_before = is_nosql_before and str(before_result.get("type", "")).startswith("kv_")
is_kv_after = is_nosql_after and str(after_result.get("type", "")).startswith("kv_")
```

**新增NoSQL专用分支**:
```python
elif is_nosql_before and is_nosql_after:
    # 使用NoSQL专用转换器
    from src.Tools.OracleChecker.oracle_check import convert_nosql_result_to_standard
    converted_before_result = convert_nosql_result_to_standard(before_result)
    converted_after_result = convert_nosql_result_to_standard(after_result)
    ...
```

---

## 🔄 Oracle检查流程

现在的Oracle检查系统支持多种类型：

```
Oracle Check 入口
    │
    ├─→ 执行错误？
    │   └─→ {"end": False, "error": "exec fail"}
    │
    ├─→ TLP类型？(molt=="tlp" 或 有tlp_partition)
    │   └─→ check_tlp_oracle(mutate_results[-4:])
    │       ├─ 验证: count(Q) == count(Q_true) + count(Q_false) + count(Q_null)
    │       ├─ 通过: {"end": True, "error": None}
    │       └─ 失败: {"end": False, "bug_type": "TLP_violation", ...}
    │
    ├─→ KV类型？(type="kv_*")
    │   └─→ 直接比较KV结果
    │
    ├─→ NoSQL类型？(type="shell_result"等)
    │   └─→ convert_nosql_result_to_standard + Check
    │
    └─→ SQL关系型
        └─→ execSQL_result_convertor + Check
```

---

## 🧪 测试验证

**测试文件**: `test_tlp_integration.py`

**测试结果**: ✅ 所有核心功能测试通过

```bash
./venv/bin/python test_tlp_integration.py

============================================================
测试1: TLP Oracle 通过（不变式成立）
============================================================
✅ 检查结果: True
   详情: TLP invariant holds: 10 == 5 + 3 + 2

============================================================
测试2: TLP Oracle 违反（发现Bug）
============================================================
❌ 检查结果: False
   Bug类型: TLP_violation
   详情: TLP invariant violated: 10 ≠ 5 + 3 + 1

============================================================
测试3: TLP变异识别
============================================================
✅ 正确识别TLP变异
✅ 正确识别非TLP变异

============================================================
🎉 所有测试通过！TLP Checker集成成功！
============================================================
```

---

## 📊 TLP Oracle示例

### 正常情况（通过）

```python
mutations_results = [
    {"MutateSqlExecResult": "[1,2,3,4,5]"},      # original: 5个文档
    {"MutateSqlExecResult": "[1,2]"},            # P=true: 2个
    {"MutateSqlExecResult": "[3,4]"},            # P=false: 2个
    {"MutateSqlExecResult": "[5]"},              # P=null: 1个
]

# 验证: 5 == 2 + 2 + 1 ✅
oracle_check = check_tlp_oracle(mutations_results)
# {"end": True, "error": None}
```

### Bug情况（失败）

```python
mutations_results = [
    {"MutateSqlExecResult": "[1,2,3,4,5]"},      # original: 5个文档
    {"MutateSqlExecResult": "[1,2]"},            # P=true: 2个
    {"MutateSqlExecResult": "[3,4]"},            # P=false: 2个
    {"MutateSqlExecResult": "[]"},               # P=null: 0个 ❌ 少了1个！
]

# 验证: 5 ≠ 2 + 2 + 0 ❌ Bug!
oracle_check = check_tlp_oracle(mutations_results)
# {"end": False, "bug_type": "TLP_violation", "details": {...}}
```

---

## 🔍 Bug检测增强

TLP Oracle可以检测以下类型的Bug：

1. **三值逻辑错误**: NULL值处理不正确
2. **分区遗漏**: 某些记录在分区时丢失
3. **重复计数**: 某些记录在多个分区中出现
4. **条件判断错误**: WHERE子句逻辑错误

---

## 🎯 使用场景

### 输入文件格式

```jsonl
{
  "index": 338,
  "a_db": "sqlite",
  "b_db": "mongodb",
  "molt": "tlp",  // ← 指定使用TLP Oracle
  "sql": "SELECT HEX(MIN(a)) FROM ..."
}
```

### 运行测试

```bash
python -m src.main --input_filename Input/tlp_tests.jsonl --tool sqlancer
```

### 检查输出

- **变异结果**: `Output/<input_name>/MutationLLM/<index>.jsonl`
- **可疑Bug**: `Output/<input_name>/SuspiciousBugs/<index>.jsonl`

---

## 📈 优势

| 特性 | NoREC | TLP |
|------|-------|-----|
| **检测范围** | 查询返回空结果的bug | 三值逻辑和分区错误 |
| **NULL值处理** | ❌ 有限 | ✅ 完整支持 |
| **数学基础** | 结果非空性 | 三值逻辑分区定理 |
| **Bug类型** | 过度过滤 | 逻辑错误、NULL处理 |
| **精确度** | 中等 | 高 |

---

## 🔧 依赖

- `src/Tools/OracleChecker/tlp_checker.py` - TLP checker核心逻辑
- `src/Tools/json_utils.py` - JSON解析工具（需要`json_repair`）
- `src/Tools/OracleChecker/oracle_check.py` - Oracle检查基础设施

---

## 📝 注意事项

1. **TLP需要4个变异结果**: original + tlp_true + tlp_false + tlp_null
2. **自动识别**: 系统会自动检测`molt="tlp"`或变异中的`oracle: "tlp_partition"`
3. **结果格式**: 支持SQL列表结果和NoSQL字典结果
4. **错误处理**: 解析失败时返回`bug_type: "parse_error"`

---

## ✅ 验证方法

```bash
# 运行集成测试
./venv/bin/python test_tlp_integration.py

# 运行实际测试
python -m src.main --input_filename Input/all.jsonl --tool sqlancer

# 查看TLP bug报告
cat Output/all/SuspiciousBugs/<index>.report.json
```

---

**集成日期**: 2025-10-31  
**状态**: ✅ 已完成并测试通过  
**贡献者**: Claude AI Assistant

