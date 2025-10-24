# Qdrant 向量数据库设置指南

## 📋 概述

Qdrant 是 QTRAN Mem0 集成的核心组件，用于存储和检索翻译记忆的向量表示。

### 为什么需要 Qdrant？

- **语义搜索**: 根据 SQL 语义相似度（而非文本匹配）检索历史案例
- **高性能**: 专门优化的向量近邻搜索算法
- **持久化**: 数据永久保存，重启不丢失

---

## 🚀 快速启动

### 方式 1: 使用提供的脚本（推荐）

```bash
# 启动 Qdrant
./docker_start_qdrant.sh

# 停止 Qdrant
./docker_stop_qdrant.sh
```

### 方式 2: 使用 Docker Compose

```bash
# 仅启动 Qdrant
docker-compose up -d qdrant

# 查看状态
docker-compose ps qdrant

# 查看日志
docker-compose logs -f qdrant

# 停止
docker-compose stop qdrant
```

### 方式 3: 启动所有数据库（包括 Qdrant）

```bash
# 启动所有服务
docker-compose up -d

# 停止所有服务
docker-compose down
```

---

## ✅ 验证安装

### 1. 检查容器状态

```bash
docker ps | grep qdrant
```

预期输出：
```
qdrant_QTRAN   qdrant/qdrant:v1.11.3   Up 2 minutes   0.0.0.0:6333->6333/tcp
```

### 2. 检查健康状态

```bash
curl http://localhost:6333/health
```

预期输出：
```json
{"title":"healthz","version":"1.11.3"}
```

### 3. 访问 Web UI

在浏览器中打开：http://localhost:6333/dashboard

---

## 🔧 配置说明

### Docker Compose 配置

```yaml
qdrant:
  image: qdrant/qdrant:v1.11.3
  container_name: qdrant_QTRAN
  ports:
    - "6333:6333"   # HTTP API
    - "6334:6334"   # gRPC API
  volumes:
    - qdrant_data:/qdrant/storage  # 持久化存储
  networks:
    - db_network
  restart: unless-stopped
```

### 环境变量（QTRAN）

```bash
# .env 文件
QDRANT_HOST=localhost
QDRANT_PORT=6333
QTRAN_USE_MEM0=true
```

### 端口说明

| 端口 | 用途 | 说明 |
|------|------|------|
| 6333 | HTTP API | Mem0 使用此端口（主要） |
| 6334 | gRPC API | 可选，高性能场景使用 |

---

## 📊 使用示例

### 查看集合列表

```bash
curl http://localhost:6333/collections
```

### 查看 Mem0 创建的集合

```bash
curl http://localhost:6333/collections/qtran_transfer_memory
```

预期输出示例：
```json
{
  "result": {
    "status": "green",
    "vectors_count": 42,
    "points_count": 42,
    "segments_count": 1
  }
}
```

### 查看集合中的向量数量

```bash
curl http://localhost:6333/collections/qtran_transfer_memory | jq '.result.points_count'
```

---

## 🛠️ 维护操作

### 备份数据

```bash
# 方式 1: Docker Volume 备份
docker run --rm -v qdrant_data:/source -v $(pwd):/backup alpine tar czf /backup/qdrant_backup_$(date +%Y%m%d).tar.gz -C /source .

# 方式 2: 使用 Qdrant 快照 API
curl -X POST http://localhost:6333/collections/qtran_transfer_memory/snapshots
```

### 恢复数据

```bash
# 从 tar.gz 恢复
docker run --rm -v qdrant_data:/target -v $(pwd):/backup alpine tar xzf /backup/qdrant_backup_YYYYMMDD.tar.gz -C /target
```

### 清空所有数据

```bash
# ⚠️ 警告：此操作不可逆
docker-compose down
docker volume rm qdrant_data
docker-compose up -d qdrant
```

### 删除特定集合

```bash
curl -X DELETE http://localhost:6333/collections/qtran_transfer_memory
```

---

## 🐛 故障排查

### 问题 1: 容器启动失败

**检查日志**：
```bash
docker logs qdrant_QTRAN
```

**常见原因**：
- 端口 6333 被占用
- 磁盘空间不足
- Docker 版本过旧

**解决方法**：
```bash
# 检查端口占用
netstat -tuln | grep 6333

# 检查磁盘空间
df -h

# 更换端口（修改 docker-compose.yml）
ports:
  - "16333:6333"  # 使用其他端口
```

### 问题 2: 连接超时

**检查网络**：
```bash
# 测试连接
curl -v http://localhost:6333/health

# 检查防火墙
sudo iptables -L | grep 6333
```

### 问题 3: 数据丢失

**原因**：未配置持久化卷

**解决**：确保 docker-compose.yml 中有 volumes 配置：
```yaml
volumes:
  - qdrant_data:/qdrant/storage
```

### 问题 4: 性能下降

**优化建议**：

1. **增加内存**（docker-compose.yml）：
```yaml
qdrant:
  deploy:
    resources:
      limits:
        memory: 2G
```

2. **定期清理旧记忆**：
```bash
python tools/mem0_inspector.py cleanup --days 90
```

3. **监控资源使用**：
```bash
docker stats qdrant_QTRAN
```

---

## 📈 性能监控

### 实时监控

```bash
# CPU 和内存使用
docker stats qdrant_QTRAN --no-stream

# 磁盘使用
docker exec qdrant_QTRAN du -sh /qdrant/storage
```

### Prometheus 指标

Qdrant 暴露 Prometheus 指标：
```bash
curl http://localhost:6333/metrics
```

---

## 🔐 安全加固（生产环境）

### 1. 启用 API Key 认证

**docker-compose.yml**：
```yaml
qdrant:
  environment:
    QDRANT__SERVICE__API_KEY: "your-secret-key-here"
```

**QTRAN 配置** (mem0_adapter.py)：
```python
config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": "localhost",
            "port": 6333,
            "api_key": os.environ.get("QDRANT_API_KEY"),  # 新增
            "collection_name": "qtran_transfer_memory"
        }
    }
}
```

### 2. 限制网络访问

**仅本地访问**：
```yaml
qdrant:
  ports:
    - "127.0.0.1:6333:6333"  # 只允许本地连接
```

### 3. 定期备份

**Cron 任务**：
```bash
# 每天凌晨 2 点备份
0 2 * * * /root/QTRAN/scripts/backup_qdrant.sh
```

---

## 📚 参考资源

- [Qdrant 官方文档](https://qdrant.tech/documentation/)
- [Qdrant Docker Hub](https://hub.docker.com/r/qdrant/qdrant)
- [Qdrant API 参考](https://qdrant.github.io/qdrant/redoc/index.html)
- [QTRAN Mem0 集成文档](./MEM0_QUICKSTART.md)

---

## 🎯 快速命令速查表

```bash
# 启动
./docker_start_qdrant.sh

# 停止
./docker_stop_qdrant.sh

# 查看状态
curl http://localhost:6333/health

# 查看集合
curl http://localhost:6333/collections

# 查看日志
docker logs -f qdrant_QTRAN

# 重启
docker-compose restart qdrant

# 备份
docker run --rm -v qdrant_data:/source -v $(pwd):/backup alpine tar czf /backup/qdrant_backup.tar.gz -C /source .

# 清理（⚠️ 危险）
docker-compose down -v
```

---

**最后更新**: 2025-10-23  
**作者**: huanghe  
**版本**: 1.0

