# Redis 知识库（输入与产物）

本文档说明 Redis 知识库在 QTRAN_PLUS 中的输入素材与自动生成的产物，以及对应的生成脚本与用途。

## 目录结构

```
NoSQLFeatureKnowledgeBase/Redis/
	inputs/                     # 输入素材（人工或上游来源）
		examples/                 # 原始命令示例（.txt）
		grammars/                 # Redis.g4 + Redis.json + annotation.md（带标签语法与注解）
		mapping/                  # SQL→Redis 映射策略（人工维护）

	outputs/                    # 自动产物（可直接用于 RAG/Transfer/Mutation/Oracle）
		parsed_examples/                  # 结构化的示例（由 examples/*.txt 生成）
		parsed_examples_enriched/         # 带 expected 返回的示例（连 Redis 执行采集）
		command_cards_draft.json          # 由 g4 语法抽取的命令卡片草稿
		redis_commands_knowledge.json     # 合并卡片+示例的统一知识库（卡片+示例）
		sql_to_redis_mapping.json         # SQL 语义到 Redis 的模式映射（供 RAG）
		redis_semantic_kb.json            # 语义 KB：by_tag/by_command/tag_to_command/alter_orders

	README.md
```

## 生成脚本

- examples → parsed_examples
	- 脚本：`src/NoSQLKnowledgeBaseConstruction/Redis/examples_to_json.py`
	- 输入：`inputs/examples/*.txt`
	- 输出：`outputs/parsed_examples/*.json`

- 语法 g4 → 命令卡片草稿
	- 脚本：`src/NoSQLKnowledgeBaseConstruction/Redis/grammar_to_cards.py`
	- 输入：`inputs/grammars/Redis.g4`
	- 输出：`outputs/command_cards_draft.json`

- 合并卡片与示例 → 统一知识库
	- 脚本：`src/NoSQLKnowledgeBaseConstruction/Redis/merge_cards_and_examples.py`
	- 输入：`outputs/command_cards_draft.json` + `outputs/parsed_examples[_enriched]/*.json`
	- 输出：`outputs/redis_commands_knowledge.json`

- 注解 → 语义（by_tag）
	- 脚本：`src/NoSQLKnowledgeBaseConstruction/Redis/annotations_to_semantics.py`
	- 输入：`inputs/grammars/Redis.json`
	- 输出：`outputs/redis_semantic_kb.json`（含 by_tag）

- 语法×语义合并 → 命令速查视图
	- 脚本：`src/NoSQLKnowledgeBaseConstruction/Redis/merge_semantics_with_grammar.py`
	- 输入：`outputs/redis_semantic_kb.json`（已有 by_tag）、`inputs/grammars/Redis.g4`
	- 输出：`outputs/redis_semantic_kb.json`（新增 by_command、tag_to_command、sources）

- 采集 expected 返回（可选）
	- 脚本：`src/NoSQLKnowledgeBaseConstruction/Redis/enrich_examples_with_expected.py`
	- 输入：`outputs/parsed_examples/*.json`
	- 输出：`outputs/parsed_examples_enriched/*.json`
	- 依赖：本机 Redis（host/port 来自 `src/Tools/DatabaseConnect/database_connector_args.json`）

## 用途建议

`outputs/redis_commands_knowledge.json` 与 `outputs/sql_to_redis_mapping.json`：
	- 作为 Transfer 的 RAG 检索源，指导 LLM 选择合适命令/结构、避免陷阱。
	- 作为 Mutation 的等价/包含关系依据（可在卡片中补充 invariants）。

- `outputs/parsed_examples_enriched/*.json`：
	- Few-shot 示例与评测基线；对含 `expected_error` 的条目进行过滤。

`outputs/redis_semantic_kb.json`：
	- by_command：按命令聚合的 Define/Use/Invalidate/AlterOrder 与按参数位的类型集合，是 LLM 约束生成与变异的首选语义源。
	- by_tag：细粒度标签视图，便于溯源与精调。
	- tag_to_command：标签到命令名的映射，便于调试与语法追踪。
	- alter_orders：执行顺序约束片段，降低非确定性。

## 维护说明

- 新增命令示例：将 `.txt` 放入 `inputs/examples/`，运行 examples_to_json.py → merge_cards_and_examples.py。
- 更新语法：覆盖 `inputs/grammars/*.g4`，运行 grammar_to_cards.py → merge_cards_and_examples.py。
- 扩充映射：编辑 `outputs/sql_to_redis_mapping.json`（或迁移到 inputs/mapping 再由生成脚本复制到 outputs）。
 - 更新注解/语义视图：覆盖 `inputs/grammars/Redis.json`，运行 annotations_to_semantics.py；随后运行 merge_semantics_with_grammar.py 刷新 by_command。

## 快捷查询（CLI）

无需写代码可直接检索语义 KB：

```bash
python -m src.main redis-kb list-commands --grep '^z'
python -m src.main redis-kb show zadd --args
python -m src.main redis-kb find-type sorted_set_key --action UseSymbol
python -m src.main redis-kb tag2cmd 'ZAddRule2->elem'
```

## 致谢

- 初始 Redis 语法来源于第三方开源 grammar，版权归原作者所有；本仓库仅用于研究与工具链构建。
