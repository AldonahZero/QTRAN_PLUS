# QTRAN 运行与产物说明

本文档解释 QTRAN 的输入文件 `Input/demo1.jsonl` 在 SQLancer 路径下如何被处理，以及如何运行和查看中间/最终产物。

## 概览
QTRAN 的主要流程分为两阶段：

1. Transfer（转换）阶段：将源数据库（a_db）上的 SQL 翻译为目标数据库（b_db）方言，并尝试在目标库执行。失败时进行错误迭代修正。
2. Mutation（变异）阶段：对已成功转换的 SQL 生成变体（由变异 LLM），在目标库执行，并用预言机（Oracle Check）比较变前/变后结果以检测逻辑错误。

## 输入文件格式
输入为 JSONL 文件（每行一个 JSON 对象），范例：

```json
{  
  "index": 0,  
  "a_db": "sqlite",  
  "b_db": "clickhouse",  
  "molt": "norec",  
  "sqls": [  
    "CREATE TABLE t0(c0 INT UNIQUE);",  
    "INSERT INTO t0(c0) VALUES (1);",  
    "SELECT COUNT(*) FROM t0 WHERE '1' IN (t0.c0); -- unexpected: fetches row"  
  ]  
}
```

`Input/demo1.jsonl` 是示例输入，程序会按行读取并处理每个 JSON 对象。

## 执行命令（示例）

在项目根目录运行：

```bash
python -m src.main --input_filename "Input/demo1.jsonl" --tool "sqlancer"
```

常用选项：
- `--temperature`：LLM 温度（默认 0.3）
- `--model`：LLM 模型（默认 gpt-4o-mini）
- `--error_iteration`：是否开启错误迭代（默认 True）
- `--iteration_num`：最大迭代次数（默认 4）

## 可选环境变量（快速模式）
- `QTRAN_SKIP_DOCKER=1`：跳过 Docker 容器与数据库的创建/启动（用于只想验证流程或已有外部数据库时）。
- `QTRAN_VALIDATE_ONLY=1`：仅检查输入文件存在并创建必要的目录结构（如果仓库实现了该校验开关）。

## 处理逻辑（高层）
1. `main.py` 解析命令并调用 `qtran_run()`。
2. `qtran_run()`（默认）会调用 `docker_create_databases()` 为各数据库准备容器（若未设置 `QTRAN_SKIP_DOCKER=1`）。
3. 针对 `sqlancer`：`sqlancer_qtran_run()` -> `sqlancer_translate()`：
   - 将 `Input/demo1.jsonl` 中每个 bug 报文拆成单条 SQL 并写入 `Input/<inputname>/<index>.jsonl`。
   - 对每个 SQL 调用 `transfer_llm()`，对指定的目标库执行转换后的 SQL；记录执行结果、错误信息、时间、成本等。
   - 转换成功会写入 `Output/<inputname>/TransferLLM/<index>.jsonl`。
4. 对成功转换的语句，调用变异流程（MutationLLM）：生成变异 SQL 并执行。
5. 将变异前/后的执行结果交给预言机 `Check()` 判断。若 `Check()` 返回 `end=False`（且 `error` 为 `None`），则被视为可疑的逻辑 Bug，并写入 `Output/<inputname>/SuspiciousBugs/`。

## 产物路径（关键）
- 单条处理后的输入： `Input/<inputname>/<index>.jsonl`
- 转换结果（Transfer LLM）： `Output/<inputname>/TransferLLM/*.jsonl`
- 变异结果（Mutation LLM）： `Output/<inputname>/MutationLLM/*.jsonl`
- 可疑 Bug 列表： `Output/<inputname>/SuspiciousBugs/*.jsonl`（每个文件包含该 bug 的核心信息）
- 汇总报告（若已生成）： `Output/<inputname>/eval_report.json`

## 如何查看某条 SQL 的执行目标
每个 `Output/<inputname>/TransferLLM/<index>.jsonl` 文件里包含该 bug 的处理记录，字段示例：
- `a_db`：源数据库
- `b_db`：目标数据库
- `SqlExecResult` / `SqlExecError`：原始 SQL 在 a_db 的执行结果/错误
- `TransferResult`：LLM 生成的目标 SQL 列表及对应执行结果

通过查看 `TransferResult` 中的 `TransferSQL` 字段可以知道 LLM 生成并被尝试在哪个目标库执行。

## 常见问题
- Q：会在所有数据库上逐一执行吗？
  - A：不会。每条 bug 报文里会明确 `a_db` 和 `b_db`，流程只针对指定的目标库进行转换与执行。

- Q：如何仅生成报告而不重新运行流程？
  - A：可以使用仓库中新增的评估汇总函数（如果实现），或手动读取 `Output/<inputname>/MutationLLM` 与 `Output/<inputname>/SuspiciousBugs` 并生成报告。

## 快速检查命令
```bash
# 查看 transfer 输出
ls -l Output/demo1/TransferLLM
# 查看 mutate 输出
ls -l Output/demo1/MutationLLM
# 查看可疑 bug
ls -l Output/demo1/SuspiciousBugs
# 如果存在，直接打印 eval 报告
cat Output/demo1/eval_report.json
```

---

文件已保存到： `doc/transfer_and_mutation_run_guide.md`。

需要我现在自动生成 `Output/demo1/eval_report.json`（如果有现成的产物），并把内容贴在这里吗？
