# 从 SQLancer 日志生成的测试数据（合并版）

## 📊 合并文件统计

**文件名**: `bugs_all_combined.jsonl`  
**总计**: **25 条测试用例**

### 数据分布

| 序号范围 | 源数据库 | 目标数据库 | MOLT策略 | 数量 |
|---------|---------|-----------|---------|------|
| 1-5 | sqlite | duckdb | norec | 5 |
| 6-10 | sqlite | monetdb | norec | 5 |
| 11-15 | sqlite | tidb | norec | 5 |
| 16-25 | mysql | mariadb | tlp (where) | 10 |

---

## 📝 数据格式

每个测试用例都遵循以下格式：

```json
{
  "index": 1,
  "a_db": "sqlite",
  "b_db": "duckdb",
  "molt": "norec",
  "sqls": [
    "CREATE TABLE t1 (c0 INT COLLATE BINARY)",
    "INSERT OR IGNORE INTO sqlite_stat1 VALUES(...)",
    "SELECT rtreecheck('rt0')"
  ]
}
```

---

## 🚀 使用方法

### 运行测试
```bash
cd /root/QTRAN
python run.py \
    --input Input/bugs_all_combined.jsonl \
    --output Output/bugs_all_combined \
    --mode full
```

---

## ⚠️ 注意事项

### SQLite 特有语法
生成的 SQLite 测试用例包含一些特有语法：
- `INSERT OR IGNORE/REPLACE/ABORT`
- `sqlite_stat1` 统计表
- `rtreecheck()` R-tree 检查函数
- `COLLATE BINARY/NOCASE`
- 虚拟表操作

这些在翻译到其他数据库时需要特别处理。

### MySQL 特有语法
MySQL 测试用例包含：
- `INSERT DELAYED/HIGH_PRIORITY/LOW_PRIORITY`
- `STORAGE MEMORY/DISK`
- `ZEROFILL`
- `COMMENT 'asdf'`
- `information_schema` 查询

---

## 📊 数据来源

- **原始日志**: `/root/sqlancer/logs/`
- **转换脚本**: `/root/QTRAN/scripts/convert_sqlancer_logs_to_qtran.py`
- **批量脚本**: `/root/QTRAN/scripts/batch_convert_logs.py`
- **生成时间**: 2025-10-28
- **合并时间**: 2025-10-28

---

## 🔍 测试覆盖

### SQLite 测试 (15 条)
- ✅ SQLite → DuckDB (5 条)
- ✅ SQLite → MonetDB (5 条)
- ✅ SQLite → TiDB (5 条)

测试内容：
- R-tree 索引功能
- 统计信息管理
- 虚拟表操作
- 复杂索引表达式
- 冲突处理策略

### MySQL 测试 (10 条)
- ✅ MySQL → MariaDB (10 条)

测试内容：
- 存储引擎选项
- 索引类型和算法
- 数据类型兼容性
- 延迟插入
- 表选项和约束

---

## 🎯 数据质量

- ✅ **格式统一**: 所有数据遵循 demo1.jsonl 格式
- ✅ **编号连续**: index 从 1 到 25 连续编号
- ✅ **映射正确**: a_db 和 b_db 按照要求映射
- ✅ **MOLT 匹配**: 每个数据库对使用正确的测试策略

---

**生成日期**: 2025-10-28  
**数据版本**: v1.1 (合并版)  
**状态**: ✅ 可用
