"""
变异与检测阶段核心：针对转换后的 SQL 进行 LLM 变异并执行预言机检查

作用概述：
- 接收转换阶段成功的 SQL，调用微调的 Mutate LLM 生成等价/相关的变体查询。
- 执行原始与变异 SQL，将结果交给预言机 Check 比较，判断逻辑是否满足预期关系。
- 汇总执行成功率与不满足预言机的可疑案例，用于 bug 发现与报告。

关联流程参考：见 abstract.md《阶段二：变异与检测》与《调用链概览》中的 run_muatate_llm_single_sql、process_mutate_llm_result、detect_bug。
"""

# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/8/2 21:19
# @Author  : shaocanfan
# @File    : MutationLlmModelFineTuning.py
import json
import os
from json_repair import repair_json
from src.Tools.DatabaseConnect.database_connector import exec_sql_statement
from src.Tools.OracleChecker.oracle_check import execSQL_result_convertor, Check
from src.Tools.OracleChecker.oracle_check import Result
from typing import Any, Dict, List, Optional

# 可选引入（仅当使用 Agent 方案时才需要）
try:
    # LangChain OpenAI 驱动（与 translate_sqlancer.py 中的旧接口并行存在）
    from langchain_openai import ChatOpenAI
    from langchain.agents import AgentExecutor, create_openai_functions_agent
    from langchain.tools import tool
    from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
except Exception:
    ChatOpenAI = None
    AgentExecutor = None
    create_openai_functions_agent = None
    tool = None
    ChatPromptTemplate = None
    MessagesPlaceholder = None

os.environ["http_proxy"] = "http://localhost:7890"
os.environ["https_proxy"] = "http://localhost:7890"


# 获取当前文件的绝对路径
current_file_path = os.path.abspath(__file__)
# 获取当前文件所在目录
current_dir = os.path.dirname(current_file_path)


filenames = {
    "FixMCmpOpU": "../../Dataset/MutationLlmModelFineTuning/PostgresSQL/TestingDataset/postgres_testing_dataset_raw2.0(FixMCmpOpU).jsonl",
    "FixMDistinctL": "../../Dataset/MutationLlmModelFineTuning/PostgresSQL/TestingDataset/postgres_testing_dataset_raw2.0(FixMDistinctL).jsonl",
    "FixMHaving1U": "../../Dataset/MutationLlmModelFineTuning/PostgresSQL/TestingDataset/postgres_testing_dataset_raw2.0(FixMHaving1U).jsonl",
    "FixMOn1U": "../../Dataset/MutationLlmModelFineTuning/PostgresSQL/TestingDataset/postgres_testing_dataset_raw2.0(FixMOn1U).jsonl",
}

results_filenames = {
    "FixMCmpOpU": "../../Dataset/MutationLlmModelFineTuning/PostgresSQL/TestingResult/postgres_testing_dataset_raw2.0(FixMCmpOpU).jsonl",
    "FixMDistinctL": "../../Dataset/MutationLlmModelFineTuning/PostgresSQL/TestingResult/postgres_testing_dataset_raw2.0(FixMDistinctL).jsonl",
    "FixMHaving1U": "../../Dataset/MutationLlmModelFineTuning/PostgresSQL/TestingResult/postgres_testing_dataset_raw2.0(FixMHaving1U).jsonl",
    "FixMOn1U": "../../Dataset/MutationLlmModelFineTuning/PostgresSQL/TestingResult/postgres_testing_dataset_raw2.0(FixMOn1U).jsonl",
}

eval_filenames = {
    "FixMCmpOpU": "../../Dataset/MutationLlmModelFineTuning/PostgresSQL/TestingResult/postgres_testing_dataset_raw2.0(FixMCmpOpU)_eval.jsonl",
    "FixMDistinctL": "../../Dataset/MutationLlmModelFineTuning/PostgresSQL/TestingResult/postgres_testing_dataset_raw2.0(FixMDistinctL)_eval.jsonl",
    "FixMHaving1U": "../../Dataset/MutationLlmModelFineTuning/PostgresSQL/TestingResult/postgres_testing_dataset_raw2.0(FixMHaving1U)_eval.jsonl",
    "FixMOn1U": "../../Dataset/MutationLlmModelFineTuning/PostgresSQL/TestingResult/postgres_testing_dataset_raw2.0(FixMOn1U)_eval.jsonl",
}


# ---------------- Agent 方案（仅变异阶段） ---------------- #


def _build_agent(system_message: str) -> Optional[AgentExecutor]:
    """创建一个轻量的 SQL 变异 Agent，用于替代引擎=agent 时的变异生成。

    参数:
        system_message: 从 JSON 配置文件加载的系统消息（与微调 LLM 保持一致）

    返回：AgentExecutor 或 None（当依赖缺失时）。
    """
    if ChatOpenAI is None:
        return None

    # 定义工具：预言机规则、语法校验、结构分析（与独立 demo 保持一致但缩减版）
    @tool
    def get_oracle_rules(oracle_type: str) -> str:
        """返回指定预言机类型(norec/tlp/semantic)的简要规则说明。"""
        rules = {
            "norec": (
                "NoREC: 生成逻辑等价的 SQL 变异; 期望结果集完全相同。"
                " 典型策略: 冗余条件、逻辑等价改写(IN/EXISTS/BETWEEN)、谓词重组。"
            ),
            "tlp": (
                "TLP: 三值逻辑分区，原查询结果 = TRUE 分区 ∪ FALSE 分区 ∪ NULL 分区。"
            ),
            "semantic": ("Semantic: 基于语义的轻微改写，保持意图不变或受控变化。"),
        }
        return rules.get(oracle_type.lower(), "unknown oracle")

    @tool
    def validate_sql_syntax(sql: str, db_type: str) -> str:
        """对给定 SQL/NoSQL 命令进行极简语法检查，返回 valid/warn/invalid 字符串。"""
        # 极简校验，主要用于引导模型自检
        s = sql.strip()
        if db_type.lower() in {
            "mysql",
            "postgres",
            "sqlite",
            "mariadb",
            "tidb",
            "duckdb",
            "clickhouse",
        }:
            if not any(
                k in s.upper() for k in ("SELECT", "INSERT", "UPDATE", "DELETE")
            ):
                return "invalid: missing DML keyword"
            if s.count("(") != s.count(")"):
                return "invalid: parenthesis mismatch"
            if not s.endswith(";"):
                return "warn: missing semicolon"
            return "valid"
        elif db_type.lower() in {"mongodb", "mongo"}:
            # MongoDB shell 命令校验
            if not s.startswith("db."):
                return "invalid: MongoDB shell command must start with 'db.'"
            if not any(
                op in s
                for op in [
                    "insertOne",
                    "findOne",
                    "find",
                    "updateOne",
                    "deleteOne",
                    "aggregate",
                ]
            ):
                return "warn: missing common MongoDB operation"
            if s.count("(") != s.count(")"):
                return "invalid: parenthesis mismatch"
            return "valid"
        return "unknown db"

    @tool
    def analyze_sql_structure(sql: str) -> str:
        """分析 SQL/NoSQL 的结构要点，标注 WHERE/filter 以及可变异点。以 JSON 字符串返回。"""
        u = sql.upper()
        # 支持 SQL 和 MongoDB shell 分析
        if "DB." in u:  # MongoDB
            has_filter = any(
                op in sql for op in ["findOne(", "find(", "updateOne(", "deleteOne("]
            )
            has_operators = any(
                op in sql for op in ["$exists", "$gt", "$lt", "$eq", "$type"]
            )
            points = []
            if has_filter:
                points.append("filter 可修改条件")
            if has_operators:
                points.append("操作符可变异($exists/$type等)")
            return json.dumps(
                {
                    "has_filter": has_filter,
                    "has_operators": has_operators,
                    "points": points,
                },
                ensure_ascii=False,
            )
        else:  # SQL
            has_where = "WHERE" in u
            has_join = "JOIN" in u
            points = []
            if has_where:
                points.append("WHERE 可重写/冗余")
            if has_join:
                points.append("JOIN 可改 EXISTS/子查询")
            return json.dumps(
                {"has_where": has_where, "has_join": has_join, "points": points},
                ensure_ascii=False,
            )

    tools = [get_oracle_rules, validate_sql_syntax, analyze_sql_structure]

    # 使用传入的 system_message（与微调 LLM 保持一致）
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_message),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    llm = ChatOpenAI(
        model=os.environ.get("OPENAI_AGENT_MODEL", "gpt-4o-mini"), temperature=0.4
    )
    agent = create_openai_functions_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,  # 生产环境关闭 verbose
        max_iterations=15,  # 增加迭代次数以允许工具调用
        return_intermediate_steps=False,
        early_stopping_method="generate",  # 允许 Agent 主动停止
    )


def _agent_generate_mutations(
    sql: str, oracle: str, db_type: str, system_message: str
) -> Optional[Dict[str, Any]]:
    """使用 Agent 生成变异结果（JSON）。失败返回 None。

    参数:
        sql: 待变异的 SQL/NoSQL 语句
        oracle: 预言机类型
        db_type: 数据库类型
        system_message: 从 JSON 配置文件加载的系统消息
    """
    agent = _build_agent(system_message)
    if agent is None:
        return None
    # system_message 已包含完整指令，这里只需提供待变异的 SQL
    input_text = f"Seed SQL/NoSQL statement:\n{sql}"
    try:
        res = agent.invoke({"input": input_text})
        output = res.get("output") if isinstance(res, dict) else None
        if not output:
            return None

        # 提取并修复 JSON：支持 ```json...``` 代码块或纯 JSON
        txt = str(output).strip()

        # 方案1: 尝试提取 ```json 代码块
        if "```json" in txt:
            start = txt.find("```json") + 7  # len("```json") = 7
            end = txt.find("```", start)
            if end > start:
                txt = txt[start:end].strip()
        elif "```" in txt:
            # 方案2: 通用代码块 (可能没有 json 标记)
            start = txt.find("```") + 3
            end = txt.find("```", start)
            if end > start:
                txt = txt[start:end].strip()

        # 方案3: 查找第一个 { 和最后一个 } (适用于前后有说明文本的情况)
        if not (txt.startswith("{") or txt.startswith("[")):
            first_brace = txt.find("{")
            last_brace = txt.rfind("}")
            if first_brace >= 0 and last_brace > first_brace:
                txt = txt[first_brace : last_brace + 1]

        # 使用 repair_json 修复可能的 JSON 格式问题（如缺少引号、多余逗号等）
        try:
            data = json.loads(txt)
        except json.JSONDecodeError:
            # JSON 解析失败，尝试使用 repair_json 修复
            try:
                repaired = repair_json(txt)
                data = json.loads(repaired)
            except Exception:
                # 修复仍失败，返回 None 触发回退
                return None

        return data
    except Exception:
        # Agent 调用失败，静默回退到 finetune LLM
        return None


# 处理mutate llm生成的结果，依次处理所有可能的变异：计算oracle，运行并记录结果，oracle check以检测bug
def process_mutate_llm_result(muatate_name, muatate_result, exec_result_before):
    """
    [
        {
            "isUpper": True,
            "transferredSqlsim_exec": {
                "exec_result": str(exec_result),
                "exec_time": str(exec_time),
                "error_message": str(error_message)
            },
            "CheckOracle":{
                "end":True,
                "error":""
            }
        }
    ]
    处理 Mutate LLM 的变异结果并执行预言机检查。

    输入示例（简化）：
    - muatate_result: 列表，每个元素形如 {"mutated sql": "...", "flag": 0/1}
    - exec_result_before: 变异前 SQL 的执行结果

    返回：列表，含每个变体的执行信息与 CheckOracle 结果。
    """
    procrssed_result = []
    for result in muatate_result:
        # 计算oracle,IsUpper: ((candidate.U^candidate.Flag)^1) == 1
        U = muatate_name.endswith("U")
        isUpper = bool((U ^ result["flag"]) ^ 1)
        # 运行该"MutateLLM_Result"并保存运行结果
        exec_result, exec_time, error_message = exec_sql_statement(
            "pinolo", "postgres", result["mutated sql"]
        )

        # 比较该"MutateLLM_Result"的运行结果是否满足oracle
        exec_result_before_formatted = execSQL_result_convertor(exec_result_before)
        exec_result_formatted = execSQL_result_convertor(exec_result)
        exec_result_before_object = Result(
            exec_result_before_formatted["column_names"],
            exec_result_formatted["column_types"],
            exec_result_before_formatted["rows"],
        )
        exec_result_object = Result(
            exec_result_formatted["column_names"],
            exec_result_formatted["column_types"],
            exec_result_before_formatted["rows"],
        )
        end, error = Check(exec_result_before_object, exec_result_object, isUpper)

        processed_item = {
            "isUpper": isUpper,
            "mutate_exec": {
                "exec_result": str(exec_result),
                "exec_time": str(exec_time),
                "error_message": str(error_message),
            },
            "CheckOracle": {"end": end, "error": str(error)},
        }
        procrssed_result.append(processed_item)

    return procrssed_result


"""
def run_muatate_llm(tool, mutate_name):
    client = OpenAI(api_key=api_key)

    # 为Mutate LLM构造满足特定格式的testing data数据项


    if tool.lower() == "pinolo":
        with open(filenames[mutate_name], "r", encoding="utf-8") as r:
            lines = r.readlines()

        for line in lines:
            data = json.loads(line)
            # 执行"transferredSqlsim"并记录结果
            exec_result, exec_time, error_message = exec_sql_statement("pinolo", "postgres", data["transferredSqlsim"])

            data["transferredSqlsim_exec"] = {
                "exec_result": str(exec_result),
                "exec_time": str(exec_time),
                "error_message": str(error_message)
            }

            # mutate the transferredSqlsim
            completion = client.chat.completions.create(
                model=mutate_llm_model_ID,
                messages=data["MutateLLM_Message"]
            )
            response_content = completion.choices[0].message.content
            # 转换字符串结果为python数据结构：mutate llm返回的结果是list形式的，有多个结果
            data["MutateLLM_Result"] = str(response_content)
            MutateLLM_Result_json = eval(response_content)

            # 处理mutate llm的结果并存储
            data["MutateLLM_OracleCheck"] = process_mutate_llm_result(mutate_name, MutateLLM_Result_json, exec_result)

            with open(results_filenames[mutate_name], "a", encoding="utf-8") as w:
                json.dump(data, w)
                w.write("\n")
"""


def run_muatate_llm_single_sql(
    tool, client, model_id, mutate_name, oracle, db_type, sql
):
    """针对单条 SQL 生成候选变体，并返回响应文本与开销统计。

    选择引擎：
    - 若环境变量 QTRAN_MUTATION_ENGINE=agent，则优先采用 Agent 方案（LangChain）。
    - 否则使用微调 LLM 路径（现有实现）。
    """
    # 为Mutate LLM构造满足特定格式的testing data数据项
    if tool.lower() == "sqlancer":
        # 构造格式化输入词
        mutate_stratege = None
        if "norec" in mutate_name.lower():
            mutate_stratege = "norec"
        elif "tlp" in mutate_name.lower():
            mutate_stratege = "tlp"
        elif "semantic" in mutate_name.lower():
            mutate_stratege = "semantic"

        # MongoDB 专用 prompt（当目标是 MongoDB 时）
        is_mongodb_target = db_type.lower() in ["mongodb", "mongo"]
        if is_mongodb_target and mutate_stratege == "semantic":
            mutate_prompt_path = os.path.join(
                current_dir,
                "..",
                "..",
                "MutationData",
                "MutationLLMPrompt",
                "semantic_mongodb.json",
            )
        elif is_mongodb_target and mutate_stratege == "tlp":
            mutate_prompt_path = os.path.join(
                current_dir,
                "..",
                "..",
                "MutationData",
                "MutationLLMPrompt",
                "tlp_mongodb.json",
            )
        elif is_mongodb_target and mutate_stratege == "norec":
            mutate_prompt_path = os.path.join(
                current_dir,
                "..",
                "..",
                "MutationData",
                "MutationLLMPrompt",
                "norec_mongodb.json",
            )
        else:
            mutate_prompt_path = os.path.join(
                current_dir,
                "..",
                "..",
                "MutationData",
                "MutationLLMPrompt",
                mutate_stratege + ".json",
            )

        with open(mutate_prompt_path, "r", encoding="utf-8") as r:
            prompt_data = json.load(r)
            system_message = prompt_data.get(oracle, prompt_data.get("semantic", ""))

        # 针对 MongoDB，用户消息应包含转换后的 MongoDB 操作
        if is_mongodb_target:
            user_content = f"Seed MongoDB operation (converted from Redis):\n{sql}"
        else:
            user_content = f"A seed SQL from {db_type.lower()}:\n{sql}"

        # 根据引擎选择执行
        engine = os.environ.get("QTRAN_MUTATION_ENGINE", "finetune").lower()

        # 1) Agent 路径（仅在关系型/语义变异下启用，对 MongoDB 也可返回 JSON）
        formatted_input = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_content},
        ]
        cost: Dict[str, Any] = {}
        completion = client.chat.completions.create(
            model=model_id, messages=formatted_input
        )
        response_content = completion.choices[0].message.content

        # 尝试使用 json-repair 修复 LLM 生成的 JSON 格式错误
        # 对于 MongoDB TLP/NoREC mutations，经常出现字段名缺少引号的问题
        if is_mongodb_target and response_content:
            try:
                # 先尝试直接解析
                json.loads(response_content)
            except json.JSONDecodeError:
                # 解析失败，尝试修复
                try:
                    repaired = repair_json(response_content)
                    # 验证修复后的 JSON 是否有效
                    json.loads(repaired)
                    response_content = repaired
                except Exception:
                    # 修复失败，保持原样（后续会处理错误）
                    pass

        # print(response_content)
        cost["Total Tokens"] = getattr(completion.usage, "total_tokens", None)
        cost["Prompt Tokens"] = getattr(completion.usage, "prompt_tokens", None)
        cost["Completion Tokens"] = getattr(completion.usage, "completion_tokens", None)
        cost["Total Cost (USD)"] = 0
        return response_content, cost


# 评估mutate llm的变异结果并检测bug
def detect_bug(mutate_name):
    """分析变异结果与预言机检查，统计执行成功率并收集不满足预言机的可疑索引。"""
    detect_results = {}
    exec_fail_mutate_sql_indexes = []
    oracle_false_indexes = []
    with open(results_filenames[mutate_name], "r", encoding="utf-8") as r:
        lines = r.readlines()
    total_num = len(lines)
    total_mutate_sql_num = 0  # 所有可能的mutate语句总数
    exec_success_mutate_sql_num = 0  # 所有可能的mutate语句中成功执行的数量

    for line in lines:
        data = json.loads(line)
        MutateLLM_Result = eval(data["MutateLLM_Result"])
        MutateLLM_OracleCheck = data["MutateLLM_OracleCheck"]

        total_mutate_sql_num += len(MutateLLM_Result)
        for possible_answer in MutateLLM_OracleCheck:
            # 1.执行成功率：postgres的所有变异结果的执行成功率
            if possible_answer["mutate_exec"]["exec_result"] != "None":
                exec_success_mutate_sql_num += 1
                # 2.检测bug：变异前和变异后的结果集是否满足oracle（IsUpper: ((candidate.U ^ candidate.Flag) ^ 1) == 1）
                if possible_answer["CheckOracle"]["end"] == False:
                    oracle_false_indexes.append(data["index"])
                # 3.分析不满足oracle的测试项
            else:
                exec_fail_mutate_sql_indexes.append(data["index"])

    success_rate = (
        str(exec_success_mutate_sql_num / total_mutate_sql_num)
        + "("
        + str(exec_success_mutate_sql_num)
        + "/"
        + str(total_mutate_sql_num)
        + ")"
    )
    detect_results["ExecSuccessRate"] = success_rate
    detect_results["ExecFailIndexes"] = exec_fail_mutate_sql_indexes
    detect_results["OracleFalseIndexes"] = oracle_false_indexes

    with open(eval_filenames[mutate_name], "w", encoding="utf-8") as w:
        json.dump(detect_results, w, indent=4)


# ------------ SQLancer 汇总报告（基于 Output 产物） ------------
def generate_sqlancer_eval_report(input_name: str):
    """
    从 Output/<input_name>/SuspiciousBugs 与 MutationLLM 产物生成评估报告：
    - 变异成功率：以 MutationLLM/*.jsonl 的最后一条记录中 MutateSqlExecError 是否为空判断
    - 可疑 Bug 列表：SuspiciousBugs/*.jsonl 中的 index 汇总去重

    输出：Output/<input_name>/eval_report.json
    """
    base_dir = os.path.abspath(
        os.path.join(current_dir, "..", "..", "Output", input_name)
    )
    suspicious_dir = os.path.join(base_dir, "SuspiciousBugs")
    mutate_dir = os.path.join(base_dir, "MutationLLM")

    report = {
        "input": input_name,
        "mutation_success_rate": 0.0,
        "total_cases": 0,
        "success_cases": 0,
        "suspicious_bug_indexes": [],
        "paths": {"suspicious": suspicious_dir, "mutation": mutate_dir},
    }

    # 统计 suspicious bug 索引
    suspicious_indexes = set()
    if os.path.isdir(suspicious_dir):
        for fname in os.listdir(suspicious_dir):
            if not fname.endswith(".jsonl"):
                continue
            fpath = os.path.join(suspicious_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as r:
                    for line in r:
                        if not line.strip():
                            continue
                        try:
                            item = json.loads(line)
                            if isinstance(item, dict) and "index" in item:
                                suspicious_indexes.add(item["index"])
                        except Exception:
                            pass
            except FileNotFoundError:
                pass

    # 统计变异执行成功率
    total = 0
    success = 0
    if os.path.isdir(mutate_dir):
        for fname in os.listdir(mutate_dir):
            if not fname.endswith(".jsonl"):
                continue
            fpath = os.path.join(mutate_dir, fname)
            try:
                records = []
                with open(fpath, "r", encoding="utf-8") as r:
                    for line in r:
                        if line.strip():
                            records.append(json.loads(line))
                if not records:
                    continue
                total += 1
                last = records[-1]
                err = last.get("MutateSqlExecError", None)
                if err in (None, "None", "none", ""):
                    success += 1
            except Exception:
                # 忽略坏文件，继续统计
                continue

    report["total_cases"] = total
    report["success_cases"] = success
    report["mutation_success_rate"] = (success / total) if total else 0.0
    report["suspicious_bug_indexes"] = sorted(list(suspicious_indexes))

    os.makedirs(base_dir, exist_ok=True)
    out_file = os.path.join(base_dir, "eval_report.json")
    with open(out_file, "w", encoding="utf-8") as w:
        json.dump(report, w, ensure_ascii=False, indent=2)
    return out_file
