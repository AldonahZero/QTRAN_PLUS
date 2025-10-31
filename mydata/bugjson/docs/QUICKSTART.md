# 🚀 快速开始 - 数据库Bug爬虫

## 📦 已创建的文件

```
mydata/bugjson/
├── bugs.json                  # 主数据文件 (当前699个bug)
├── bugs.json.backup          # 自动备份
├── advanced_crawler.py       # ⭐ 增强版爬虫（推荐）
├── bug_crawler.py            # 基础版爬虫
├── crawler_config.py         # 配置模板
├── stats.py                  # 统计分析工具
├── README.md                 # 详细文档
└── QUICKSTART.md            # 本文件
```

---

## ⚡ 3步快速使用

### 1️⃣ 基础爬取（无需配置）

```bash
cd /root/QTRAN/mydata/bugjson
python advanced_crawler.py
```

**限制**: 每小时60个请求（GitHub限制）

### 2️⃣ 高速爬取（推荐）

**步骤1 - 获取GitHub Token:**
- 访问: https://github.com/settings/tokens
- 生成新token (classic)
- 权限: 勾选 `public_repo`
- 复制token (类似: `ghp_xxxxxxxxxxxx`)

**步骤2 - 创建配置:**
```bash
cat > crawler_config_local.py << 'EOF'
GITHUB_TOKEN = "ghp_你的token粘贴到这里"
EOF
```

**步骤3 - 运行:**
```bash
python advanced_crawler.py
```

**好处**: 每小时5000个请求！

### 3️⃣ 查看统计

```bash
python stats.py
```

---

## 📊 当前数据集状态

```
总bug数: 699个
数据库分布:
  ✅ ClickHouse:  200个 (28.6%)
  ✅ SQLite:      193个 (27.6%)
  ✅ DuckDB:       75个 (10.7%)
  ✅ CockroachDB:  68个 (9.7%)
  ✅ TiDB:         62个 (8.9%)
  ✅ 其他:        101个

时间范围: 2019-05 ~ 2025-07
```

---

## 🎯 支持的数据源

### ✅ 已实现

| 数据库 | 来源 | 命令 |
|--------|------|------|
| **DuckDB** | GitHub | `python advanced_crawler.py` |
| **ClickHouse** | GitHub | `python advanced_crawler.py` |
| **PostgreSQL** | GitHub | `python advanced_crawler.py` |

### 🔧 自定义爬取

编辑 `advanced_crawler.py` 的 `main()` 函数：

```python
# 只爬取DuckDB
duckdb_count = crawler.crawl_repo(
    repo="duckdb/duckdb",
    dbms_name="DuckDB",
    max_issues=500,           # 增加数量
    since_date="2020-01-01",  # 修改起始日期
    labels=["bug", "crash"]   # 只爬取crash类bug
)
```

---

## 💡 常见任务

### 爬取最新的100个DuckDB bug

```python
from advanced_crawler import GitHubIssueCrawler

crawler = GitHubIssueCrawler(github_token="your_token")
crawler.crawl_repo("duckdb/duckdb", "DuckDB", max_issues=100)
crawler.save_bugs()
```

### 只爬取crash类型的bug

```python
crawler.crawl_repo(
    repo="duckdb/duckdb",
    dbms_name="DuckDB",
    labels=["bug", "crash"]  # 只要crash
)
```

### 爬取所有2024年以后的bug

```python
crawler.crawl_repo(
    repo="duckdb/duckdb",
    dbms_name="DuckDB",
    since_date="2024-01-01"
)
```

---

## 🐛 故障排查

### ❌ 403 API限流

**症状:**
```
⏰ API限流，等待 3600秒...
```

**解决:**
1. 等待1小时
2. 或设置GitHub Token (提升到5000请求/小时)

### ❌ 爬取到0个bug

**原因:**
- `since_date` 设置过晚
- 所有bug都已存在（去重）

**解决:**
```python
# 改早一点的日期
since_date="2020-01-01"
```

### ❌ requests模块不存在

```bash
pip install requests
```

---

## 📈 爬虫特性

### ✅ 智能功能
- **自动去重**: 检查已有链接，避免重复
- **自动备份**: 每次保存前备份原文件
- **智能提取**: 从issue中提取SQL代码
- **Oracle分类**: 自动判断crash/error/PQS
- **限流处理**: 自动等待API限流恢复
- **断点续爬**: 支持中断后继续

### 📋 数据格式

每个bug包含：
```json
{
    "date": "31/10/2025",
    "dbms": "ClickHouse",
    "links": {
        "bugreport": "https://github.com/..."
    },
    "oracle": "crash",
    "reporter": "username",
    "status": "open",
    "title": "Bug标题",
    "test": ["SQL语句1", "SQL语句2"],
    "comment": "简短说明"
}
```

---

## 🎓 进阶使用

### 添加新数据库

1. 编辑 `advanced_crawler.py`
2. 在 `main()` 中添加：

```python
# MySQL (如果有GitHub镜像)
mysql_count = crawler.crawl_repo(
    repo="mysql/mysql-server",
    dbms_name="MySQL",
    max_issues=100
)
```

### 过滤特定标签

```python
labels=["bug", "severity:critical"]
```

### 修改爬取数量

```python
max_issues=1000  # 默认200
```

---

## 📞 需要帮助？

查看详细文档: `cat README.md`

---

**最后更新**: 2025-10-31
**当前版本**: v1.0

