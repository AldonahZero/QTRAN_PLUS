# Redis → PostgreSQL 翻译与变异总结

## 1. 背景
本阶段实现了将 Redis 命令（示例集中为：`SET / ZADD / SORT / ZRANDMEMBER / GET`）转换为具有相近语义的 PostgreSQL SQL 语句，并对翻译后的 SQL 进行变异（当前使用 `norec` 思路的布尔表达式求和形式）。所有示例均保持既有列名（如：`mykey` / `score` / `member`），且禁止引入除 `tab_0`、`tab_1` 外的新表名。

## 2. 数据建模与表约定
| Redis 概念 | PostgreSQL 映射 | 说明 |
|------------|----------------|------|
| KV (`SET key value`) | `tab_0(mykey TEXT)`（示例）或泛化为 `tab_0(key,text_value)` | 目前示例直接用键名当列，简单但不通用 |
| 有序集合 (`ZADD key score member`) | `tab_1(score INTEGER, member TEXT)` | 忽略集合名（如：`lukpltvt`），统一落到 tab_1 |
| 随机成员 (`ZRANDMEMBER key WITHSCORES`) | `SELECT member, score FROM tab_1 ORDER BY RANDOM() LIMIT 1;` | 利用随机排序模拟随机获取 |
| 排序 (`SORT key`) | `SELECT member FROM tab_1 ORDER BY score;` | 假设按 score 排序成员 |
| 获取值 (`GET key`) | `SELECT mykey FROM tab_0;` | 直接列投影（假设列即 key） |

> 现实现采用“结构最小 + 任务驱动”策略，未引入通用 schema（例如统一 key/value 表）。后续可抽象映射层。

## 3. 翻译规则摘要
| Redis 命令 | 翻译策略 | 示例 |
|------------|----------|------|
| SET k v | 若表不存在：`CREATE TABLE IF NOT EXISTS tab_0 (mykey TEXT); INSERT ...` | `SET mykey hello;` → `CREATE TABLE IF NOT EXISTS tab_0 (...); INSERT INTO tab_0 (mykey) VALUES ('hello');` |
| ZADD k s m | 同上，插入一行 | `ZADD lukpltvt 5826 vgjrzjoy;` → `CREATE TABLE IF NOT EXISTS tab_1 (score INTEGER, member TEXT); INSERT INTO tab_1 (score, member) VALUES (5826, 'vgjrzjoy');` |
| SORT k | 读取并按 score 排序 | `SORT lukpltvt;` → `SELECT member FROM tab_1 ORDER BY score;` |
| ZRANDMEMBER k WITHSCORES | 随机一行 | `ZRANDMEMBER lukpltvt -9223... WITHSCORES;` → `SELECT member, score FROM tab_1 ORDER BY RANDOM() LIMIT 1;` |
| GET k | 读取列 | `GET mykey;` → `SELECT mykey FROM tab_0;` |

## 4. 变异（Mutation）机制观察
示例（`/Output/redis_demo_02/MutationLLM/22.jsonl`）中对翻译后的：
```
SELECT mykey FROM tab_0;
```
生成变异 SQL：
```
SELECT SUM(count)
FROM (
  SELECT (mykey) IS TRUE AS count
  FROM tab_0
) AS res;
```
执行失败错误：
```
(psycopg2.errors.DatatypeMismatch) argument of IS TRUE must be type boolean, not type text
```

### 问题原因
`mykey` 为 TEXT，直接 `(mykey) IS TRUE` 不合法。

### 改进建议
1. 统一生成可布尔化表达式：  
   - 文本列：`(mykey IS NOT NULL AND mykey <> '')`
   - 数值列：`(col IS NOT NULL)`
2. norec 变形模板建议参数化：  
   ```
   SELECT SUM(flag) FROM (
       SELECT (/* BOOL_EXPR */) :: int AS flag
       FROM tab_0
   ) t;
   ```
3. 避免对不支持布尔上下文的列直接加 `IS TRUE`。

## 5. 日志节选（索引 22）
- 翻译链条完整：原始 Redis → 翻译 SQL → 执行结果 → 变异 SQL → 变异执行失败 → 记录 `MutateSqlExecError`
- 多步翻译中针对“表不存在”自动补全 `CREATE TABLE IF NOT EXISTS ...`（第二次尝试成功）

## 6. 已发现的语义与工程风险
| 问题 | 描述 | 建议 |
|------|------|------|
| 表名/列名过拟合 | `mykey` 被当成列名 | 引入统一 schema：`tab_0(key TEXT, val TEXT)` |
| 忽略 Redis key 维度 | 多个不同 key 会互相覆盖语义 | 添加 key 列 |
| Z 集合未区分集合名 | `lukpltvt` 丢失 | 增加 set_name 列 |
| 随机性不可重现 | `ORDER BY RANDOM()` | 可用 `TABLESAMPLE` / 受控随机或禁止随机 |
| 变异布尔表达式非法 | 直接 IS TRUE | 使用安全模板 |
| 多语句合并执行 | `CREATE TABLE ...; INSERT ...;` | 拆分，逐条执行并捕获错误 |
| 负数 count 参数 | `ZRANDMEMBER` 负数报错 | 预解析校验并降级处理 |

## 7. 未来工作路线
1. 引入 Redis→关系模型抽象层（元数据驱动）
2. 支持更多命令族（HASH / LIST / SET / EXPIRE）
3. 规范多语句拆分执行与回滚策略
4. 变异阶段结构化策略库（按列类型选择模板）
5. 随机相关命令引入伪随机种子控制
6. 评估语义等价性判定：结果集对比 + 归一化（排序、NULL 处理）

## 8. 快速检查清单
- 未生成新表名（只用 tab_0 / tab_1）
- 未引入无意义常量（NULL, 0, RANDOM() 仅在必要语义下使用）
- 列名未改写
- 多语句已正确分隔
- 变异语句保证类型安全

## 9. 结论
Redis → PostgreSQL 的最小可行翻译与基础变异已跑通；当前瓶颈主要在：
- 语义抽象不足（集合 / key 维度丢失）
- 变异布尔表达式类型不安全
后续需通过抽象建模与模板化提升稳定性与扩展性。