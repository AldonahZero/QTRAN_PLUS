# 数据库Bug爬虫

自动爬取和更新数据库bug信息，扩展 `bugs.json` 数据集。

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `bugs.json` | 主数据文件（8943个bug，截止2020/09/24） |
| `advanced_crawler.py` | 🌟 增强版爬虫（推荐使用） |
| `bug_crawler.py` | 基础版爬虫 |
| `crawler_config.py` | 配置模板 |
| `crawler_config_local.py` | 本地配置（需自行创建） |

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install requests
```

### 2. 运行爬虫

```bash
# 基础模式（无GitHub Token，60请求/小时）
python advanced_crawler.py

# 高级模式（配置GitHub Token后，5000请求/小时）
# 1) 创建配置文件
cp crawler_config.py crawler_config_local.py

# 2) 编辑配置，添加你的GitHub Token
vim crawler_config_local.py

# 3) 运行
python advanced_crawler.py
```

### 3. 查看结果

```bash
# 查看新增的bug
tail -n 50 bugs.json

# 统计
python -c "import json; data=json.load(open('bugs.json')); print(f'总bug数: {len(data)}')"
```

---

## 🔑 获取GitHub Token

**为什么需要？**
- 无Token: 60请求/小时
- 有Token: 5000请求/小时

**获取步骤：**

1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token" → "Generate new token (classic)"
3. 设置：
   - Note: `QTRAN Bug Crawler`
   - Expiration: `90 days`
   - Scopes: 勾选 `public_repo`
4. 点击 "Generate token"
5. **复制token** (只显示一次！)
6. 粘贴到 `crawler_config_local.py`:

```python
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"
```

---

## 📊 支持的数据源

### ✅ 已实现

| 数据库 | 来源 | 说明 |
|--------|------|------|
| **DuckDB** | GitHub Issues | ✅ 完全支持 |
| **ClickHouse** | GitHub Issues | ✅ 完全支持 |
| **PostgreSQL** | GitHub 镜像 | ✅ 部分支持 |

### 🚧 计划中

| 数据库 | 来源 | 难度 |
|--------|------|------|
| SQLite | https://www.sqlite.org/src/timeline | 🔴 需解析HTML |
| MySQL | https://bugs.mysql.com/ | 🟡 需Bugzilla API |
| MongoDB | https://jira.mongodb.org/ | 🟡 需Jira API |
| MariaDB | https://jira.mariadb.org/ | 🟡 需Jira API |

---

## 📈 爬虫特性

### advanced_crawler.py (推荐)

✅ **功能强大**
- 支持GitHub Token认证
- 自动去重（检查已有链接）
- 自动备份原文件
- 智能提取SQL代码
- 确定Oracle类型（crash/error/PQS）
- 支持多数据源并发爬取

✅ **智能解析**
- 从Markdown代码块提取SQL
- 从issue body提取测试用例
- 自动判断bug状态（open/fixed/closed）
- 提取reporter和日期信息

✅ **安全可靠**
- 自动限流处理
- 请求失败重试
- 数据备份机制
- 详细的日志输出

---

## 🎯 使用示例

### 示例1: 爬取DuckDB最新100个bug

```python
from advanced_crawler import GitHubIssueCrawler

crawler = GitHubIssueCrawler(github_token="your_token")
crawler.crawl_repo(
    repo="duckdb/duckdb",
    dbms_name="DuckDB",
    max_issues=100,
    since_date="2020-09-25",
    labels=["bug"]
)
crawler.save_bugs()
```

### 示例2: 只爬取crash类型的bug

修改 `advanced_crawler.py` 中的参数：

```python
labels=["bug", "crash"]
```

### 示例3: 爬取所有未关闭的bug

```python
# 在crawl_repo方法中添加state过滤
params['state'] = 'open'
```

---

## 📋 数据格式

每个bug记录包含以下字段：

```json
{
    "date": "24/09/2020",
    "dbms": "DuckDB",
    "links": {
        "bugreport": "https://github.com/..."
    },
    "oracle": "crash",
    "reporter": "username",
    "status": "fixed",
    "title": "Buffer overflow in ...",
    "test": [
        "CREATE TABLE t0(...);",
        "INSERT INTO t0 VALUES(...);",
        "SELECT * FROM t0 WHERE ..."
    ],
    "comment": "Brief description...",
    "severity": "High"  // 可选
}
```

### Oracle类型说明

| Type | 说明 | 示例关键词 |
|------|------|------------|
| `crash` | 程序崩溃 | segfault, assertion, panic |
| `error` | 错误/异常 | error, exception, fails |
| `PQS` | 结果错误 | wrong result, expected, actual |
| `unknown` | 未知类型 | - |

---

## ⚠️ 注意事项

### API限流

**GitHub API限制：**
- 未认证: 60请求/小时
- 认证: 5000请求/小时

**触发限流时：**
```
⏰ API限流，等待 3600秒...
```

**解决方案：**
1. 等待1小时
2. 使用GitHub Token
3. 分批次运行

### 数据质量

**自动过滤：**
- ✅ 跳过Pull Request
- ✅ 跳过无bug标签的issue
- ✅ 去重已存在的bug

**需要手动检查：**
- ⚠️ SQL提取可能不完整
- ⚠️ Oracle类型可能判断不准
- ⚠️ 部分issue可能是功能请求而非bug

---

## 📊 统计信息

### 当前数据集 (bugs.json)

```
总bug数: 8943
来源分布:
  - SQLite: ~8000+
  - DuckDB: ~100
  - 其他: ~800
  
时间范围: 2019-2020
主要Reporter: Manuel Rigger
```

### 爬取后预期

```
预计新增: 500-1000个bug
新数据库: ClickHouse, PostgreSQL
时间范围: 2020-2025
```

---

## 🔧 故障排查

### 问题1: ModuleNotFoundError: No module named 'requests'

```bash
pip install requests
```

### 问题2: GitHub API 403 Forbidden

**原因**: 超过API限额

**解决**:
1. 等待限流重置（每小时重置）
2. 添加GitHub Token

### 问题3: 爬取到的bug数量为0

**可能原因**:
1. `since_date` 设置过晚
2. 标签过滤太严格
3. 所有bug都已存在

**解决**:
```python
# 调整since_date
since_date="2020-01-01"  # 更早的日期

# 放宽标签过滤
labels=[]  # 不过滤标签
```

### 问题4: 无法解析某些issue

**正常现象**: 不是所有issue都包含SQL代码

**改进**: 手动添加特殊格式的bug

---

## 🎯 最佳实践

### 1. 增量爬取

```python
# 设置since_date为bugs.json中最新的日期
since_date="2020-09-25"  # 上次爬取的日期
```

### 2. 分批运行

```python
# 每次爬取100个，避免超时
max_issues=100
```

### 3. 定期备份

```python
# 爬虫会自动备份
# 手动备份：
cp bugs.json bugs.json.backup.$(date +%Y%m%d)
```

### 4. 质量检查

```bash
# 检查最后10个bug
python -c "import json; bugs=json.load(open('bugs.json')); \
    for b in bugs[-10:]: print(f'{b[\"date\"]} - {b[\"dbms\"]} - {b[\"title\"]}')"
```

---

## 📝 贡献指南

欢迎添加新的数据源！

### 添加新数据库步骤：

1. 在 `advanced_crawler.py` 中添加爬取逻辑
2. 实现 `parse_xxx_issue` 方法
3. 测试并验证数据格式
4. 更新本README

### 代码规范：

- 遵循PEP 8
- 添加类型注解
- 编写详细的docstring
- 处理异常情况

---

## 📞 联系方式

- Issues: 在GitHub仓库提issue
- Email: 项目维护者邮箱

---

## 📜 许可证

MIT License

---

**最后更新**: 2025-10-31
**维护者**: QTRAN Team

