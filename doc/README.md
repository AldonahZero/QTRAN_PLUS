# QTRAN 文档索引 (Enhanced Documentation Hub)

> 目标：作为统一入口，让新读者 5 分钟建立项目心智模型；老读者快速跳转到架构、运行、设计、知识库与微调材料。

---
## 0. 快速开始 (Quick Start)
```bash
# 1. 安装依赖 (建议 Python 3.11+)
pip install -r requirements.txt

# 2. 运行一个示例输入 (SQLancer 路径)
python -m src.main --input_filename "Input/demo1.jsonl" --tool "sqlancer"

# 3. 查看输出结构
ls -1 Output/demo1/
```
核心阶段：
1. Transfer：跨方言转换（源 a_db → 目标 b_db）+ 错误迭代修正
2. Mutation：在目标库上生成等价/相关变体，触发潜在引擎逻辑不一致
3. Oracle Check：比较变异前后结果，判定可疑 Bug

---
## 1. 文档地图 (Documentation Map)
| 主题 | 入口 | 内容摘要 |
|------|------|----------|
| 总览 / 愿景 | `doc/overview/README.md` | 项目目标、术语、顶层结构规划 |
| 核心流程详解 | `doc/abstract.md` | 端到端调用链 + 两阶段解析 |
| 运行指南 | `doc/guides/transfer_and_mutation_run_guide.md` | 输入格式、命令、产物目录说明 |
| 设计：知识/Oracle 策略 | `doc/design/transfer_and_mutation_knowledge_design.md` | Transfer vs Mutation 知识分层与 RAG 策略 |
| 设计：Redis→Mongo 映射 | `doc/design/redis_to_mongodb_conversion_summary.md` | 文档模型转换要点与注意事项 |
| KV/NoSQL 结果归一化 | `doc/kb/kv_nosql_return_structures.md` | Redis 为基准的多系统结果抽象与评分 |
| 差异对照（重构中） | `doc/redis_memcached_etcd_consul_diff.md` | 预留：更细的命令/协议对照（当前占位） |
| 微调：任务汇总 | `doc/finetune/fine_tuning_jobs_summary.md` | 已完成 / 计划中的微调作业一览 |
| 微调：Redis 变异 | `doc/finetune/redis_mutation_finetune.md` | 变异样本设计、标注与评估方向 |

---
## 2. 架构速览 (Architecture Snapshot)

```
Input JSONL --> TransferLLM --> Exec(Target DB) --(errors)--> Iterative Fix
      |                                              |
      v                                              v
  MutationLLM --------> Variant SQLs ----> Exec + Oracle ----> Suspicious Bugs
```

核心模块：
- `src/TransferLLM/`：跨方言转换与错误迭代
- `src/MutationLlmModelValidator/`：变异生成 + Bug 检测调度
- `src/Tools/DatabaseConnect/`：多数据库 / KV / NoSQL 执行（含 Redis / MongoDB / Memcached / etcd / Consul 归一化）
- `src/Tools/OracleChecker/`：结果比较逻辑
- `FeatureKnowledgeBase/` & `RAG_Feature_Mapping/`：特性语义 + 映射支撑

---
## 3. KV / NoSQL 归一化进展
已实现统一结果结构 `_unify_result`；当前支持：
| 系统 | 支持操作 | 归一化类型 (type) | 备注 |
|------|----------|------------------|------|
| Redis | 常见键/结构命令 | kv_* / structure_* | 原生命令解析 |
| Memcached | get/set/delete/incr/decr | kv_get / kv_set / kv_delete | TCP 文本协议解析 |
| etcd (v3) | PUT/GET/DELETE/RANGE | kv_set / kv_get / kv_delete / kv_range | `docker exec etcdctl -w json` + base64 解码 |
| Consul KV | PUT/GET/DELETE/RANGE | 同上 | HTTP API + base64 解码 |
| MongoDB | insert/find/update/delete | doc_* / kv_get (投影 value 时) | 仍使用专用执行函数，后续可迁移统一包装 |

待补（规划）：
- [ ] 事务型 (etcd txn) → `txn`
- [ ] MongoDB 结果统一封装 `_unify_result`
- [ ] 归一化 Equality 三态 (true/false/null + reason)

---
## 4. 典型目录结构与产物
```
Input/                # JSONL 输入（bug 报文 / SQL 序列）
Output/<case>/        # 每个输入集的输出根
  TransferLLM/        # 转换阶段记录
  MutationLLM/        # 变异阶段记录
  SuspiciousBugs/     # 预言机失败样本
FeatureKnowledgeBase/ # 关系型与 NoSQL 特性知识
RAG_Feature_Mapping/  # a_db→b_db 映射索引
MutationData/         # 微调与变异相关语料
src/                  # 主代码 (Transfer / Mutation / 执行 / Oracle)
```

---
## 5. 执行流关键接口 (Execution Hotspots)
| 入口 | 说明 |
|------|------|
| `src/main.py` | 参数解析 & 任务分发 |
| `transfer_llm()` | 构建 Prompt + LLM 转换 + 错误修正迭代 |
| `run_muatate_llm_single_sql()` | 变异生成入口 |
| `exec_sql_statement()` | 多数据库统一执行（含 NoSQL 路径分派） |
| `Check()` | 预言机判定逻辑 |

---
## 6. RAG 与知识使用策略摘要
| 阶段 | 主检索层 | 辅助层 | 目的 |
|------|----------|--------|------|
| Transfer 解析 | 源库特性 KB | 通用 SQL | 准确理解原语义 |
| 特征映射 | 映射表 | 源/目标 KB | 判定替换/降级策略 |
| 输出与修正 | 目标库 KB | 映射记录 | 生成 & 修正合法语句 |
| Mutation 生成 | Oracle 策略模板 | 目标库边界 KB | 构造等价/对照查询 |

---
## 7. 微调与数据 (Fine-tuning Highlights)
| 文件 | 作用 |
|------|------|
| `finetune/fine_tuning_jobs_summary.md` | 历史与排期追踪 |
| `finetune/redis_mutation_finetune.md` | Redis 变异策略与样本设计 |
| `MutationData/FineTuningTrainingData/` | 训练样本主目录 |
| `MutationData/MutationLLMPrompt/` | Prompt 模板集合 |

改进机会：
- 统一样本 schema 版本标记
- 加入失败修复样本闭环
- 自动统计脚本生成 dataset_stats

---
## 8. 后续文档 Roadmap
| 计划 | 优先级 | 说明 |
|------|--------|------|
| architecture.svg | 中 | 补充高层数据流图 |
| result_normalization.md | 高 | 将代码实现与抽象映射补全（已部分实现） |
| quickstart.md | 高 | 面向新用户的 5 分钟教程 |
| troubleshooting.md | 高 | 常见运行/容器/权限错误指引 |
| glossary.md | 中 | 统一术语，避免歧义 |
| error_iteration_strategy.md | 中 | 错误分类与修正规则体系化 |

---
## 9. FAQ 精选
| 问题 | 答案 |
|------|------|
| 支持哪些数据库? | 关系型: MySQL / MariaDB / TiDB / Postgres / SQLite / DuckDB / ClickHouse / MonetDB；NoSQL: Redis / MongoDB；KV: Memcached / etcd / Consul |
| 一条输入可能生成多条目标 SQL 吗? | 是，Transfer 阶段可能生成候选版本并择优执行。 |
| 如何判断 Bug? | 通过 Oracle Check，对比原/变异查询结果逻辑关系是否符合预期。 |
| 为何要错误迭代? | 降低 LLM 第一次转换失败率，利用执行错误上下文做定向修复。 |
| 可跳过 Docker 吗? | 可设置 `QTRAN_SKIP_DOCKER=1`（需外部 DB 自行准备）。 |

---
## 10. 贡献指引 (Contribution Quick Hints)
1. 新增数据库：扩展 `database_connector_args.json` + `exec_sql_statement` 分派。
2. 新增 Oracle 策略：添加变异模板 + 在 Mutation 阶段挂载判断逻辑。
3. 新增特性映射：在 `RAG_Feature_Mapping/<Dialect>/` 下补充 JSON/表格。
4. 补文档：保持章节编号与导航表更新。
5. 性能调优：关注执行缓存、重复 RAG 调用去重、etcd/consul 进程复用。

---
**如果你正首次浏览仓库，建议阅读顺序：**
1. `doc/abstract.md`
2. `doc/guides/transfer_and_mutation_run_guide.md`
3. `doc/design/transfer_and_mutation_knowledge_design.md`
4. `doc/kb/kv_nosql_return_structures.md`
5. 代码入口：`src/main.py`

欢迎提出改进建议！
