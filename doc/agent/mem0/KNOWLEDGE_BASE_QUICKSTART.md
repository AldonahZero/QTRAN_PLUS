# 知识库集成快速开始指南

## 🚀 5 分钟快速开始

http://localhost:63613/collections/qtran_mutation_memories
http://localhost:63613/collections/qtran_transfer_memory
### 步骤 1: 安装依赖

```bash
# 确保已安装必要的包
pip install mem0ai qdrant-client
```

### 步骤 2: 启动 Qdrant

```bash
# 使用 Docker 启动 Qdrant
docker run -d -p 6333:6333 --name qtran-qdrant qdrant/qdrant

# 验证 Qdrant 运行
curl http://localhost:6333/health
```

### 步骤 3: 设置环境变量

```bash
export QTRAN_USE_MEM0=true
export OPENAI_API_KEY=your_openai_api_key_here
```

### 步骤 4: 导入知识库

#### 选项 A: 使用批量导入脚本（推荐）

```bash
# 导入所有知识库（可能需要 30-60 分钟）
./tools/batch_import_knowledge.sh --all

# 或者只导入 NoSQL 数据库
./tools/batch_import_knowledge.sh --nosql

# 或者只导入 SQL 数据库
./tools/batch_import_knowledge.sh --sql
```

#### 选项 B: 手动导入特定数据库

```bash
# MongoDB
python tools/knowledge_base_importer.py --nosql mongodb

# Redis
python tools/knowledge_base_importer.py --nosql redis

# MySQL
python tools/knowledge_base_importer.py --sql mysql

# PostgreSQL
python tools/knowledge_base_importer.py --sql postgres
```

### 步骤 5: 验证导入

```bash
# 查看导入的知识
python tools/mem0_inspector.py inspect --limit 20

# 搜索特定知识
python tools/mem0_inspector.py search "MongoDB \$and"
```

### 步骤 6: 运行测试

```bash
# 快速测试（导入少量测试数据）
python test_knowledge_base_integration.py --quick

# 完整测试（需要先导入知识库）
python test_knowledge_base_integration.py
```

### 步骤 7: 使用知识库进行翻译

```bash
# 知识库会自动集成到翻译流程中
export QTRAN_USE_MEM0=true

python -m src.TransferLLM.translate_sqlancer \
    --input Input/test.jsonl \
    --output Output/results.jsonl
```

## 📊 导入统计参考

典型的导入统计（供参考）：

```
Total memories imported: 2500-3500

By Database:
  mongodb: 800-1000    (operators + API patterns + snippets)
  redis: 100-200       (commands + mappings)
  mysql: 400-600       (datatypes + functions + operators)
  postgres: 300-500
  sqlite: 200-300
  其他 SQL: 每个 200-400

By Type:
  function: 800-1200
  operator: 300-500
  datatype: 400-600
  api_pattern: 500-800
  command: 100-200
  code_snippet: 300-500
```

## 🎯 常见使用场景

### 场景 1: Redis 到 MongoDB 翻译

```bash
# 1. 导入相关知识库
python tools/knowledge_base_importer.py --nosql redis
python tools/knowledge_base_importer.py --nosql mongodb

# 2. 运行翻译
export QTRAN_USE_MEM0=true
python -m src.TransferLLM.translate_sqlancer \
    --input Input/redis_to_mongodb.jsonl
```

### 场景 2: MySQL 到 PostgreSQL 翻译

```bash
# 1. 导入相关知识库
python tools/knowledge_base_importer.py --sql mysql
python tools/knowledge_base_importer.py --sql postgres

# 2. 运行翻译
python -m src.TransferLLM.translate_sqlancer \
    --input Input/mysql_to_postgres.jsonl
```

### 场景 3: 查询特定知识

```python
from src.TransferLLM.mem0_adapter import TransferMemoryManager

manager = TransferMemoryManager()

# 查询 MongoDB 的 $and 操作符
results = manager.get_knowledge_base_info("$and operator", "mongodb", limit=3)
for r in results:
    print(r['memory'])

# 查询 MySQL 的 INTEGER 类型
results = manager.get_knowledge_base_info("INTEGER type", "mysql", limit=3)
for r in results:
    print(r['memory'])
```

## ⚡ 性能优化建议

### 减少导入时间

如果完整导入太慢，可以：

1. **只导入需要的数据库**
   ```bash
   # 只导入常用的数据库
   python tools/knowledge_base_importer.py --nosql mongodb
   python tools/knowledge_base_importer.py --sql mysql
   python tools/knowledge_base_importer.py --sql postgres
   ```

2. **减少样本数量**（编辑 `tools/knowledge_base_importer.py`）
   ```python
   # 找到这些行并修改数量
   max_samples = 500    # 改为 200
   max_snippets = 300   # 改为 100
   ```

### 控制 Prompt 长度

如果 Prompt 太长，可以：

1. **减少检索数量**（编辑 `src/TransferLLM/mem0_adapter.py`）
   ```python
   # build_enhanced_prompt() 方法中
   memories = self.get_relevant_memories(..., limit=2)  # 默认 3
   kb_info_origin = self.get_knowledge_base_info(..., limit=1)  # 默认 2
   kb_info_target = self.get_knowledge_base_info(..., limit=1)  # 默认 2
   ```

2. **禁用知识库增强**
   ```python
   enhanced_prompt = manager.build_enhanced_prompt(
       ...,
       include_knowledge_base=False  # 只使用历史翻译记忆
   )
   ```

## 🔧 故障排查

### 问题 1: Qdrant 连接失败

```bash
# 检查 Qdrant 是否运行
docker ps | grep qdrant

# 重启 Qdrant
docker restart qtran-qdrant

# 或重新创建
docker rm -f qtran-qdrant
docker run -d -p 6333:6333 --name qtran-qdrant qdrant/qdrant
```

### 问题 2: 导入速度很慢

```bash
# 检查网络延迟（OpenAI API）
ping api.openai.com

# 检查 Qdrant 性能
curl http://localhost:6333/collections
```

### 问题 3: 知识未被检索到

```bash
# 检查知识是否存在
python tools/mem0_inspector.py search "your query"

# 检查 user_id 是否正确
# 知识库使用格式: qtran_kb_{database}
# 例如: qtran_kb_mongodb, qtran_kb_mysql
```

### 问题 4: OpenAI API 配额不足

```bash
# 使用更便宜的模型
export OPENAI_MEMORY_MODEL=gpt-3.5-turbo  # 默认 gpt-4o-mini

# 或使用 Fallback 模式（本地存储）
# 导入时会自动降级到 ChromaDB
```

## 📦 备份与恢复

### 创建备份

```bash
# 导出所有记忆
python tools/mem0_inspector.py export backup_$(date +%Y%m%d).json

# 备份脚本会自动创建备份目录
./tools/batch_import_knowledge.sh --all
# 完成后会询问是否创建备份
```

### 恢复备份

```bash
# 从备份文件恢复
python tools/mem0_inspector.py import backup_20251024.json
```

## 📝 下一步

完成快速开始后，建议：

1. **阅读完整文档**
   - [知识库集成详细文档](./KNOWLEDGE_BASE_MEM0_INTEGRATION.md)
   - [Mem0 集成总结](./MEM0_INTEGRATION_SUMMARY.md)

2. **运行实际测试**
   ```bash
   python -m src.TransferLLM.translate_sqlancer \
       --input Input/your_test_data.jsonl
   ```

3. **监控效果**
   - 查看日志中的 "📚 Relevant Historical Knowledge" 部分
   - 查看日志中的 "📖 Knowledge Base" 部分
   - 比较有无知识库增强的翻译质量

4. **定期维护**
   - 每月导出备份
   - 清理过时知识（如果需要）
   - 更新知识库文件后重新导入

## 💡 提示

- **首次使用**：建议先使用 `--quick` 模式测试
- **生产使用**：导入所有相关数据库的知识
- **开发调试**：使用 `mem0_inspector.py` 查看实际存储内容
- **性能调优**：根据实际效果调整检索数量

## 🆘 获取帮助

如果遇到问题：

1. 查看详细文档: [KNOWLEDGE_BASE_MEM0_INTEGRATION.md](./KNOWLEDGE_BASE_MEM0_INTEGRATION.md)
2. 运行测试: `python test_knowledge_base_integration.py --quick`
3. 查看日志: 检查导入和翻译过程的日志输出
4. 检查环境: 确保 Qdrant、OpenAI API Key 配置正确

---

**创建日期**: 2025-10-24  
**更新日期**: 2025-10-24  
**版本**: 1.0

