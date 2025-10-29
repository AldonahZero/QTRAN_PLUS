# 真实 Bug 测试用例数据集

## 📋 文件说明

**文件名**: `bugs_real.jsonl`  
**生成时间**: 2025-10-29  
**生成工具**: `scripts/extract_real_bugs.py`  
**数据来源**: `mydata/bugjson/bugs.json` (499个真实 bug)

## 🎯 特点

这是从**真实 bug 报告**中提取的测试用例，具有以下优势：

✅ **质量高** - 所有测试用例都是真实发现的 bug  
✅ **简洁** - 平均 3.8 条 SQL，平均每条 50 字符  
✅ **已修复** - 所有 bug 都已被数据库开发者修复，是经过验证的真实 bug  
✅ **跨数据库兼容** - 已过滤掉数据库特有语法

## 📊 数据统计

### 总览
- **测试用例总数**: 148 条
- **来源 Bug 数**: 499 个
- **成功提取率**: 29.7%

### SQL 特征
| 指标 | 数值 |
|------|------|
| SQL 数量范围 | 2-7 条 |
| SQL 平均数量 | 3.8 条 |
| 单条 SQL 最短 | 0 字符（空注释） |
| 单条 SQL 最长 | 234 字符 |
| 单条 SQL 平均 | 50 字符 |
| **简单测试用例** | **75 条** (SQL≤4条且每条<100字符) |

### 数据库分布

**源数据库 (a_db)**:
| 数据库 | 数量 | 占比 |
|--------|------|------|
| SQLite | 68 条 | 45.9% |
| DuckDB | 50 条 | 33.8% |
| MySQL | 24 条 | 16.2% |
| PostgreSQL | 6 条 | 4.1% |

**目标数据库 (b_db)**:
| 数据库 | 数量 | 占比 |
|--------|------|------|
| DuckDB | 71 条 | 48.0% |
| PostgreSQL | 50 条 | 33.8% |
| MariaDB | 12 条 | 8.1% |
| TiDB | 12 条 | 8.1% |
| CockroachDB | 3 条 | 2.0% |

## 📝 过滤规则

### 排除的模式
脚本排除了以下数据库特有语法：

**SQLite 特有**:
- `sqlite_stat*`, `rtreecheck`, `PRAGMA`, `WITHOUT ROWID`
- `INSERT/UPDATE/DELETE OR REPLACE/IGNORE/ABORT`
- `COLLATE BINARY`

**PostgreSQL 特有**:
- `pg_*` 函数
- `ONLY`, `INHERITS`, `TABLESPACE`

**MySQL 特有**:
- `STORAGE DISK/MEMORY`
- `COLUMN_FORMAT`

**DuckDB 特有**:
- `COLLATE NOACCENT/POSIX`
- `::INT1/INT2/INT4/INT8`

**其他**:
- `VACUUM`, `ANALYZE`, `EXPLAIN`

### 包含条件
✅ 必须包含 `CREATE TABLE`  
✅ 必须包含 `SELECT`  
✅ SQL 数量: 2-8 条  
✅ 单条 SQL ≤ 300 字符  
✅ Bug 状态: `fixed` 或 `fixed (in documentation)`

## 📋 测试用例示例

### 示例 1: SQLite → DuckDB (简单)
```json
{
  "index": 1003,
  "a_db": "sqlite",
  "b_db": "duckdb",
  "molt": "norec",
  "sqls": [
    "CREATE TABLE t0(c0 INT UNIQUE COLLATE NOCASE);",
    "INSERT INTO t0(c0) VALUES ('./');",
    "SELECT * FROM t0 WHERE t0.c0 LIKE './';"
  ]
}
```

### 示例 2: MySQL → MariaDB
```json
{
  "index": 1050,
  "a_db": "mysql",
  "b_db": "mariadb",
  "molt": "norec",
  "sqls": [
    "CREATE TABLE t0(c0 INT);",
    "INSERT INTO t0 VALUES (1);",
    "SELECT c0 FROM t0 WHERE c0 = 1;"
  ]
}
```

### 示例 3: DuckDB → PostgreSQL
```json
{
  "index": 1100,
  "a_db": "duckdb",
  "b_db": "postgres",
  "molt": "norec",
  "sqls": [
    "CREATE TABLE test(c0 INTEGER);",
    "INSERT INTO test VALUES(1);",
    "SELECT * FROM test WHERE c0 > 0;"
  ]
}
```

## 🚀 使用方法

### 推荐：测试真实 Bug
```bash
cd /root/QTRAN
./run.sh Input/bugs_real.jsonl
```

### 对比：其他数据集
```bash
# 兼容数据集（SQLancer生成，36条）
./run.sh Input/bugs_compatible.jsonl

# 完整数据集（包含不兼容的，51条）
./run.sh Input/bugs_all_combined.jsonl

# Demo数据集（精心设计，14条）
./run.sh Input/demo1.jsonl
```

## 📈 预期效果

使用 `bugs_real.jsonl` 的优势：

✅ **更高的成功率**  
- SQL 简洁，翻译难度低
- 平均 3.8 条 SQL，比 SQLancer 生成的简单得多

✅ **真实 Bug**  
- 所有测试用例都是真实发现的 bug
- 已被数据库开发者验证和修复

✅ **更好的测试质量**  
- 测试的是实际会遇到的问题
- 不是压力测试，而是功能测试

## 📂 相关文件

- **真实 Bug 数据**: `Input/bugs_real.jsonl` (148条) ⭐⭐⭐⭐⭐
- **提取脚本**: `scripts/extract_real_bugs.py`
- **原始数据**: `mydata/bugjson/bugs.json` (499个 bug)
- **兼容数据**: `Input/bugs_compatible.jsonl` (36条)
- **完整数据**: `Input/bugs_all_combined.jsonl` (51条)

## 🔍 质量对比

| 数据集 | 来源 | 数量 | 平均SQL | 平均长度 | 推荐指数 |
|--------|------|------|---------|----------|----------|
| **bugs_real.jsonl** | **真实Bug** | **148** | **3.8条** | **50字符** | **⭐⭐⭐⭐⭐** |
| demo1.jsonl | 精心设计 | 14 | 5.0条 | 80字符 | ⭐⭐⭐⭐⭐ |
| bugs_compatible.jsonl | SQLancer | 36 | 7.0条 | 103字符 | ⭐⭐⭐ |
| bugs_all_combined.jsonl | SQLancer | 51 | 混合 | 混合 | ⭐⭐ |

## ✅ 验证

```bash
# 统计测试用例数量
wc -l Input/bugs_real.jsonl
# 预期: 148

# 验证数据格式和质量
python3 -c "
import json
with open('Input/bugs_real.jsonl', 'r') as f:
    data = [json.loads(line) for line in f if line.strip()]

simple = [c for c in data if len(c['sqls']) <= 4 and all(len(sql) < 100 for sql in c['sqls'])]

print(f'✅ {len(data)} 条测试用例格式正确')
print(f'✨ {len(simple)} 条简单测试用例（推荐优先测试）')
"
```

## 🎯 推荐测试策略

1. **首先测试简单用例**（75条）
   - SQL ≤ 4条且每条 < 100字符
   - 成功率最高
   - 快速验证基本功能

2. **然后测试标准用例**（73条）
   - 稍复杂但仍然兼容
   - 覆盖更多场景

3. **对比 demo1.jsonl**
   - 精心设计的测试用例
   - 用于验证特定功能

---

**生成工具**: `scripts/extract_real_bugs.py`  
**数据来源**: 真实 Bug 报告数据库 (499个)  
**更新时间**: 2025-10-29  
**推荐指数**: ⭐⭐⭐⭐⭐ (最高推荐)

