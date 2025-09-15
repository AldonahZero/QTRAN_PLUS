QTRAN 项目核心流程详解
一、 核心目标
QTRAN项目的核心目标是实现一个自动化的数据库逻辑错误检测流程。它通过以下三个关键步骤，将针对单一数据库的测试能力扩展到多种数据库：

转换 (Transfer)：接收一个为源数据库（如 SQLite）设计的SQL语句，并利用大语言模型（LLM）将其准确地转换为目标数据库（如 ClickHouse）的SQL方言。

变异 (Mutation)：对成功转换后的SQL语句进行逻辑上等价或相关的微小改动，生成一组新的测试查询。

预言机检查 (Oracle Check)：同时执行变异前和变异后的SQL查询，并比较它们的执行结果。如果结果不符合预定义的逻辑关系（即“预言机”），则标志着发现了一个潜在的数据库逻辑错误（Bug）。

整个流程被清晰地划分为两大阶段：转换阶段 (Transfer Phase) 和 变异与检测阶段 (Mutation & Bug Detection Phase)。

二、 调用链概览
程序的执行流程由一系列核心模块和函数驱动：

main.py: 程序的入口。负责解析命令行参数并启动整个流程。

qtran_run(): main.py 中的主函数，根据用户指定的工具（sqlancer 或 pinolo）选择不同的执行路径。

sqlancer_qtran_run() / pinolo_qtran_run(): 分别处理来自不同源工具的逻辑，是转换流程的起点。

transfer_llm() (src/TransferLLM/TransferLLM.py): 转换阶段的核心。调用LLM，负责将SQL语句从源方言翻译为目标方言，并包含错误迭代修正机制。

run_muatate_llm_single_sql() (src/MutationLlmModelValidator/MutateLLM.py): 变异阶段的核心。调用一个经过微调的LLM，对转换后的SQL进行智能变异。

process_mutate_llm_result() (src/MutationLlmModelValidator/MutateLLM.py): 负责执行原始SQL和变异SQL，并收集它们的执行结果。

Check() (src/Tools/OracleChecker/oracle_check.py): 预言机检查的核心。扮演“裁判”的角色，比较两个SQL结果集，判断数据库行为是否符合预期。

detect_bug() (src/MutationLlmModelValidator/MutateLLM.py): 负责汇总所有检查结果，如果不满足预言机，则记录为一个可疑的Bug。

三、 详细数据转换流程
阶段一：转换 (Transfer Phase)
此阶段的目标是将输入的SQL语句准确地翻译成目标数据库的方言，并确保其可执行。

启动与分发 (main.py):

程序从 main() 函数启动，解析用户输入的参数，如输入文件名 (--input_filename) 和源工具名 (--tool)。

qtran_run() 函数根据 --tool 的值将任务分发给相应的处理函数。

数据加载与准备 (以 pinolo 为例, TransferLLM.py):

load_data(): 从数据集中加载由源工具（如Pinolo）生成的原始SQL语句对。

init_data(): 将加载的SQL数据构造成包含索引、长度等元信息的JSON对象，为后续处理做准备。

核心转换 (transfer_llm in TransferLLM.py):

构建提示 (Prompt): 这是与LLM交互的关键。程序会构建一个包含多重信息的详细Prompt：

转换指令: 明确告知LLM转换的目标和要求（如保持列名不变）。

特征知识库: 提供源数据库和目标数据库在特定函数或语法上的差异和示例，引导LLM进行更准确的转换。

Few-Shot示例: 给出一些已完成的转换范例，帮助LLM更好地理解任务。

调用LLM: 将构建好的Prompt发送给大语言模型（如 GPT-4o-mini）以获取转换结果。

错误迭代: 如果LLM返回的SQL在目标数据库上执行失败，程序会将错误信息 (error_message) 再次发送给LLM，要求其根据错误进行修正。此过程会循环，直到SQL可以成功执行或达到最大迭代次数。

结果记录: 详细记录每次转换尝试的SQL、执行结果、时间、成本和错误信息。

阶段二：变异与检测 (Mutation & Bug Detection Phase)
在获得可成功执行的SQL后，此阶段通过微小的改动来探测数据库的逻辑一致性。

调用变异LLM (run_muatate_llm_single_sql in MutateLLM.py):

函数接收在第一阶段成功转换的SQL。

根据预设的变异策略（如 norec, tlp），加载相应的系统提示。

将提示和SQL语句一同发送给一个专门用于SQL变异的微调LLM。

处理变异结果 (process_mutate_llm_result in MutateLLM.py):

遍历由变异LLM生成的所有SQL语句。

对每一条变异SQL，执行它并记录结果。同时，也执行变异前的SQL作为比较基准。

将两个结果集传递给 Check() 函数进行预言机检查。

预言机检查 (Check in oracle_check.py):

这是逻辑错误检测的裁决步骤。Result.cmp() 方法会精确比较两个结果集的关系（相等、子集、超集等）。

Check() 函数根据比较结果和预期的逻辑关系，判断数据库的行为是否正确。例如，如果预期结果相等但实际不相等，则检查失败。

Bug汇总 (detect_bug in MutateLLM.py):

在所有测试用例运行后，此函数会分析预言机检查的结果。

如果 CheckOracle 字段显示检查失败 (end 为 False)，则认为发现了一个逻辑Bug，并记录其索引。

最终输出一份包含变异成功率和可疑Bug列表的评估报告。