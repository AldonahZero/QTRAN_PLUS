# DuckDB 数据添加记录

## 📅 更新时间
2025-10-29

## 📊 数据来源
- **日志目录**: `/root/sqlancer/logs/duckdb/`
- **日志文件数量**: 87 个
- **有效日志**: 34 个
- **生成测试用例**: 68 条

## 🎯 配置规则

根据 `Input/demo1.jsonl` 中的配置，DuckDB 作为源数据库时：

| b_db (目标数据库) | molt (测试策略) |
|------------------|----------------|
| mariadb | tlp (aggregate max) |
| postgres | tlp (where) |

每个有效的 DuckDB 日志文件会生成 **2 个测试用例**（对应上述两种配置）。

## 📋 筛选条件

脚本 `scripts/add_duckdb_data.py` 使用以下条件筛选有效测试用例：

1. ✅ 至少包含 1 条 `CREATE TABLE` 语句
2. ✅ 至少包含 1 条 `SELECT` 语句
3. ✅ SQL 总数在 3-20 条之间
4. ❌ 跳过注释行和空行

## 📈 统计数据

### 更新前
- **总测试用例**: 25 条
  - sqlite → duckdb/monetdb/tidb: 15 条
  - mysql → mariadb: 10 条

### 更新后
- **总测试用例**: 93 条 (+68)

### 数据库分布

**a_db (源数据库)**:
- duckdb: **68 条** 🆕
- sqlite: 15 条
- mysql: 10 条

**b_db (目标数据库)**:
- mariadb: 44 条 (+34)
- postgres: 34 条 (+34)
- duckdb: 5 条
- monetdb: 5 条
- tidb: 5 条

## 📝 测试用例示例

### 示例 1: DuckDB → MariaDB
```json
{
  "index": 26,
  "a_db": "duckdb",
  "b_db": "mariadb",
  "molt": "tlp (aggregate max)",
  "sqls": [
    "CREATE TABLE t0(c0 TIMESTAMP, PRIMARY KEY(c0));",
    "CREATE TABLE t1(c0 DATE NOT NULL, c1 VARCHAR NOT NULL DEFAULT(-0.0), ...);",
    "ANALYZE;",
    "INSERT INTO t0(c0) VALUES (DATE '1970-01-24'), (DATE '1970-01-19');",
    "INSERT INTO t1(c1, c0) VALUES (')', '1970-01-17'), (...);",
    ...
  ]
}
```

### 示例 2: DuckDB → PostgreSQL
```json
{
  "index": 27,
  "a_db": "duckdb",
  "b_db": "postgres",
  "molt": "tlp (where)",
  "sqls": [
    "CREATE TABLE t0(c0 TIMESTAMP, PRIMARY KEY(c0));",
    "CREATE TABLE t1(c0 DATE NOT NULL, c1 VARCHAR NOT NULL DEFAULT(-0.0), ...);",
    "ANALYZE;",
    ...
  ]
}
```

## 🔧 使用方法

### 运行完整测试集
```bash
cd /root/QTRAN
./run.sh Input/bugs_all_combined.jsonl
```

### 只测试 DuckDB 案例
```bash
# 提取 DuckDB 测试用例
python3 -c "
import json
with open('Input/bugs_all_combined.jsonl', 'r') as f:
    data = [json.loads(line) for line in f if line.strip()]

duckdb_cases = [d for d in data if d['a_db'] == 'duckdb']

with open('Input/duckdb_only.jsonl', 'w') as f:
    for case in duckdb_cases:
        f.write(json.dumps(case) + '\n')

print(f'✅ 已提取 {len(duckdb_cases)} 条 DuckDB 测试用例到 Input/duckdb_only.jsonl')
"

# 运行测试
./run.sh Input/duckdb_only.jsonl
```

## 📂 相关文件

- **输出文件**: `Input/bugs_all_combined.jsonl`
- **生成脚本**: `scripts/add_duckdb_data.py`
- **参考配置**: `Input/demo1.jsonl`
- **日志来源**: `/root/sqlancer/logs/duckdb/`

## ✅ 验证

```bash
# 验证文件行数
wc -l Input/bugs_all_combined.jsonl
# 预期: 93

# 验证 JSON 格式
python3 -c "
import json
with open('Input/bugs_all_combined.jsonl', 'r') as f:
    data = [json.loads(line) for line in f if line.strip()]
print(f'✅ 所有 {len(data)} 条数据格式正确')
"
```

---

**生成工具**: `scripts/add_duckdb_data.py`  
**更新时间**: 2025-10-29  
**状态**: ✅ 完成

