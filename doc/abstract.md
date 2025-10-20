# **QTRAN 项目核心流程详解**

## **一、 核心目标**

QTRAN项目的核心目标是实现一个自动化的数据库逻辑错误检测流程。它通过以下三个关键步骤，将针对单一数据库的测试能力扩展到多种数据库：

1. **转换 (Transfer)**：接收一个为源数据库（如 SQLite）设计的SQL语句，并利用大语言模型（LLM）将其准确地转换为目标数据库（如 ClickHouse）的SQL方言。  
2. **变异 (Mutation)**：对成功转换后的SQL语句进行逻辑上等价或相关的微小改动，生成一组新的测试查询。  
3. **预言机检查 (Oracle Check)**：同时执行变异前和变异后的SQL查询，并比较它们的执行结果。如果结果不符合预定义的逻辑关系（即“预言机”），则标志着发现了一个潜在的数据库逻辑错误（Bug）。

整个流程被清晰地划分为两大阶段：**转换阶段 (Transfer Phase)** 和 **变异与检测阶段 (Mutation & Bug Detection Phase)**。

## **二、 调用链概览**

程序的执行流程由一系列核心模块和函数驱动：

* **main.py**: **程序的入口**。负责解析命令行参数并启动整个流程。  
* **qtran\_run()**: main.py 中的主函数，根据用户指定的工具（sqlancer 或 pinolo）选择不同的执行路径。  
* **sqlancer\_qtran\_run() / pinolo\_qtran\_run()**: 分别处理来自不同源工具的逻辑，是转换流程的起点。  
* **transfer\_llm()** (src/TransferLLM/TransferLLM.py): **转换阶段的核心**。调用LLM，负责将SQL语句从源方言翻译为目标方言，并包含错误迭代修正机制。  
* **run\_muatate\_llm\_single\_sql()** (src/MutationLlmModelValidator/MutateLLM.py): **变异阶段的核心**。调用一个经过微调的LLM，对转换后的SQL进行智能变异。  
* **process\_mutate\_llm\_result()** (src/MutationLlmModelValidator/MutateLLM.py): 负责执行原始SQL和变异SQL，并收集它们的执行结果。  
* **Check()** (src/Tools/OracleChecker/oracle\_check.py): **预言机检查的核心**。扮演“裁判”的角色，比较两个SQL结果集，判断数据库行为是否符合预期。  
* **detect\_bug()** (src/MutationLlmModelValidator/MutateLLM.py): 负责汇总所有检查结果，如果不满足预言机，则记录为一个可疑的Bug。

## **四、Transfer 与 Mutate 的行为要点、风险与工程建议**

下面把我们在实现中观察到的行为、带来的利弊和可落地的改进建议写清楚，便于后续维护与调整：

### 1) 核心行为回顾
- transfer 阶段在 `src/TransferLLM/TransferLLM.py` 中执行：会把原始 SQL 在目标 DB 上执行以获得 `origin_exec_result`，将 LLM 生成的每个候选 `TransferSQL` 在目标库上执行并记录执行结果，同时维护 `exec_equalities`（表示每个候选是否与原始执行结果等价）。
- translate 层（`src/TransferLLM/translate_sqlancer.py`）会把 `transfer_llm` 的返回值保存到 `info` 中（字段如 `TransferResult`、`TransferSqlExecResult`、`TransferSqlExecEqualities`）。
- mutate 阶段以“翻译后的语句（TransferResult 中最后一次可提取的语句）”为基准：先执行该 `before_mutate`，再执行变异生成的 `after_mutate`，并把二者的执行结果传入 `Check()` 做 Oracle 判断（结果保存在 `OracleCheck` 字段）。

### 2) 当前默认策略（仓库里已实现的行为）
- 宽松策略：只要存在 `TransferResult`（即使 `exec_equalities` 全为 False，表示语义不等价），`translate_sqlancer.py` 仍会把最后一次 `TransferResult` 送到变异阶段并进行变异与比较。也就是说变异比较的对象是 `before_mutate`（翻译后） vs `after_mutate`（变异后），而不是直接与“翻译前的原始 SQL”的执行结果比较。
- 当最后一次 `TransferResult` 为空或无法提取时（即转换全部尝试都失败），变异阶段会跳过该用例（不会调用变异）。

### 3) 这样做的意义与局限
- 意义：对于发现目标 DB 的崩溃、未处理异常或鲁棒性问题（crash/hang/异常路径），宽松策略有较高覆盖率——即便翻译并不完全等价，基于翻译后的语句做变异仍可能触发实现缺陷。
- 局限：若目标是发现“严格的语义等价缺陷”（即转换后语义应与原始语义一致但不一致），宽松策略会带来大量噪声（假阳性），因为差异可能来自翻译本身而非目标实现的逻辑错误。定位根因也更困难。

### 4) 推荐的工程策略（可选实现）
下面按风险/收益列出可选策略，便于按目标选择：

- 严格模式（高精度，低噪声）
   - 仅当 `TransferSqlExecEqualities` 中存在至少一个 True（说明存在等价候选）时，才把该候选交给变异；否则跳过并记录 `transfer_fail` 原因。
   - 实现点：在 `src/TransferLLM/translate_sqlancer.py` 的 mutate 阶段，加入对 `TransferSqlExecEqualities` 的检查并决定是否继续变异。

- 标记并同时变异（兼顾覆盖）
   - 对等价候选正常变异；若无等价候选，则仍变异但给该结果标记 `transfer_confidence: low`，后续在 `getSuspicious` 或输出汇总时把低置信度结果单独分类供人工复核。
   - 实现点：在传给 `run_muatate_llm_single_sql` 时附加 `transfer_confidence`，并在 `MutateLLM.py` 中持久化该字段。

- 折衷优先回退（推荐的折衷方案）
   - 优先选择被判为等价的候选做变异；若没有等价候选，回退到“最后一个非空候选”并标注低置信度，然后继续变异。
   - 优点是兼顾了变异覆盖与降低噪声。

### 5) 小型改动建议（立即可落地）
- 在 `translate_sqlancer.py` 的 mutate 开始处加入一段逻辑：优先查找 `TransferSqlExecEqualities` 中的 True 候选并使用；若找不到则从 `TransferResult` 中选最后一个非空候选并在上下文中打标（`transfer_confidence: low`），如果所有候选都为空再跳过变异。
- 在 `MutateLLM.py` 中把收到的 `transfer_confidence` 写入变异输出（JSON），并在 `getSuspicious` 或报告中把低置信度项单独汇总。

### 6) 总结
- 如果目标是“尽量多发现潜在崩溃/鲁棒性问题”，保持当前宽松策略并且对低置信度项做标注与单独统计是合适的。
- 如果目标是“高置信度、低噪声地定位语义级别的逻辑 bug”，建议采用严格模式或折衷优先回退策略。

如需我现在把其中一种策略（严格 / 标记并变异 / 折衷回退）实现到代码中并做一次单用例验证，我可以直接修改 `src/TransferLLM/translate_sqlancer.py`（以及必要时修改 `src/MutationLlmModelValidator/MutateLLM.py`）并跑基础静态检查与示例运行。请告诉我你想要哪个策略，我会立刻实现并提交补丁。

## **三、 详细数据转换流程**

### **阶段一：转换 (Transfer Phase)**

此阶段的目标是将输入的SQL语句准确地翻译成目标数据库的方言，并确保其可执行。

1. **启动与分发 (main.py)**:  
   * 程序从 main() 函数启动，解析用户输入的参数，如输入文件名 (--input\_filename) 和源工具名 (--tool)。  
   * qtran\_run() 函数根据 \--tool 的值将任务分发给相应的处理函数。  
2. **数据加载与准备 (以 pinolo 为例, TransferLLM.py)**:  
   * load\_data(): 从数据集中加载由源工具（如Pinolo）生成的原始SQL语句对。  
   * init\_data(): 将加载的SQL数据构造成包含索引、长度等元信息的JSON对象，为后续处理做准备。  
3. **核心转换 (transfer\_llm in TransferLLM.py)**:  
   * **构建提示 (Prompt)**: 这是与LLM交互的关键。程序会构建一个包含多重信息的详细Prompt：  
     * **转换指令**: 明确告知LLM转换的目标和要求（如保持列名不变）。  
     * **特征知识库**: 提供源数据库和目标数据库在特定函数或语法上的差异和示例，引导LLM进行更准确的转换。  
     * **Few-Shot示例**: 给出一些已完成的转换范例，帮助LLM更好地理解任务。  
   * **调用LLM**: 将构建好的Prompt发送给大语言模型（如 GPT-4o-mini）以获取转换结果。  
   * **错误迭代**: 如果LLM返回的SQL在目标数据库上执行失败，程序会将错误信息 (error\_message) 再次发送给LLM，要求其根据错误进行修正。此过程会循环，直到SQL可以成功执行或达到最大迭代次数。  
   * **结果记录**: 详细记录每次转换尝试的SQL、执行结果、时间、成本和错误信息。

### **阶段二：变异与检测 (Mutation & Bug Detection Phase)**

在获得可成功执行的SQL后，此阶段通过微小的改动来探测数据库的逻辑一致性。

1. **调用变异LLM (run\_muatate\_llm\_single\_sql in MutateLLM.py)**:  
   * 函数接收在第一阶段成功转换的SQL。  
   * 根据预设的变异策略（如 norec, tlp），加载相应的系统提示。  
   * 将提示和SQL语句一同发送给一个专门用于SQL变异的微调LLM。  
2. **处理变异结果 (process\_mutate\_llm\_result in MutateLLM.py)**:  
   * 遍历由变异LLM生成的所有SQL语句。  
   * 对每一条变异SQL，执行它并记录结果。同时，也执行变异前的SQL作为比较基准。  
   * 将两个结果集传递给 Check() 函数进行预言机检查。  
3. **预言机检查 (Check in oracle\_check.py)**:  
   * 这是逻辑错误检测的裁决步骤。Result.cmp() 方法会精确比较两个结果集的关系（相等、子集、超集等）。  
   * Check() 函数根据比较结果和预期的逻辑关系，判断数据库的行为是否正确。例如，如果预期结果相等但实际不相等，则检查失败。  
4. **Bug汇总 (detect\_bug in MutateLLM.py)**:  
   * 在所有测试用例运行后，此函数会分析预言机检查的结果。  
   * 如果 CheckOracle 字段显示检查失败 (end 为 False)，则认为发现了一个逻辑Bug，并记录其索引。  
   * 最终输出一份包含变异成功率和可疑Bug列表的评估报告。

### 可选：仅在变异阶段启用 Agent（方案 2）

从现在起，变异阶段支持通过轻量的 LangChain Agent 生成 3-5 个候选变异并进行基本语法自检。默认仍使用微调 LLM；若要启用 Agent，请设置环境变量：

```
export QTRAN_MUTATION_ENGINE=agent
```

启用后，`src/MutationLlmModelValidator/MutateLLM.py` 中的 `run_muatate_llm_single_sql` 将优先走 Agent 路径；若 Agent 失败，会自动回退到微调 LLM 路径，保持兼容性。