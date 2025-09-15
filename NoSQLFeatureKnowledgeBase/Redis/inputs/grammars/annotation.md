# Redis 注解与语义提取

本目录放置 Redis 的带标签语法与注解：
- Redis.g4：带标签（#AltName 与 elem=label）的 ANTLR4 语法
- Redis.json：BuzzBee 风格的 annotations，描述 Define/Use/Invalidate/Scope/AlterOrder 等语义
- annotation.md：注解编写规范与约定（非必须，供人读）

---

## by_command 视图（自动生成）

脚本 `src/NoSQLKnowledgeBaseConstruction/Redis/merge_semantics_with_grammar.py` 会把 `outputs/redis_semantic_kb.json` 中的 `by_tag` 聚合为 `by_command`，形成：
- by_command[command].actions: 该命令的汇总动作（Define/Use/Invalidate/AlterOrder）
- by_command[command].args[label]: 指定参数位的动作与涉及的类型（含 custom_resolver 展开名）
- tag_to_command: 从标签（如 `AppendRule1->elem`）到命令名（`append`）的映射

快速用法：
- 查询某命令定义的资源：by_command[cmd].actions.DefineSymbol
- 查询某命令第一个 key 位使用的资源：by_command[cmd].args.elem.UseSymbol（label 以语法标签为准）

生成或更新：
- 需先生成 `outputs/redis_semantic_kb.json`（已含 by_tag）
- 然后运行合并脚本（已在仓库中）：

```bash
python3 src/NoSQLKnowledgeBaseConstruction/Redis/merge_semantics_with_grammar.py
```

生成后的文件路径：
- `NoSQLFeatureKnowledgeBase/Redis/outputs/redis_semantic_kb.json`

用途：
- RAG：根据命令名直接检索其 Define/Use/Invalidate 的 key 类型与语义
- 变异/生成：定位参数位（label）并替换为符合类型约束的符号或值
- Oracle：根据 Invalidate/Scope 等信息进行副作用与范围推理

---

## 查询 CLI（可选）

脚本：`src/NoSQLKnowledgeBaseConstruction/Redis/query_semantic_kb.py`

示例：
```bash
# 列出命令（支持过滤）
python3 src/NoSQLKnowledgeBaseConstruction/Redis/query_semantic_kb.py list-commands --grep '^bit'

# 查看命令详情（包含参数位）
python3 src/NoSQLKnowledgeBaseConstruction/Redis/query_semantic_kb.py show bitop --args

# 反查某类型在哪些命令被使用/定义/失效
python3 src/NoSQLKnowledgeBaseConstruction/Redis/query_semantic_kb.py find-type sorted_set_key --action UseSymbol

# 查看标签对应的命令名
python3 src/NoSQLKnowledgeBaseConstruction/Redis/query_semantic_kb.py tag2cmd 'AppendRule1->elem'
```
