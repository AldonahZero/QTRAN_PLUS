# Mem0 集成快速入门指南

## 🚀 5 分钟快速开始

### 第一步：安装依赖

```bash
# 安装所有依赖（包括 Mem0）
pip install -r requirements.txt

# 或单独安装 Mem0 相关包
pip install mem0ai==0.1.32 qdrant-client==1.11.3
```

### 第二步：启动向量数据库

#### 方式 1: 使用 Docker（推荐）

```bash
# 启动 Qdrant
docker run -d -p 6333:6333 qdrant/qdrant

# 验证是否运行
curl http://localhost:6333/health
```

#### 方式 2: 使用降级模式（无需 Qdrant）

如果不想安装 Docker，系统会自动降级到文件存储模式（功能受限）。

### 第三步：配置环境变量

```bash
# 创建或编辑 .env 文件
cat > .env << EOF
# 启用 Mem0
QTRAN_USE_MEM0=true

# Qdrant 配置（可选，默认值如下）
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Mem0 使用的 LLM 模型（用于记忆管理）
OPENAI_MEMORY_MODEL=gpt-4o-mini

# OpenAI API Key（必需）
OPENAI_API_KEY=your_api_key_here
EOF
```

### 第四步：运行测试验证

```bash
# 运行集成测试
python test_mem0_integration.py

# 使用降级模式测试（无需 Qdrant）
python test_mem0_integration.py --fallback
```

### 第五步：开始使用

```bash
# 启用 Mem0 后运行翻译
export QTRAN_USE_MEM0=true

# 运行正常的翻译任务
python -m src.TransferLLM.translate_sqlancer \
    --input Input/your_test_case.jsonl \
    --tool sqlancer \
    --model gpt-4o-mini
```

---

## 📖 使用示例

### 在代码中使用 Mem0

```python
from src.TransferLLM.mem0_adapter import TransferMemoryManager

# 初始化记忆管理器
manager = TransferMemoryManager(user_id="qtran_redis_to_mongodb")

# 开启会话
manager.start_session(
    origin_db="redis",
    target_db="mongodb",
    molt="semantic"
)

# 记录成功的翻译
manager.record_successful_translation(
    origin_sql="SET mykey hello",
    target_sql="db.myCollection.insertOne({ _id: 'mykey', value: 'hello' })",
    origin_db="redis",
    target_db="mongodb",
    iterations=1,
    features=["SET"]
)

# 搜索相关历史记忆
memories = manager.get_relevant_memories(
    query_sql="SET anotherkey world",
    origin_db="redis",
    target_db="mongodb",
    limit=3
)

# 增强 Prompt
enhanced_prompt = manager.build_enhanced_prompt(
    base_prompt="Your base prompt...",
    query_sql="SET testkey value",
    origin_db="redis",
    target_db="mongodb"
)

# 结束会话
manager.end_session(success=True)

# 查看性能指标
print(manager.get_metrics_report())
```

---

## 🔍 验证 Mem0 是否工作

### 检查日志输出

启用 Mem0 后，翻译过程会输出以下日志：

```
✅ Mem0 initialized for redis -> mongodb
📚 Prompt enhanced with Mem0 historical knowledge
💾 Recorded successful translation (iteration 1)
🔧 Recorded error fix pattern

=== Mem0 Performance Metrics ===
⏱️  Average search time: 0.123s
🔍 Total searches: 5
⏱️  Average add time: 0.089s
💾 Total additions: 8
🎯 Memory hit rate: 80.0%
================================
```

### 检查 Qdrant 中的数据

```bash
# 查看集合列表
curl http://localhost:6333/collections

# 查看记忆数量
curl http://localhost:6333/collections/qtran_transfer_memory
```

---

## ⚙️ 配置选项

### 环境变量完整列表

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `QTRAN_USE_MEM0` | `false` | 是否启用 Mem0 |
| `QDRANT_HOST` | `localhost` | Qdrant 服务地址 |
| `QDRANT_PORT` | `6333` | Qdrant 服务端口 |
| `OPENAI_MEMORY_MODEL` | `gpt-4o-mini` | 记忆管理使用的模型 |
| `OPENAI_API_KEY` | - | OpenAI API 密钥（必需） |

### 自定义配置

```python
# 在 mem0_adapter.py 中修改配置
config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": "your-qdrant-host",
            "port": 6333,
            "collection_name": "custom_collection_name"
        }
    },
    "llm": {
        "provider": "openai",
        "config": {
            "model": "gpt-4o",  # 使用更强的模型
            "temperature": 0.1,  # 降低温度提高一致性
        }
    }
}
```

---

## 🐛 常见问题

### Q1: Qdrant 连接失败

**现象**：
```
⚠️ Failed to initialize Mem0 with Qdrant, falling back to in-memory mode
```

**解决方法**：
```bash
# 检查 Qdrant 是否运行
docker ps | grep qdrant

# 如未运行，启动 Qdrant
docker run -d -p 6333:6333 qdrant/qdrant

# 检查端口是否被占用
netstat -tuln | grep 6333
```

### Q2: Mem0 未生效

**现象**：翻译过程中没有看到 Mem0 相关日志

**解决方法**：
```bash
# 确认环境变量已设置
echo $QTRAN_USE_MEM0  # 应输出 true

# 如果在 Python 中，直接设置
import os
os.environ["QTRAN_USE_MEM0"] = "true"
```

### Q3: 记忆搜索无结果

**现象**：`get_relevant_memories` 返回空列表

**原因**：
- 刚启动，还没有历史记忆
- 搜索的内容与已有记忆语义差距太大

**解决方法**：
```python
# 先记录一些案例
manager.record_successful_translation(...)

# 等待几秒让向量索引完成
import time
time.sleep(2)

# 再次搜索
memories = manager.get_relevant_memories(...)
```

### Q4: OpenAI API 调用失败

**现象**：
```
Error: OpenAI API key not found
```

**解决方法**：
```bash
# 设置 API Key
export OPENAI_API_KEY="sk-..."

# 或在代码中
os.environ["OPENAI_API_KEY"] = "sk-..."
```

---

## 📊 性能优化建议

### 1. 批量记录

```python
# 不推荐：每次翻译都创建新 manager
for sql in sqls:
    manager = TransferMemoryManager()
    manager.record_successful_translation(...)

# 推荐：复用 manager
manager = TransferMemoryManager()
for sql in sqls:
    manager.record_successful_translation(...)
```

### 2. 限制记忆数量

```python
# 搜索时限制返回数量
memories = manager.get_relevant_memories(..., limit=3)  # 仅取前 3 条
```

### 3. 定期清理旧记忆

```bash
# 每月清理一次（需要实现清理脚本）
python tools/cleanup_old_memories.py --days 90
```

---

## 📈 监控与调试

### 查看记忆内容

```python
# 使用 tools/mem0_inspector.py
from tools.mem0_inspector import inspect_memories, search_memories

# 查看最近的 10 条记忆
inspect_memories(user_id="qtran_redis_to_mongodb", limit=10)

# 搜索特定内容
search_memories("SET key value", limit=5)
```

### 性能指标

```python
# 在翻译结束后查看
manager.end_session(success=True)
print(manager.get_metrics_report())
```

输出示例：
```
=== Mem0 Performance Metrics ===
⏱️  Average search time: 0.089s
🔍 Total searches: 12
⏱️  Average add time: 0.045s
💾 Total additions: 8
🎯 Memory hit rate: 83.3%
================================
```

---

## 🔄 升级与迁移

### 从旧版本升级

```bash
# 备份现有数据
docker exec qdrant-container /bin/bash -c "cd /qdrant/storage && tar czf backup.tar.gz *"

# 更新依赖
pip install --upgrade mem0ai qdrant-client

# 重启 Qdrant
docker restart qdrant-container
```

### 导出与导入记忆

```python
# 导出
from tools.mem0_inspector import export_memories
export_memories("memories_backup.json")

# 导入
from tools.mem0_inspector import import_memories
import_memories("memories_backup.json")
```

---

## 📚 延伸阅读

- [Mem0 完整集成方案](./MEM0_INTEGRATION_PROPOSAL.md)
- [Mem0 官方文档](https://docs.mem0.ai/)
- [Qdrant 文档](https://qdrant.tech/documentation/)
- [QTRAN Agent 模式总结](../../AGENT_MODE_SUMMARY.md)

---

**最后更新**: 2025-10-23  
**作者**: huanghe  
**版本**: 1.0

