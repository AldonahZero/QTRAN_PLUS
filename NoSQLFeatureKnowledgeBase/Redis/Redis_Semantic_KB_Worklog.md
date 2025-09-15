# Redis 语义知识库构建与查询（工作汇总）

本文档记录本次对 Redis 知识库的自动化增强：从 BuzzBee 注解和带标签语法提取语义，再合并为“命令速查视图”，并提供 CLI 查询工具。

## 目录与产物
- 输入（已就绪）
  - `NoSQLFeatureKnowledgeBase/Redis/inputs/grammars/Redis.g4`: 带 #AltName 与 elem=label 的语法
  - `NoSQLFeatureKnowledgeBase/Redis/inputs/grammars/Redis.json`: BuzzBee 风格注解（Define/Use/Invalidate/Scope/AlterOrder）
  - `NoSQLFeatureKnowledgeBase/Redis/inputs/grammars/annotation.md`: 注解说明与使用指南
- 输出（自动生成/更新）
  - `NoSQLFeatureKnowledgeBase/Redis/outputs/redis_semantic_kb.json`
    - `by_tag`: 注解按标签聚合（已有）
    - `by_command`: 新增，按命令聚合 Define/Use/Invalidate/AlterOrder
    - `tag_to_command`: 新增，标签→命令映射
    - `sources.Redis.g4`: 语法文件追踪信息（size/mtime）

## 生成脚本
- 从注解抽取语义（已存在）：
  - `src/NoSQLKnowledgeBaseConstruction/Redis/annotations_to_semantics.py`
  - 输出：`outputs/redis_semantic_kb.json`（含 by_tag）
- 合并语法标签与语义动作（新增）：
  - `src/NoSQLKnowledgeBaseConstruction/Redis/merge_semantics_with_grammar.py`
  - 功能：
    - 解析 `by_tag` 的键（如 `AppendRule1->elem`、逗号分隔多个标签）
    - 以规则前缀提取命令名（`AppendRule`→`append`，`ZUnionStoreRule`→`zunionstore`）
    - 聚合到 `by_command`（整体与按参数位）并生成 `tag_to_command`

运行（先确保 `redis_semantic_kb.json` 已包含 by_tag）：
```bash
python3 src/NoSQLKnowledgeBaseConstruction/Redis/merge_semantics_with_grammar.py
```

## 查询 CLI（新增）
- 脚本：`src/NoSQLKnowledgeBaseConstruction/Redis/query_semantic_kb.py`
- 顶层入口集成：`python -m src.main redis-kb ...`
- 常用命令：
```bash
# 列出命令（可过滤）
python -m src.main redis-kb list-commands --grep '^bit'

# 展示命令详情（含参数位动作）
python -m src.main redis-kb show bitop --args

# 按类型反查（例：哪些命令 Use 有序集合 key）
python -m src.main redis-kb find-type sorted_set_key --action UseSymbol

# 标签映射到命令
python -m src.main redis-kb tag2cmd 'AppendRule1->elem'
```

实现要点：
- 惰性导入：在 `src/main.py` 中对子命令进行早期分流；TransferLLM 与 docker 相关模块在主流程内按需导入
- 可重复运行：合并脚本幂等，重复执行只会刷新视图

## 用途与集成
- RAG 提示：根据命令名直接取 `by_command[cmd].actions/args` 描述类型与副作用
- 变异生成：利用 `by_command[cmd].args[label]` 的类型约束替换/生成参数
- Oracle 推理：依托 `InvalidateSymbol`/`Scope` 等信息判断副作用与范围
- 调试辅助：`tag_to_command` 帮助语法标签与命令之间跳转

## 后续建议
- 扩展 custom resolver：将 `##hset_field_type_resolver` 等解析为具体类型集合
- 增加单测覆盖：对 CLI 输出进行更细粒度校验（当前已含最小用例 `tests/test_redis_kb_cli.py`）
- 如需 MongoDB 侧复用，抽象通用合并器与查询 CLI 模板
