# Design

该目录存放系统设计、模块设计、知识建模、迁移与变异机制等详细设计文档。

子类目建议：
- 架构设计
- 模块设计
- 数据/知识建模
- 迁移与变异逻辑
- 性能与扩展性

## 当前文档
- `transfer_and_mutation_knowledge_design.md`：Transfer 与 Mutation 阶段知识/RAG/Oracle 使用策略。
- `redis_to_mongodb_conversion_summary.md`：Redis 命令到 MongoDB 文档结构映射与实现注意事项。

## 计划追加
- result_normalization.md （跨 KV / 文档 / 关系 结果统一结构方案）
- error_iteration_strategy.md （LLM 错误分类与迭代修正规则表）
- feature_mapping_cache.md （映射缓存与失效策略）
