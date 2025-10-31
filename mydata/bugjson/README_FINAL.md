# 数据库Bug数据集 - 最终版本

## 📦 文件说明

### 数据文件

| 文件 | 说明 | Bug数 | 时间范围 |
|------|------|-------|----------|
| `bugs.json` | 原始数据集 | 499个 | 2019-2020 |
| `bugs_new.json` ⭐ | **完整数据集（推荐）** | 849个 | 2019-2025 |

### 核心代码

| 文件 | 说明 |
|------|------|
| `multi_source_crawler.py` ⭐ | **最强爬虫** - 多源架构，支持6种数据源 |
| `demo.py` | 演示脚本 - 快速测试爬虫 |
| `bugs.py` | 原始工具脚本 - 数据验证和导出 |

### 工具脚本

| 文件 | 说明 |
|------|------|
| `stats.py` | 统计分析工具 |
| `clean_bugs.py` | 数据清理工具 |
| `merge_multi_db.py` | 数据合并工具 |
| `crawler_config.py` | 爬虫配置文件 |

---

## 🚀 快速使用

### 1. 查看数据统计

```bash
python stats.py bugs_new.json
```

### 2. 运行演示

```bash
python demo.py
```

### 3. 爬取最新bugs

```bash
# 推荐：设置GitHub Token后运行
python multi_source_crawler.py
```

---

## 📊 bugs_new.json 数据集详情

**总bug数**: 849个

**包含的数据库**:
- ✅ SQLite: 193个 (2019-2020)
- ✅ DuckDB: 175个 (2020-2025) 🆕
- ✅ MySQL: 40个 (2019-2020)
- ✅ PostgreSQL: 31个 (2019)
- ✅ MonetDB: 100个 (2025) 🆕
- ✅ MariaDB: 57个 (2019-2025) 🆕
- ✅ ClickHouse: 100个 (2025) 🆕
- ✅ 其他: 153个

**特点**:
- ✅ 包含2025年10月最新bugs
- ✅ 每个bug包含SQL测试用例
- ✅ Oracle类型标注（crash/error/PQS等）
- ✅ 官方链接可追溯

---

## 🏗️ multi_source_crawler.py 架构

最强的多源爬虫，支持不同数据库使用不同的爬取方法：

### 支持的数据源

1. **SQLiteBugCrawler** - SQLite官方Bug Tracker (HTML解析)
2. **DuckDBGitHubCrawler** - GitHub Issues (智能过滤)
3. **MySQLBugzillaCrawler** - MySQL Bugzilla API
4. **PostgreSQLMailingListCrawler** - PostgreSQL邮件列表
5. **MariaDBJiraCrawler** - MariaDB Jira API
6. **GitHub通用爬虫** - MonetDB/ClickHouse等

### 特点

- ✅ 面向对象设计（BaseBugCrawler基类）
- ✅ 自动去重
- ✅ 智能SQL提取
- ✅ 支持扩展新数据库

---

## 💡 配置GitHub Token

获得5000请求/小时的限额：

1. 访问: https://github.com/settings/tokens
2. 生成token (勾选`public_repo`权限)
3. 编辑`crawler_config.py`:
   ```python
   GITHUB_TOKEN = "ghp_你的token"
   ```

---

## 📖 详细文档

- `README.md` - 技术文档
- `QUICKSTART.md` - 快速开始
- `使用指南.md` - 完整教程
- `多数据库爬取说明.md` - 多源爬虫说明

---

## 🎯 常用命令

```bash
# 查看统计
python stats.py bugs_new.json

# 爬取新bugs
python multi_source_crawler.py

# 清理数据
python clean_bugs.py bugs_new.json

# 合并数据
python merge_multi_db.py bugs.json bugs_new.json bugs_merged.json
```

---

**最后更新**: 2025-10-31  
**总bug数**: 849个  
**时间范围**: 2019-2025

