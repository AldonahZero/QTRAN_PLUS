# 知识库到 Mem0 集成文档

## 概述

本文档描述如何将 NoSQLFeatureKnowledgeBase 和 FeatureKnowledgeBase 中的知识导入到 Mem0 记忆系统中，以增强 QTRAN 的翻译能力。

## 架构设计

### 知识组织结构

```
Mem0 记忆存储
├── qtran_kb_mongodb (MongoDB 知识库)
│   ├── operators (操作符知识)
│   ├── api_patterns (API 模式)
│   └── code_snippets (代码片段)
├── qtran_kb_redis (Redis 知识库)
│   ├── commands (命令知识)
│   └── sql_mapping (SQL 映射)
├── qtran_kb_mysql (MySQL 知识库)
│   ├── datatype (数据类型)
│   ├── function (函数)
│   └── operator (操作符)
├── qtran_kb_postgres (PostgreSQL 知识库)
└── ... (其他数据库)
```

### 记忆类型分类

1. **NoSQL 知识库**
   - `type: operator` - 操作符定义
   - `type: api_pattern` - API 使用模式
   - `type: code_snippet` - 代码示例
   - `type: command` - 命令定义
   - `type: sql_mapping` - SQL 到 NoSQL 的映射

2. **SQL 知识库**
   - `type: datatype` - 数据类型定义
   - `type: function` - 函数定义
   - `type: operator` - 操作符定义

## 快速开始

### 1. 环境准备

```bash
# 确保已安装依赖
pip install -r requirements.txt

# 启动 Qdrant（如果还没启动）
docker run -d -p 6333:6333 qdrant/qdrant

# 设置环境变量
export QTRAN_USE_MEM0=true
export OPENAI_API_KEY=your_api_key_here
```

### 2. 导入知识库

#### 导入所有知识库（推荐首次使用）

```bash
# 导入所有 NoSQL 和 SQL 数据库的知识
# 注意：这可能需要 30-60 分钟，取决于数据量
python tools/knowledge_base_importer.py --all
```

#### 选择性导入

```bash
# 只导入 MongoDB 知识
python tools/knowledge_base_importer.py --nosql mongodb

# 只导入 Redis 知识
python tools/knowledge_base_importer.py --nosql redis

# 只导入 MySQL 知识
python tools/knowledge_base_importer.py --sql mysql

# 只导入 MySQL 的数据类型和函数
python tools/knowledge_base_importer.py --sql mysql --type datatype,function

# 导入 PostgreSQL 知识
python tools/knowledge_base_importer.py --sql postgres
```

### 3. 验证导入

```bash
# 查看导入的记忆统计
python tools/mem0_inspector.py inspect --limit 20

# 搜索特定知识
python tools/mem0_inspector.py search "MongoDB \$and operator"
python tools/mem0_inspector.py search "MySQL INTEGER type"
```

## 使用方式

### 在翻译中自动使用知识库

知识库已集成到 `mem0_adapter.py` 中，当启用 Mem0 时会自动工作：

```python
# 在 TransferLLM.py 中的使用（已自动集成）
from src.TransferLLM.mem0_adapter import TransferMemoryManager

manager = TransferMemoryManager(user_id="qtran_redis_to_mongodb")
manager.start_session(origin_db="redis", target_db="mongodb", molt="semantic")

# 构建增强的 prompt（自动包含知识库信息）
enhanced_prompt = manager.build_enhanced_prompt(
    base_prompt=base_prompt,
    query_sql=sql_statement,
    origin_db="redis",
    target_db="mongodb",
    include_knowledge_base=True  # 默认为 True
)

# 后续使用 enhanced_prompt 调用 LLM...
```

### 手动查询知识库

```python
from src.TransferLLM.mem0_adapter import TransferMemoryManager

manager = TransferMemoryManager(user_id="qtran_test")

# 查询 MongoDB 相关知识
kb_info = manager.get_knowledge_base_info(
    query="$and operator usage",
    database="mongodb",
    limit=3
)

for info in kb_info:
    print(f"Memory: {info['memory']}")
    print(f"Metadata: {info['metadata']}")
```

## 知识库内容说明

### NoSQL 知识库

#### MongoDB 知识

1. **知识图谱** (`mongodb_knowledge_graph.json`)
   - 操作符及其关系
   - 等价形式
   - 使用方法
   - 属性和关系（如 De Morgan's Law）

   示例：
   ```
   MongoDB Operator: $and
   Equivalent forms: implicit_conjunction
   Used with methods: find
   Properties: commutative
   Equivalent to: $not via De Morgan's Law
   ```

2. **API 模式** (`extracted_api_patterns.json`)
   - 实际 API 调用示例
   - 参数结构
   - 使用的操作符

   示例：
   ```
   MongoDB API Pattern: db.inventory.insertMany()
   Example arguments: [{"item": "journal", "qty": 25, ...}]
   Uses operators: $eq, $in
   ```

3. **代码片段** (`mongodb_code_snippets.json`)
   - 常见操作的代码示例
   - 最佳实践
   - 典型用例

#### Redis 知识

1. **命令知识** (`redis_commands_knowledge.json`)
   - 命令定义
   - 使用示例
   - 参数说明

   示例：
   ```
   Redis Command: SET
   Example: SET mykey "Hello"
   Example: SET mykey "World" EX 60
   ```

2. **SQL 映射** (`sql_to_redis_mapping.json`)
   - SQL 操作到 Redis 命令的映射
   - 转换示例
   - 注意事项

### SQL 知识库

#### 数据类型 (datatype)

示例 (MySQL):
```
MYSQL Data Type: INTEGER
Description: MySQL supports INTEGER (or INT) and SMALLINT types...
Category: Numeric Data Types > Integer Types
Example SQL: SELECT CAST(123 AS SIGNED);
Reference: https://dev.mysql.com/doc/refman/8.0/en/integer-types.html
```

#### 函数 (function)

示例 (MySQL):
```
MYSQL Function: ABS(X)
Description: Returns the absolute value of X, or NULL if X is NULL.
Category: Built-In Functions and Operators > Mathematical Functions
Example SQL: SELECT ABS(2);
Example SQL: SELECT ABS(-32);
```

#### 操作符 (operator)

示例 (MySQL):
```
MYSQL Operator: =
Description: Equal operator for comparison...
Category: Operators > Comparison Operators
Example SQL: SELECT 1 = 1;
```

## 知识库更新策略

### 增量更新

当知识库文件更新后，重新导入即可：

```bash
# 重新导入特定数据库
python tools/knowledge_base_importer.py --nosql mongodb

# 系统会自动去重（Mem0 基于向量相似度）
```

### 清理旧知识

```bash
# 导出备份
python tools/mem0_inspector.py export kb_backup_$(date +%Y%m%d).json

# 清理 90 天前的知识（如果设置了时间戳）
python tools/mem0_inspector.py cleanup --days 90
```

## 性能优化

### 导入性能

1. **批量导入限制**
   - MongoDB API 模式：限制为 500 个样本
   - MongoDB 代码片段：限制为 300 个样本
   - SQL 特性：导入全部，每 20 个显示进度

2. **优化建议**
   ```bash
   # 如果导入速度慢，可以减少样本数量
   # 编辑 tools/knowledge_base_importer.py
   max_samples = 500  # 改为 200
   max_snippets = 300  # 改为 100
   ```

### 查询性能

1. **关键词提取优化**
   - 自动从 SQL 中提取关键词
   - 限制为前 5 个最相关的关键词
   - 避免过长的查询字符串

2. **结果数量控制**
   - 默认每个数据库返回 2 条知识
   - 历史翻译记忆返回 3 条
   - 总共约 7-10 条增强信息

## 故障排查

### 问题 1: 导入失败

```bash
# 检查 Qdrant 是否运行
curl http://localhost:6333/health

# 查看详细错误
python tools/knowledge_base_importer.py --sql mysql 2>&1 | tee import.log
```

### 问题 2: 知识未被检索到

```python
# 测试知识库查询
from src.TransferLLM.mem0_adapter import TransferMemoryManager

manager = TransferMemoryManager()
results = manager.get_knowledge_base_info("INTEGER", "mysql", limit=5)
print(f"Found {len(results)} results")
for r in results:
    print(r)
```

### 问题 3: Prompt 过长

```python
# 禁用知识库增强
enhanced_prompt = manager.build_enhanced_prompt(
    base_prompt=base_prompt,
    query_sql=sql,
    origin_db=origin_db,
    target_db=target_db,
    include_knowledge_base=False  # 只使用历史翻译记忆
)
```

## 配置选项

### 环境变量

```bash
# 启用/禁用 Mem0
export QTRAN_USE_MEM0=true

# Qdrant 配置
export QDRANT_HOST=localhost
export QDRANT_PORT=6333

# OpenAI 配置
export OPENAI_API_KEY=your_key
export OPENAI_MEMORY_MODEL=gpt-4o-mini  # 用于记忆管理的模型
```

### 代码配置

在 `mem0_adapter.py` 中可调整的参数：

```python
# build_enhanced_prompt() 方法
memories = self.get_relevant_memories(..., limit=3)  # 历史记忆数量
kb_info_origin = self.get_knowledge_base_info(..., limit=2)  # 源 DB 知识数量
kb_info_target = self.get_knowledge_base_info(..., limit=2)  # 目标 DB 知识数量

# _extract_keywords_from_sql() 方法
unique_keywords = list(dict.fromkeys(keywords))[:5]  # 关键词数量
```

## 统计与监控

### 导入统计

导入完成后会显示统计信息：

```
📊 Knowledge Base Import Statistics
====================================
Total memories imported: 1234

By Database:
  mongodb: 500
  mysql: 234
  postgres: 200
  redis: 300

By Type:
  operator: 150
  function: 400
  datatype: 200
  api_pattern: 300
  command: 184

⏱️  Total time: 245.32s
💾 Average time per memory: 0.199s
```

### 运行时监控

```bash
# 查看记忆使用情况
python tools/mem0_inspector.py inspect --limit 50

# 搜索特定类型
python tools/mem0_inspector.py search "type:operator"
python tools/mem0_inspector.py search "database:mongodb"
```

## 高级用法

### 自定义知识导入

如果需要添加自定义知识：

```python
from src.TransferLLM.mem0_adapter import TransferMemoryManager

manager = TransferMemoryManager()

# 添加自定义知识
manager.memory.add(
    "PostgreSQL SERIAL type is equivalent to AUTO_INCREMENT in MySQL",
    user_id="qtran_kb_postgres",
    metadata={
        "database": "postgres",
        "type": "datatype",
        "feature_name": "SERIAL",
        "source": "custom"
    }
)
```

### 导出和分享知识

```bash
# 导出特定数据库的知识
python tools/mem0_inspector.py export mongodb_kb.json

# 在另一个环境导入
python tools/mem0_inspector.py import mongodb_kb.json
```

## 最佳实践

1. **首次使用**
   - 先导入常用数据库 (MySQL, PostgreSQL, MongoDB, Redis)
   - 验证导入成功
   - 运行小规模测试

2. **定期维护**
   - 每月导出备份
   - 清理过时的知识
   - 更新知识库文件后重新导入

3. **性能优化**
   - 监控 prompt 长度
   - 根据实际效果调整检索数量
   - 必要时禁用某些类型的知识增强

4. **调试技巧**
   - 使用 `mem0_inspector.py` 查看实际存储的内容
   - 检查 metadata 确保分类正确
   - 对比有无知识库增强的翻译效果

## 示例工作流

### 完整的使用流程

```bash
# 1. 初始化环境
export QTRAN_USE_MEM0=true
export OPENAI_API_KEY=your_key
docker run -d -p 6333:6333 qdrant/qdrant

# 2. 导入知识库
python tools/knowledge_base_importer.py --nosql mongodb
python tools/knowledge_base_importer.py --nosql redis
python tools/knowledge_base_importer.py --sql mysql
python tools/knowledge_base_importer.py --sql postgres

# 3. 验证导入
python tools/mem0_inspector.py inspect --limit 10

# 4. 运行翻译测试
python -m src.TransferLLM.translate_sqlancer \
    --input Input/test_redis_to_mongodb.jsonl \
    --output Output/results.jsonl

# 5. 查看增强效果
# 检查日志中的 "📚 Relevant Historical Knowledge" 部分
# 检查日志中的 "📖 Knowledge Base" 部分

# 6. 导出记忆备份
python tools/mem0_inspector.py export backup_$(date +%Y%m%d).json
```

## 参考资料

- [Mem0 官方文档](https://docs.mem0.ai/)
- [Qdrant 文档](https://qdrant.tech/documentation/)
- [QTRAN Mem0 集成总结](./MEM0_INTEGRATION_SUMMARY.md)
- [Mem0 快速开始](./MEM0_QUICKSTART.md)

## 更新日志

### 2025-10-24
- ✅ 创建知识库导入工具 (`knowledge_base_importer.py`)
- ✅ 扩展 `mem0_adapter.py` 支持知识库查询
- ✅ 添加自动关键词提取功能
- ✅ 集成到翻译 prompt 增强流程
- ✅ 支持所有主要数据库 (MongoDB, Redis, MySQL, PostgreSQL 等)

### 未来计划
- 🔄 添加知识质量评分机制
- 🔄 实现知识版本控制
- 🔄 支持知识库自动更新
- 🔄 添加知识使用统计分析

