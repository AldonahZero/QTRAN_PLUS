# Docker 容器管理指南

## 快速开始

### 启动所有数据库容器
```bash
./docker-start.sh
```

### 停止所有数据库容器
```bash
./docker-stop.sh
```

## 重要说明

### 容器命名规则
为了确保容器名称与配置文件（`database_connector_args.json`）保持一致，我们使用以下启动方式：

```bash
docker compose --project-name "" -f docker-compose.yml up -d
```

**关键点：**
- `--project-name ""`：设置空的项目名，防止Docker自动添加前缀
- 容器名称将完全按照 `docker-compose.yml` 中的 `container_name` 设置
- 例如：`mariadb_QTRAN` 而不是 `xxx_mariadb_QTRAN`

### 容器列表
启动后的容器名称：
- `mariadb_QTRAN` - MariaDB 11.5.2
- `mysql_QTRAN` - MySQL 8.0.39
- `postgres_QTRAN` - PostgreSQL 16.3
- `monetdb_QTRAN` - MonetDB
- `clickhouse_QTRAN` - ClickHouse 24.9.2
- `mongodb_QTRAN` - MongoDB 7.0
- `redis_QTRAN` - Redis 7.2
- `memcached_QTRAN` - Memcached 1.6
- `etcd_QTRAN` - etcd v3.5.14
- `consul_QTRAN` - Consul 1.19
- `qdrant_QTRAN` - Qdrant v1.11.3
- `surrealdb_QTRAN` - SurrealDB

## 常用命令

### 查看运行中的容器
```bash
docker ps | grep QTRAN
```

### 查看容器日志
```bash
docker logs mariadb_QTRAN
docker logs -f mysql_QTRAN  # 实时查看
```

### 重启单个容器
```bash
docker restart mariadb_QTRAN
```

### 进入容器Shell
```bash
docker exec -it mariadb_QTRAN bash
docker exec -it postgres_QTRAN psql -U postgres
```

### 完全清理（包括数据卷）
```bash
docker compose --project-name "" down -v
```

## 故障排查

### 如果容器名称带有前缀
如果发现容器名称类似 `xxx_mariadb_QTRAN`（带随机前缀），说明启动方式不对。

**解决方法：**
1. 停止现有容器：`./docker-stop.sh`
2. 删除容器：`docker rm $(docker ps -a | grep QTRAN | awk '{print $1}')`
3. 重新启动：`./docker-start.sh`

### 如果容器已存在但名称不对
```bash
# 重命名容器
docker rename xxx_mariadb_QTRAN mariadb_QTRAN
```

## 端口映射

| 服务 | 容器端口 | 宿主机端口 |
|------|---------|-----------|
| MariaDB | 3306 | 9901 |
| MySQL | 3306 | 13306 |
| PostgreSQL | 5432 | 5432 |
| MonetDB | 50000 | 50000 |
| ClickHouse HTTP | 8123 | 8123 |
| ClickHouse Native | 9000 | 9000 |
| MongoDB | 27017 | 27017 |
| Redis | 6379 | 6379 |
| Memcached | 11211 | 11211 |
| etcd | 2379 | 12379 |
| Consul HTTP | 8500 | 18500 |
| Consul DNS | 8600 | 18600 |
| Qdrant | 6333 | 6333 |
| SurrealDB | 8000 | 8000 |

