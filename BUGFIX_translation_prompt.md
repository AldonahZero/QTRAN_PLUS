# Bug修复：翻译Prompt导致数据被改变

## 🔍 问题描述

加入mem0后，LLM翻译质量反而下降，出现：
- ❌ LLM改变数据值（NULL → 默认值，'' → '1969-12-21'）
- ❌ LLM删除数据（删除NULL值）
- ❌ LLM搞混值的位置（true和-805450823互换）
- ❌ LLM改变表名（t2 → t0）

## 🐛 根本原因

**Prompt第1240行的指令有严重歧义：**

```python
# src/TransferLLM/TransferLLM.py:1240
2. Strictly forbid meaningless features(such as NULL,0), 
   features with random return value(such as current_time).
```

### LLM的错误理解

| 原意 | LLM理解 | 导致的问题 |
|------|---------|-----------|
| 避免不可复制的特性（如CURRENT_TIME） | 删除所有"无意义"的数据 | NULL、空字符串、0都被改变 |
| 移除非确定性函数 | 修改任何看起来"不合理"的值 | 普通数据也被擅自修改 |

### 实际案例

**案例1：删除NULL值**
```sql
-- 原始
INSERT INTO t0(c0) VALUES(NULL), ('0.9173837544006114'), ("Y?")

-- LLM翻译（错误）
INSERT INTO t0(c0) VALUES('0.9173837544006114'), ('Y?')  
-- ❌ NULL被删除了！
```

**案例2：改变数据值**
```sql
-- 原始
INSERT INTO t1(c2, c0, c1) VALUES ('', true, -805450823)

-- LLM翻译（错误）
INSERT INTO t1(c2, c0, c1) VALUES ('1969-12-21', -805450823, 1)
-- ❌ 所有3个值都被改变了！
```

**案例3：改变表名**
```sql
-- 原始
INSERT INTO t2(c0) VALUES('*{5 !r''')

-- LLM翻译（错误）
INSERT INTO t0(c0) VALUES('*{5 !r''')
-- ❌ t2被改成t0了！
```

## 📊 mem0的影响

**mem0本身不是问题**，但可能加剧了问题：

1. **如果历史记忆中包含错误翻译案例：**
   ```
   记忆示例：
   Input:  INSERT INTO t0 VALUES(NULL)
   Output: INSERT INTO t0 VALUES('default')  ← 错误！
   ```

2. **LLM会学习这个错误模式：**
   - 看到NULL就删除
   - 看到空字符串就替换成默认值
   - 看到不存在的表名就改成存在的表

3. **形成恶性循环：**
   - 错误翻译 → 存入mem0 → LLM学习 → 更多错误翻译

## ✅ 解决方案

### 方案1：修改Prompt（立即生效）

修改 `src/TransferLLM/TransferLLM.py` 第1240行：

**❌ 当前的错误prompt：**
```python
2. Strictly forbid meaningless features(such as NULL,0), 
   features with random return value(such as current_time).
```

**✅ 修改后的正确prompt：**
```python
2. Keep all data values EXACTLY as they are in the original statement.
   This includes NULL values, empty strings (''), zeros (0), and all other literal values.
   ONLY remove non-deterministic functions that produce random results (such as CURRENT_TIMESTAMP(), RANDOM(), NOW()).
   NEVER modify, delete, or substitute actual data values or table names.
```

### 方案2：清理错误的mem0记忆

```bash
cd /root/QTRAN

# 检查是否有错误记忆
python3 << 'PYTHON'
import os
os.environ["QTRAN_USE_MEM0"] = "true"

from src.TransferLLM.mem0_adapter import TransferMemoryManager

# 检查DuckDB→PostgreSQL的历史翻译
mgr = TransferMemoryManager(user_id="qtran_duckdb_to_postgres")
memories = mgr.get_relevant_memories("INSERT INTO", "duckdb", "postgres", limit=10)

print("=== 检查历史翻译记忆 ===")
for i, m in enumerate(memories, 1):
    print(f"\n【记忆 {i}】")
    if 'NULL' in str(m) or 'default' in str(m).lower():
        print("⚠️ 可能包含错误的NULL处理")
    print(m)
PYTHON

# 如果发现错误记忆，清除它们
# python3 -c "
# from src.TransferLLM.mem0_adapter import TransferMemoryManager
# mgr = TransferMemoryManager(user_id='qtran_duckdb_to_postgres')
# # 清除特定的错误记忆
# mgr.delete_memories([memory_id])
# "
```

### 方案3：添加翻译验证

在翻译后添加验证逻辑，检查：
1. 数据值数量是否一致
2. NULL值是否被保留
3. 表名/列名是否改变

```python
def validate_translation(original_sql: str, translated_sql: str) -> bool:
    """验证翻译是否忠实"""
    # 检查VALUES中的值数量
    original_values = extract_values(original_sql)
    translated_values = extract_values(translated_sql)
    
    if len(original_values) != len(translated_values):
        print(f"⚠️ 值数量不匹配: {len(original_values)} → {len(translated_values)}")
        return False
    
    # 检查NULL是否被保留
    if 'NULL' in original_sql.upper() and 'NULL' not in translated_sql.upper():
        print(f"⚠️ NULL值被删除")
        return False
    
    # 检查表名是否改变
    original_table = extract_table_name(original_sql)
    translated_table = extract_table_name(translated_sql)
    
    if original_table != translated_table:
        print(f"⚠️ 表名被改变: {original_table} → {translated_table}")
        return False
    
    return True
```

## 📝 具体修改步骤

### Step 1: 修改Prompt

```bash
cd /root/QTRAN

# 备份原文件
cp src/TransferLLM/TransferLLM.py src/TransferLLM/TransferLLM.py.backup

# 修改第1240行
# 手动编辑或使用以下命令
```

### Step 2: 测试修改效果

```bash
# 使用修复后的prompt重新测试
python3 -m src.main \
  --input_filename Input/bugs_duckdb_to_postgres.jsonl \
  --tool sqlancer

# 检查是否还有数据被改变的问题
cat Output/bugs_duckdb_to_postgres/SuspiciousBugs/*.report.json
```

### Step 3: 验证效果

检查修复后的翻译：
```bash
# 查看第一个bug的翻译
cat Output/bugs_duckdb_to_postgres/TransferLLM/1.jsonl | jq 'select(.sql | contains("INSERT INTO t1")) | {original: .sql, translated: .TransferResult[0]}'

# 验证数据值是否保持一致
```

## 🎯 预期效果

修复后，翻译应该：
- ✅ 保留所有NULL值
- ✅ 保留所有空字符串
- ✅ 保留所有零值
- ✅ 不改变表名/列名
- ✅ 不搞混数据值的位置
- ✅ 只移除非确定性函数（CURRENT_TIMESTAMP等）

## 📚 相关文档

- `src/TransferLLM/TransferLLM.py:1240` - 需要修改的prompt位置
- `src/TransferLLM/mem0_adapter.py` - mem0记忆管理
- `Output/bugs_*/SuspiciousBugs/` - 可疑bug报告

## 🔗 相关Issue

这个问题影响所有使用该prompt的翻译任务：
- MySQL → MariaDB
- DuckDB → PostgreSQL
- PostgreSQL → DuckDB
- 所有SQL到SQL的翻译

## ✅ 检查清单

修复完成后，检查：
- [ ] Prompt已修改，明确要求保留所有数据值
- [ ] 测试用例通过，无数据被改变
- [ ] mem0中的错误记忆已清理
- [ ] 添加了翻译验证逻辑（可选）
- [ ] 文档已更新

## 💡 经验教训

1. **Prompt设计要精确无歧义**：避免使用"meaningless"这种主观词汇
2. **明确区分"数据"和"函数"**：数据要保留，非确定性函数要移除
3. **mem0需要质量控制**：错误的记忆会被LLM学习，形成恶性循环
4. **需要翻译验证机制**：自动检查翻译是否忠实

## 🎓 总结

**问题根源**：Prompt第1240行的"Strictly forbid meaningless features(such as NULL,0)"指令有歧义

**直接影响**：LLM误删除NULL、空字符串、零值等数据

**间接影响**：mem0记录了错误翻译，形成恶性循环

**解决方案**：修改prompt，明确要求保留所有数据值，只移除非确定性函数

