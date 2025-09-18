## Transfer 与 Mutation 阶段知识/Oracle 使用设计

本文档回答两个核心问题：

1. Transfer（转换）阶段到底用 a_db 还是 b_db 的知识库？
2. Mutation（变异）阶段中指定的 molt（norec / tlp / pinolo / dqe 等）与微调模型侧重 a 还是 b 的特性？

---

## 1. Transfer 阶段：知识库使用策略

目标：将源 SQL（a_db 方言 + 语义特性）正确、保守地“落地”到目标数据库 b_db（语法 / 语义 / 行为差异）。

不是简单选 a_db 或 b_db，而是“分层组合”：

| 作用环节 | 主要依赖 | 补充依赖 | 目的 |
|----------|----------|----------|------|
| 语句解析 / 特征抽取 | a_db 知识库（语法元素、数据类型、函数/操作符语义） | 通用 SQL 规范 | 正确理解源语义，避免漏掉方言特性 |
| 特征映射（feature mapping） | 映射表（`RAG_Feature_Mapping/a→b`） | a_db 与 b_db 各自 KB | 判定元素：直接对应 / 需重写 / 不可保留 |
| 目标重写 & 约束验证 | b_db 知识库（语法、限制、保留字、行为差异） | a_db KB（用于解释原意决定降级与否） | 生成语法合法且语义尽量等价（或安全降级）的目标 SQL |
| 错误迭代修正 | b_db 执行反馈 + b_db KB（错误模式→修正规则） | 映射知识（验证替代方案） | 针对执行错误做定向修正再试 |

简化认知：
* “理解阶段”偏向 a_db
* “输出阶段”偏向 b_db
* “桥梁”是映射（Feature / Operator / Function 对应 + 不可达说明）
* 错误迭代聚焦 b_db 错误语义（类型精度、大小写敏感、隐式转换、NULL 行为、分组/聚合等）

### 推荐处理序列（实现步骤）
1. 解析源 SQL：抽取数据类型、函数/操作符、关键子句（LIMIT / OFFSET / WINDOW / HINT）、方言扩展（如 SQLite `WITHOUT ROWID`、MySQL `ENGINE=InnoDB`）。
2. 映射分类：Direct / Alias / Composite / Emulate / Drop(降级) / Unsupported。
3. Composite / Emulate：插入模板（例：无 `ILIKE` → `LOWER(col) LIKE LOWER(pat)`）。
4. 约束检查：保留字冲突、标识符大小写、字符串拼接符、布尔字面量（TRUE vs 1）、时间函数、隐式转换风险。
5. 生成候选版本（可多条）→ 排序：最少语义退化 > 兼容度最强 > 结构最简单。
6. 执行 + 错误回溯：错误分类（正则 / embedding）→ 修正规则 → 重试。

---

## 2. Mutation 阶段：molt（Oracle 策略）与模型侧重点

molt（`MutationData/FineTuningTrainingData` 中的 norec / tlp / dqe / pinolo 等）表示“逻辑漏洞检测预言机策略”，不是数据库身份标签。

Mutation 阶段特征：
* 执行环境：b_db（目标库）
* 变异生成的 SQL：在 b_db 上运行，与原始或结构等价版本比对结果
* 微调 Mutation 模型 & 模板：聚焦 b_db 的内部行为特性（优化器、NULL、类型、聚合、边界值）

对比：
* Transfer LLM：跨方言迁移（关注 a→b 映射）
* Mutation LLM：b_db 内部“等价 / 期望等价”结构变换，诱发执行不一致

### 常见 Oracle 关注点
| Oracle (molt) | 核心思想 | 需聚焦的 b_db 特性示例 |
|---------------|----------|-------------------------|
| norec (NoREC) | 聚合/枚举改写对比计数或布尔 | COUNT vs SUM(CASE …)、聚合稳定性、NULL 传播 |
| tlp (三值逻辑) | P / NOT P / P IS NULL 拆分 | NULL 语义、`IS` vs `=`、谓词过滤行为 |
| pinolo / 行重写类 | 等价谓词 / JOIN / 子查询结构替换 | 操作符优先级、JOIN 类型、半/反连接语义 |
| dqe (等价表达) | 表达式等价重写 | 恒等变换、隐式类型转换规则 |

为何不再依赖 a_db：此时 SQL 已是 b_db 方言；目标是发现 b_db 引擎内部不一致。a_db 知识仅偶尔用于保留/标注背景，不主导变异。

---

## 3. 知识检索（RAG）分层建议

| 层 | 检索 Query 构造 | 返回内容 | 使用阶段 |
|----|----------------|----------|----------|
| Source 语义层 | 源函数/类型/关键子句特征 | a_db Feature KB | Transfer 解析与分类 |
| 映射桥接层 | (a_feature, target=b_db) | Mapping KB (`RAG_Feature_Mapping`) | Transfer 重写 |
| Target 约束层 | 目标语法节点组合 (例: LIMIT+OFFSET) | b_db Feature KB | Transfer 校验 + 迭代 |
| Mutation Oracle 层 | oracle 名 + 结构特征 (谓词/聚合/窗口) | 预训练/微调模板 & 语料 | Mutation 生成 |
| Edge / Boundary 层 | 目标库边界值描述 | b_db 数值/时间/排序/字符集 KB | Mutation 边界注入 |

---

## 4. Mutation 微调数据构建原则

| 分类 | 说明 | 示例 |
|------|------|------|
| Pair 等价集 | (原, 结构变体, 期望等价) | `SELECT COUNT(*) FROM t` ↔ `SELECT SUM(1) FROM t` |
| Boundary 触发 | 注入极值 / 溢出常量 | `WHERE c < 9223372036854775807` |
| Null / 三值逻辑 | TLP 模板拆分 | `WHERE P` → `P` / `NOT P` / `P IS NULL` |
| 聚合替换 | COUNT/SUM/MIN/MAX 交换、去 DISTINCT | 优化器稳定性测试 |
| Join/Subquery 重写 | IN ↔ EXISTS, JOIN 重组 | 语义保持对照 |

标注重点：
* 标记 等价 / 期望等价 / 非等价（故意破坏）
* 包含失败样本（语法/语义错误）帮助模型学习规避

---

## 5. 目标不支持源特性的策略

| 情况 | 策略 | 举例 |
|------|------|------|
| 目标无该函数 | 降级模拟 | `IFNULL(x,y)` → `COALESCE(x,y)` |
| 语义近似但行为差异 | 注释 + 显式转换 | NULL 排序差异：补 `ORDER BY col IS NULL` |
| 无法可靠模拟 | 标记 & 跳过 / 拆分 | 复杂窗口在旧版本不支持 |
| 类型精度差异 | CAST + 注释 | `DECIMAL(65,30)` → `DECIMAL(38,30) /* truncated */` |

Mutation 阶段避免再引入“源侧不可达语义补偿”，防止逻辑偏移。

---

## 6. 核心结论摘要

* Transfer：同时用 a_db 与 b_db 知识；真正输出与迭代围绕 b_db；a_db 用于语义理解 + 特征标注 + 映射输入。
* Mutation：molt 策略与微调模型聚焦 b_db 内部行为（优化器、NULL、边界、类型）；目标是在 b_db 内部构造“期望等价”对照引出不一致。

---

## 7. 可扩展落地建议（后续可加）

1. 引入错误分类器（正则 + 嵌入）> 动态修正规则优先级队列。
2. Feature 映射缓存：相同源特征跨多条语句重用映射结果，减少重复 RAG 调用。
3. 变异多层门控：语法 -> 语义（AST 正常性） -> 结果稳定性（多次执行一致） -> 覆盖增量。
4. Oracle 策略选择器：基于语句形态（是否含聚合/谓词/子查询）动态挑选 norec / tlp / dqe。
5. 边界值库分级：通用（2^31±1,2^63±1）+ 类型特有（日期上下界、浮点特性）。
6. 失败语料回灌微调：将高频失败模式（解析失败 / 逻辑破坏）抽样加入下一轮训练。

---

文件自动生成：`doc/transfer_and_mutation_knowledge_design.md`
