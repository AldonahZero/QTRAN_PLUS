# Bug数据集与爬虫系统

## 📂 目录结构

```
/root/QTRAN/mydata/bugjson/
├── data/           # 数据文件
├── backup/         # 备份文件
├── scripts/        # 工具脚本
├── crawler/        # 爬虫系统
└── docs/           # 文档
```

## 🚀 快速使用

### 1. 查看数据
```bash
cd scripts
python3 stats.py ../data/bugs_new.json
```

### 2. 运行爬虫
```bash
cd crawler
./manage_crawler_service.sh run
```

### 3. 合并新数据
```bash
cd scripts
python3 merge_multi_db.py
```

## 📖 详细文档

请查看 `docs/` 目录中的文档：
- `README_FINAL.md` - 最终说明
- `SERVICE_README.md` - 服务文档
- `QUICKSTART.md` - 快速开始

## 📊 数据文件

主数据文件: `data/bugs_new.json` (850个bugs, 2019-2025)

包含数据库:
- SQLite: 193个
- DuckDB: 175个
- MySQL: 40个
- PostgreSQL: 31个
- MonetDB: 100个
- MariaDB: 58个

## 🤖 自动爬虫服务

爬虫已配置为系统服务，每天凌晨2点自动运行。

管理命令:
```bash
cd crawler
./manage_crawler_service.sh status    # 查看状态
./manage_crawler_service.sh run       # 立即运行
./manage_crawler_service.sh logs      # 查看日志
```

---
最后更新: 2025-10-31
