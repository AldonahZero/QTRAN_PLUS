# Redis 知识库（输入与产物）

本文档说明 Redis 知识库在 QTRAN_PLUS 中的输入素材与自动生成的产物，以及对应的生成脚本与用途。

## 目录结构

```
NoSQLFeatureKnowledgeBase/Redis/
	inputs/                 # 输入素材（人工或上游来源）
		examples/            # 原始命令示例（.txt）
		grammars/            # RedisLexer.g4 / RedisParser.g4
		mapping/             # SQL→Redis 映射策略（人工维护）

	outputs/               # 自动产物（可直接用于 RAG/Transfer/Mutation）
		parsed_examples/             # 结构化的示例（由 examples/*.txt 生成）
		parsed_examples_enriched/    # 带 expected 返回的示例（连 Redis 执行采集）
		command_cards_draft.json     # 由 g4 语法抽取的命令卡片草稿
		redis_commands_knowledge.json# 合并卡片+示例的统一知识库
		sql_to_redis_mapping.json    # SQL 语义到 Redis 的模式映射（供 RAG）

	README.md
```

## 生成脚本

- examples → parsed_examples
	- 脚本：`src/NoSQLKnowledgeBaseConstruction/Redis/examples_to_json.py`
	- 输入：`inputs/examples/*.txt`
	- 输出：`outputs/parsed_examples/*.json`

- 语法 g4 → 命令卡片草稿
	- 脚本：`src/NoSQLKnowledgeBaseConstruction/Redis/grammar_to_cards.py`
	- 输入：`inputs/grammars/RedisLexer.g4`、`inputs/grammars/RedisParser.g4`
	- 输出：`outputs/command_cards_draft.json`

- 合并卡片与示例 → 统一知识库
	- 脚本：`src/NoSQLKnowledgeBaseConstruction/Redis/merge_cards_and_examples.py`
	- 输入：`outputs/command_cards_draft.json` + `outputs/parsed_examples[_enriched]/*.json`
	- 输出：`outputs/redis_commands_knowledge.json`

- 采集 expected 返回（可选）
	- 脚本：`src/NoSQLKnowledgeBaseConstruction/Redis/enrich_examples_with_expected.py`
	- 输入：`outputs/parsed_examples/*.json`
	- 输出：`outputs/parsed_examples_enriched/*.json`
	- 依赖：本机 Redis（host/port 来自 `src/Tools/DatabaseConnect/database_connector_args.json`）

## 用途建议

- `outputs/redis_commands_knowledge.json` 与 `outputs/sql_to_redis_mapping.json`：
	- 作为 Transfer 的 RAG 检索源，指导 LLM 选择合适命令/结构、避免陷阱。
	- 作为 Mutation 的等价/包含关系依据（可在卡片中补充 invariants）。

- `outputs/parsed_examples_enriched/*.json`：
	- Few-shot 示例与评测基线；对含 `expected_error` 的条目进行过滤。

## 维护说明

- 新增命令示例：将 `.txt` 放入 `inputs/examples/`，运行 examples_to_json.py → merge_cards_and_examples.py。
- 更新语法：覆盖 `inputs/grammars/*.g4`，运行 grammar_to_cards.py → merge_cards_and_examples.py。
- 扩充映射：编辑 `outputs/sql_to_redis_mapping.json`（或迁移到 inputs/mapping 再由生成脚本复制到 outputs）。

## 致谢

- 初始 Redis 语法来源于第三方开源 grammar，版权归原作者所有；本仓库仅用于研究与工具链构建。
