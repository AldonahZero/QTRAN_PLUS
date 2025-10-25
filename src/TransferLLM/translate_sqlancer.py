"""
SQLancer 路径：Bug 报告解析 -> 方言特征识别 -> LLM 转换 -> 变异与检查

作用概述：
- 读取 SQLancer 生成的 bug 报告，抽取 SQL 并进行潜在方言特征识别与映射。
*- 调用 transfer_llm 将 a_db 的 SQL 转为 b_db 方言，并支持错误迭代修正。
- 将最终可执行的 SELECT 语句交给 Mutate LLM 生成变异候选，供后续预言机检查。
- 负责组织输入/输出文件与过程持久化（Input/Output 目录）。

关联流程参考：见 abstract.md《调用链概览》《阶段一：转换》《阶段二：变异与检测》。
"""

# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/10/20 19:21
# @Author  : huanghe
# @File    : sqlancer_exp.py
# @Intro   :

from src.DialectRecognition.dialect_feature_recognizer import (
    potential_features_refiner_single_sql,
    sqlancer_potential_dialect_features_process_and_map,
)

# from src.TransferLLM.rag_based_feature_mapping import rag_feature_mapping_llm, rag_feature_mapping_count, rag_feature_mapping_process
from src.TransferLLM.TransferLLM import transfer_llm
from src.Tools.DatabaseConnect.database_connector import database_clear
from datetime import datetime
from src.MutationLlmModelValidator.MutateLLM import run_muatate_llm_single_sql
from src.Tools.OracleChecker.oracle_check import execSQL_result_convertor, Result, Check
from src.Tools.OracleChecker.tlp_checker import check_tlp_oracle, is_tlp_mutation
import os
import json
from json_repair import repair_json
from openai import OpenAI
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from src.Tools.DatabaseConnect.database_connector import exec_sql_statement
from src.Tools.json_utils import make_json_safe


current_file_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file_path)


def _extract_transferred_stmt(transfer_results):
    """Return the last transferred statement regardless of SQL or NoSQL branch.

    transfer_results: list of dicts produced by transfer_llm.
    Each dict may contain one of:
        - "TransferSQL" (SQL semantic path)
        - "TransferNoSQL" (NoSQL crash path)
    """
    if not transfer_results:
        return None
    last = transfer_results[-1]
    return last.get("TransferSQL") or last.get("TransferNoSQL")


"""
sqlancer_norec_mutate_id = os.environ['SQLANCER_MUTATE_MODEL_NOREC']
sqlancer_dqe_mutate_id = os.environ['SQLANCER_MUTATE_MODEL_DQE']
sqlancer_tlp_mutate_id = os.environ['SQLANCER_MUTATE_MODEL_TLP']
"""

"""
TLP_supported_dbs = ["sqlite", "mysql", "tidb", "duckdb"]
TLP_extended_dbs = ["mariadb", "postgres", "monetdb", "clickhouse"]

NoRec_supported_dbs = ["sqlite", "mariadb", "postgres"]
NoRec_extended_dbs = ["mysql", "tidb", "monetdb", "duckdb", "clickhouse"]
"""


# 获取sqlancer的bug report,并进行potential dialect feature识别
def load_sqlancer_bug_report(fuzzer, a_db, b_db, bug):
    """按行拆分 SQLancer bug 报告中的 SQL，附带必要上下文，作为后续转换输入单元。"""
    # 以列表形式返回bug经过处理得到的input信息
    bug_input = []
    # 有多条数据，存储在jsonl文件中，每一句sql存为一行
    for sql in bug["sqls"]:
        # 识别potential feature,将所有的feature都粗略的认为是dialect
        (
            SqlPotentialFunctionIndexes,
            SqlPotentialOperatorIndexes,
            SqlPotentialDialectFunction,
            SqlPotentialDialectOperator,
        ) = potential_features_refiner_single_sql(sql)
        # 获取对应的mapping indexes
        SqlPotentialDialectFunctionMapping = (
            sqlancer_potential_dialect_features_process_and_map(
                a_db,
                b_db,
                SqlPotentialDialectFunction,
                "function",
                search_k=0,
                version_id=1,
            )
        )
        # 暂不考虑operator
        SqlPotentialDialectOperatorMapping = []
        # SqlPotentialDialectOperatorMapping = sqlancer_potential_dialect_features_process_and_map(a_db, b_db, SqlPotentialDialectOperator, "operator",search_k=0, version_id=1)
        new_content = {
            "index": bug["index"],
            "a_db": bug["a_db"],
            "b_db": bug["b_db"],
            "molt": bug["molt"],
            "sql": sql,
        }
        bug_input.append(new_content)
    return bug_input


def sqlancer_translate(
    input_filepath,
    tool="sqlancer",
    temperature=0.3,
    model="gpt-4o-mini",
    error_iteration=True,
    iteration_num=4,
    FewShot=False,
    with_knowledge=True,
):
    """
    SQLancer 全流程驱动：
    - 构建 Input/Output 目录；
    - 解析 bug 报告，提取待转换 SQL；
    - 调用 transfer_llm 执行跨方言转换及错误迭代；
    - 调用 Mutate LLM 获取变异结果并持久化。
    """
    # ========== Mem0 记忆管理初始化 ==========
    use_mem0 = os.environ.get("QTRAN_USE_MEM0", "false").lower() == "true"
    
    # 翻译阶段的 Mem0 管理器
    mem0_manager = None
    if use_mem0:
        try:
            from src.TransferLLM.mem0_adapter import (
                TransferMemoryManager, FallbackMemoryManager
            )
            try:
                mem0_manager = TransferMemoryManager(
                    user_id="qtran_transfer_universal"
                )
                print(f"✅ Translation Mem0 initialized")
            except ImportError:
                print("⚠️ Mem0 not available for translation, using fallback")
                mem0_manager = FallbackMemoryManager(
                    user_id="qtran_transfer_fallback"
                )
        except Exception as e:
            print(f"⚠️ Failed to initialize Translation Mem0: {e}")
            mem0_manager = None
    
    # 变异阶段的 Mem0 管理器
    mutation_mem0_manager = None
    if use_mem0:
        try:
            from src.MutationLlmModelValidator.mutation_mem0_adapter import (
                MutationMemoryManager, FallbackMutationMemoryManager
            )
            try:
                mutation_mem0_manager = MutationMemoryManager(
                    user_id="qtran_mutation_universal"
                )
                print(f"✅ Mutation Mem0 initialized")
            except ImportError:
                print("⚠️ Mem0 not available for mutation, using fallback")
                mutation_mem0_manager = FallbackMutationMemoryManager(
                    user_id="qtran_mutation_fallback"
                )
        except Exception as e:
            print(f"⚠️ Failed to initialize Mutation Mem0: {e}")
            mutation_mem0_manager = None
    
    input_filename = os.path.basename(input_filepath).replace(".jsonl", "")
    input_dic = os.path.join(current_dir, "..", "..", "Input", input_filename)
    if not os.path.exists(input_dic):
        os.makedirs(input_dic, exist_ok=True)  # 如果文件夹已存在，则不会抛出异常
    # 新建所需transfer output文件夹
    output_transfer_dic = os.path.join(
        current_dir, "..", "..", "Output", input_filename, "TransferLLM"
    )
    if not os.path.exists(output_transfer_dic):
        os.makedirs(
            output_transfer_dic, exist_ok=True
        )  # 如果文件夹已存在，则不会抛出异常
    # 新建所需mutate output文件夹
    output_mutate_dic = os.path.join(
        current_dir, "..", "..", "Output", input_filename, "MutationLLM"
    )
    if not os.path.exists(output_mutate_dic):
        os.makedirs(
            output_mutate_dic, exist_ok=True
        )  # 如果文件夹已存在，则不会抛出异常

    with open(input_filepath, "r", encoding="utf-8") as r:
        bugs = r.readlines()
    for line in bugs:
        bug = json.loads(line)
        a_db = bug["a_db"]
        b_db = bug["b_db"]
        fuzzer = bug["molt"]

        # Step1: rag_based_feature_mapping。先做以下mapping，SQLite/mariadb/（Postgres是0暂时不弄）mapping to mysql/tidb/monetdb/duckdb/clickhouse
        # rag_feature_mapping_llm(1,0,a_db, b_db, ["function"], ["Feature", "Description", "Examples", "Category"])
        # rag_feature_mapping_count(1,0, a_db, b_db, ["function"], ["Feature", "Description", "Examples", "Category"])
        # rag_feature_mapping_process(1,0, a_db, b_db, ["function"], ["Feature", "Description", "Examples", "Category"])

        # Step2: potential_features_refiner
        bug_input = []
        bug_input_filename = os.path.join(input_dic, str(bug["index"]) + ".jsonl")
        if not os.path.exists(bug_input_filename):
            bug_input = load_sqlancer_bug_report(fuzzer, a_db, b_db, bug)
            for info in bug_input:
                with open(bug_input_filename, "a", encoding="utf-8") as a:
                    json.dump(info, a)
                    a.write("\n")
        else:
            print("📥 " + bug_input_filename + " exists.")
            with open(bug_input_filename, "r", encoding="utf-8") as r:
                lines = r.readlines()
            for line in lines:
                bug_input.append(json.loads(line))

        # Step3: 根据bug report中信息进行transfer并存储到output文件夹中
        transfer_outputs = []
        bug_output_transfer_filename = os.path.join(
            output_transfer_dic, str(bug["index"]) + ".jsonl"
        )
        if not os.path.exists(bug_output_transfer_filename):
            # transfer llm conversion
            chat = ChatOpenAI(temperature=temperature, model=model)
            memory = ConversationBufferMemory()  # 内存：对话缓冲区内存
            if error_iteration:
                conversation = ConversationChain(
                    llm=chat,
                    memory=memory,
                    verbose=False,  # 为true的时候是展示langchain实际在做什么
                )
            else:
                conversation = ConversationChain(
                    llm=chat, verbose=False  # 为true的时候是展示langchain实际在做什么
                )
            for info in bug_input:
                transfer_start_time = datetime.now()  # 使用 ISO 8601 格式
                (
                    costs,
                    transfer_results,
                    exec_results,
                    exec_times,
                    error_messages,
                    origin_exec_result,
                    origin_exec_time,
                    origin_error_message,
                    exec_equalities,
                ) = transfer_llm(
                    tool=tool,
                    exp=fuzzer,
                    conversation=conversation,
                    error_iteration=error_iteration,
                    iteration_num=iteration_num,
                    FewShot=FewShot,
                    with_knowledge=with_knowledge,
                    origin_db=a_db,
                    target_db=b_db,
                    test_info=info,
                )
                transfer_end_time = datetime.now()  # 使用 ISO 8601 格式
                info["SqlExecResult"] = origin_exec_result
                info["SqlExecError"] = origin_error_message
                info["TransferResult"] = transfer_results
                info["TransferCost"] = costs
                info["TransferTimeCost"] = (
                    transfer_end_time - transfer_start_time
                ).total_seconds()
                info["TransferSqlExecResult"] = exec_results
                info["TransferSqlExecError"] = error_messages
                info["TransferSqlExecEqualities"] = exec_equalities
                transfer_outputs.append(info)
            # sqlancer执行完一组sql后，将a_db和d_db都进行clear
            database_clear(tool, fuzzer, a_db)
            database_clear(tool, fuzzer, b_db)
            # 全部执行完再进行存储
            with open(bug_output_transfer_filename, "a", encoding="utf-8") as a:
                for item in transfer_outputs:
                    json.dump(make_json_safe(item), a, ensure_ascii=False)
                    a.write("\n")
        else:
            print("📥 " + bug_output_transfer_filename + " exists.")
            with open(bug_output_transfer_filename, "r", encoding="utf-8") as r:
                lines = r.readlines()
            for line in lines:
                transfer_outputs.append(json.loads(line))

        # Step4:mutate llm,将transfer后的最后一句select语句进行mutate并返回结果
        mutate_results = []
        bug_output_mutate_filename = os.path.join(
            output_mutate_dic, str(bug["index"]) + ".jsonl"
        )
        if not os.path.exists(bug_output_mutate_filename):
            for item in transfer_outputs:
                mutate_results.append(item)
            if len(mutate_results) and len(mutate_results[-1]["TransferResult"]):
                print("🔧 mutate_results: ", mutate_results[-1])
                mutate_sql = _extract_transferred_stmt(
                    mutate_results[-1]["TransferResult"]
                )
                if mutate_sql is None:
                    print(
                        "🔧 [WARN] No TransferSQL/TransferNoSQL found in last TransferResult; skipping mutate phase for this bug."
                    )
                    continue

                # 智能检测实际执行的目标数据库类型
                # 检查 TransferSqlExecResult 来确定真实的目标数据库
                actual_target_db = b_db  # 默认使用 b_db
                if (
                    "TransferSqlExecResult" in mutate_results[-1]
                    and mutate_results[-1]["TransferSqlExecResult"]
                ):
                    try:
                        exec_result_str = mutate_results[-1]["TransferSqlExecResult"][0]
                        if isinstance(exec_result_str, str):
                            exec_result_json = json.loads(exec_result_str)
                            detected_db_type = exec_result_json.get(
                                "dbType", ""
                            ).lower()
                            if detected_db_type in ["mongodb", "mongo"]:
                                actual_target_db = "mongodb"
                                print(
                                    "📥 "
                                    + f"[INFO] Detected actual target database: MongoDB (b_db was {b_db})"
                                )
                    except (json.JSONDecodeError, KeyError, IndexError) as e:
                        print(
                            f"[WARN] Failed to detect actual target database: {e}, using b_db={b_db}"
                        )

                # mutate llm client
                client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
                mutate_start_time = datetime.now()  # 使用 ISO 8601 格式
                if fuzzer.lower() == "norec":
                    # 优先环境变量，其次回退到通用模型（用于 agent 失败时的兜底）
                    mutate_llm_model_ID = os.environ.get(
                        f"{fuzzer}_MUTATION_LLM_ID".upper(), "gpt-4o-mini"
                    )
                elif "tlp" in fuzzer.lower():
                    fuzzer_temp = "tlp"
                    mutate_llm_model_ID = os.environ.get(
                        f"{fuzzer_temp}_MUTATION_LLM_ID".upper(), "gpt-4o-mini"
                    )
                elif "semantic" in fuzzer.lower():
                    fuzzer_temp = "semantic"
                    mutate_llm_model_ID = os.environ.get(
                        f"{fuzzer_temp}_MUTATION_LLM_ID".upper(), "gpt-4o-mini"
                    )
                else:
                    mutate_llm_model_ID = os.environ.get(
                        "SEMANTIC_MUTATION_LLM_ID", "gpt-4o-mini"
                    )
                # ========== Mem0 开始变异会话 ==========
                if mutation_mem0_manager:
                    try:
                        mutation_mem0_manager.start_session(
                            db_type=actual_target_db,
                            oracle_type=bug["molt"],
                            sql_type="SELECT"  # 假定变异的都是 SELECT 类查询
                        )
                    except Exception as e:
                        print(f"⚠️ Failed to start mutation session: {e}")
                
                # 调用变异
                mutate_content, cost = run_muatate_llm_single_sql(
                    tool,
                    client,
                    mutate_llm_model_ID,
                    fuzzer,
                    bug["molt"],
                    actual_target_db,  # 使用检测到的实际目标数据库,而非 b_db
                    mutate_sql,
                    mem0_manager=mutation_mem0_manager  # 传入 Mem0 管理器
                )
                mutate_end_time = datetime.now()  # 使用 ISO 8601 格式
                mutate_results[-1]["MutateTimeCost"] = (
                    mutate_end_time - mutate_start_time
                ).total_seconds()
                mutate_results[-1]["MutateResult"] = str(mutate_content)
                mutate_results[-1]["MutateCost"] = cost
                # 进行存储
                with open(bug_output_mutate_filename, "a", encoding="utf-8") as a:
                    for item in mutate_results:
                        json.dump(make_json_safe(item), a, ensure_ascii=False)
                        a.write("\n")
        else:
            print("🔧 " + bug_output_mutate_filename + " 已存在")
            # load出来
            with open(bug_output_mutate_filename, "r", encoding="utf-8") as r:
                lines = r.readlines()
            for line in lines:
                mutate_results.append(json.loads(line))

        # Step5: check oracle,执行mutate后sql并记录执行结果以及oracle check结果
        if "MutateSqlExecResult" not in mutate_results[-1]:
            ddls = []
            transfer_fail_flag = False
            for i in range(len(mutate_results) - 1):
                stmt_i = _extract_transferred_stmt(mutate_results[i]["TransferResult"])
                if stmt_i:
                    ddls.append(stmt_i)
                if mutate_results[i]["TransferSqlExecError"][-1] != "None":
                    transfer_fail_flag = True
            # 先创造执行环境
            database_clear(tool, fuzzer, b_db)
            for ddl in ddls:
                exec_sql_statement(tool, fuzzer, b_db, ddl)

            before_mutate = _extract_transferred_stmt(
                mutate_results[-1]["TransferResult"]
            )
            if before_mutate is None:
                print(
                    "[ERROR] Cannot extract before_mutate statement; aborting mutate/oracle stage for this bug."
                )
                continue
            after_mutate = mutate_results[-1]["MutateResult"]

            before_result, before_exec_time, before_error_message = exec_sql_statement(
                tool, fuzzer, b_db, before_mutate
            )

            # 如果 MutateResult 是 JSON 且包含 mutations 列表，则逐条解析并执行每个 cmd（适用于 NoSQL mutation 回放）
            after_result = None
            after_exec_time = None
            after_error_message = None
            try:
                parsed_mutate = None
                if isinstance(mutate_results[-1].get("MutateResult"), str):
                    try:
                        # 先尝试使用 json-repair 修复可能的 JSON 格式错误
                        repaired_json = repair_json(mutate_results[-1]["MutateResult"])
                        parsed_mutate = json.loads(repaired_json)
                    except Exception:
                        # 如果修复失败，尝试直接解析
                        try:
                            parsed_mutate = json.loads(
                                mutate_results[-1]["MutateResult"]
                            )
                        except Exception:
                            parsed_mutate = None
                else:
                    parsed_mutate = mutate_results[-1].get("MutateResult")

                if isinstance(parsed_mutate, dict) and "mutations" in parsed_mutate:
                    cmds = []
                    for m in parsed_mutate.get("mutations", []):
                        # 支持两种字段名: "cmd" 和 "mutated_sql"
                        cmd = m.get("cmd") or m.get("mutated_sql")
                        if cmd:
                            # 如果 cmd 本身是字符串且包含 JSON，也尝试修复
                            if isinstance(cmd, str) and cmd.strip().startswith("{"):
                                try:
                                    repaired_cmd = repair_json(cmd)
                                    cmds.append(repaired_cmd)
                                except Exception:
                                    cmds.append(cmd)
                            else:
                                cmds.append(cmd)

                    mutate_exec_list = []
                    mutate_errors = []
                    total_time = 0.0
                    for cmd in cmds:
                        r, t, e = exec_sql_statement(tool, fuzzer, b_db, cmd)
                        mutate_exec_list.append(r)
                        mutate_errors.append(e)
                        try:
                            total_time += float(t)
                        except Exception:
                            pass

                    # 保存逐条执行的结果（序列化为 JSON 字符串以便持久化）
                    mutate_results[-1]["MutateSqlExecResult"] = json.dumps(
                        mutate_exec_list, ensure_ascii=False
                    )
                    mutate_results[-1]["MutateSqlExecTime"] = str(total_time)
                    # 如果所有子命令都没有报错，则标记 None（字符串形式保持兼容）
                    any_err = [e for e in mutate_errors if e and str(e) != "None"]
                    mutate_results[-1]["MutateSqlExecError"] = (
                        str(any_err) if any_err else "None"
                    )

                    # 选择用于 oracle 比较的 after_result：优先取第一次 kv_get 的返回，其次取最后一个可用 dict 返回
                    for r in mutate_exec_list:
                        if isinstance(r, dict) and str(r.get("type", "")).startswith(
                            "kv_get"
                        ):
                            after_result = r
                            break
                    if after_result is None:
                        for r in reversed(mutate_exec_list):
                            if isinstance(r, dict):
                                after_result = r
                                break

                    if after_result is None:
                        # 若逐条执行没有可用结构化结果，fallback 为尝试把整体 MutateResult 当作单条命令执行
                        after_result, after_exec_time, after_error_message = (
                            exec_sql_statement(
                                tool,
                                fuzzer,
                                b_db,
                                mutate_results[-1].get("MutateResult"),
                            )
                        )
                    else:
                        after_exec_time = total_time
                        after_error_message = None
                else:
                    # 不是 JSON mutations，按旧逻辑直接执行整个字符串
                    after_result, after_exec_time, after_error_message = (
                        exec_sql_statement(
                            tool, fuzzer, b_db, mutate_results[-1].get("MutateResult")
                        )
                    )
            except Exception as e:
                # 出现异常时回退到原行为
                after_result, after_exec_time, after_error_message = exec_sql_statement(
                    tool, fuzzer, b_db, mutate_results[-1].get("MutateResult")
                )

            # 对于sqlancer的tlp，谓词的随机性比较大，这里将重复几次，以生成可执行的mutate sql
            if fuzzer.lower() == "tlp":
                client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
                mutate_cnt = 1
                while mutate_cnt <= iteration_num:
                    if after_error_message != None:
                        mutate_llm_model_ID = os.environ[
                            f"{fuzzer}_MUTATION_LLM_ID".upper()
                        ]
                        (
                            mutate_results[-1]["MutateResult"],
                            mutate_results[-1]["MutateCost"],
                        ) = run_muatate_llm_single_sql(
                            tool,
                            client,
                            mutate_llm_model_ID,
                            fuzzer,
                            # Some bug reports may not include an 'oracle' field.
                            # Fall back to 'molt' (fuzzer type) or None to preserve behavior
                            # and avoid KeyError.
                            bug.get("oracle", bug.get("molt", None)),
                            b_db,
                            before_mutate,
                        )
                        after_mutate = mutate_results[-1]["MutateResult"]
                        after_result, after_exec_time, after_error_message = (
                            exec_sql_statement(tool, fuzzer, b_db, after_mutate)
                        )

                        # 将最后一次的结果存储到对应的mutate output文件中,先清空
                        with open(
                            bug_output_mutate_filename, "w", encoding="utf-8"
                        ) as a:
                            pass
                        with open(
                            bug_output_mutate_filename, "a", encoding="utf-8"
                        ) as a:
                            for item in mutate_results:
                                json.dump(make_json_safe(item), a, ensure_ascii=False)
                                a.write("\n")
                        mutate_cnt += 1
                    else:
                        break
            # 全部执行完再次进行clear
            database_clear(tool, fuzzer, b_db)
            # 对不同类型的目标数据库采用不同的持久化格式：
            # - 对于关系型/SQL 数据库，保留原注释里的行为（字符串化），以保持与现有 downstream 兼容性
            # - 对于 NoSQL（如 MongoDB/Redis 等），使用 json.dumps() 来确保字段为合法 JSON（双引号），并保留结构化信息
            nosql_dbs = {"mongodb", "mongo", "redis", "etcd", "memcached", "cassandra"}
            try:
                if isinstance(b_db, str) and b_db.lower() in nosql_dbs:
                    # NoSQL: 保留结构化结果并使用合法 JSON 序列化
                    mutate_results[-1]["MutateSqlExecResult"] = json.dumps(
                        after_result, ensure_ascii=False
                    )
                    mutate_results[-1]["MutateSqlExecTime"] = str(after_exec_time)
                    # 对 Error 也使用 json.dumps()，将 None 转为 null
                    mutate_results[-1]["MutateSqlExecError"] = json.dumps(
                        after_error_message, ensure_ascii=False
                    )
                else:
                    # SQL: 使用字符串化以兼容旧逻辑（注释中的实现）
                    mutate_results[-1]["MutateSqlExecResult"] = str(after_result)
                    mutate_results[-1]["MutateSqlExecTime"] = str(after_exec_time)
                    mutate_results[-1]["MutateSqlExecError"] = str(after_error_message)
            except Exception:
                # 在极端情况下回退到通用字符串化，避免破坏文件写入流程
                mutate_results[-1]["MutateSqlExecResult"] = str(after_result)
                mutate_results[-1]["MutateSqlExecTime"] = str(after_exec_time)
                mutate_results[-1]["MutateSqlExecError"] = str(after_error_message)

            if before_error_message or after_error_message:
                # 如果是mutate前和后的语句有执行fail的情况
                oracle_check_res = {"end": False, "error": "exec fail"}
            else:
                # -------- TLP Oracle 检查 -------- #
                # 检查是否为 TLP 变异(通过 oracle 字段判断)
                if is_tlp_mutation(mutate_results[-1]):
                    try:
                        # 为 TLP 准备变异结果列表
                        # mutate_results[-1] 包含了所有分区的执行结果
                        tlp_results = []

                        # 解析 mutations 数组
                        mutate_result_str = mutate_results[-1].get("MutateResult", "{}")
                        if isinstance(mutate_result_str, str):
                            parsed_mutate = json.loads(mutate_result_str)
                        else:
                            parsed_mutate = mutate_result_str

                        mutations = parsed_mutate.get("mutations", [])

                        # 解析执行结果列表
                        exec_result_str = mutate_results[-1].get(
                            "MutateSqlExecResult", "[]"
                        )
                        if isinstance(exec_result_str, str):
                            exec_results = json.loads(exec_result_str)
                        else:
                            exec_results = exec_result_str

                        # 组装每个分区的结果
                        for i, (mutation, exec_result) in enumerate(
                            zip(mutations, exec_results)
                        ):
                            tlp_results.append(
                                {
                                    "MutateResult": json.dumps(
                                        {"mutations": [mutation]}
                                    ),
                                    "MutateSqlExecResult": exec_result,
                                }
                            )

                        # 调用 TLP 检查器
                        oracle_check_res = check_tlp_oracle(tlp_results)

                    except Exception as e:
                        oracle_check_res = {
                            "end": False,
                            "error": f"TLP oracle check failed: {str(e)}",
                            "bug_type": "tlp_check_error",
                        }
                else:
                    # -------- 非 TLP: 使用原有的 Oracle 检查逻辑 -------- #
                    converted_before_result = execSQL_result_convertor(before_result)
                    converted_after_result = execSQL_result_convertor(after_result)

                    # -------- KV 专用 oracle -------- #
                    # 识别条件：原始 before_result/after_result 为 dict 且含 'type' 且前缀 kv_
                    is_kv_before = isinstance(before_result, dict) and str(
                        before_result.get("type", "")
                    ).startswith("kv_")
                    is_kv_after = isinstance(after_result, dict) and str(
                        after_result.get("type", "")
                    ).startswith("kv_")
                    if is_kv_before and is_kv_after:
                        # 简化策略：
                        # 1) 对 kv_get：值相等 (包含均为 None) 则通过
                        # 2) 对写操作 (kv_set/kv_delete) -> after 不报错即可通过（不可比值）
                        # 3) kv_range：列表元素集合一致（忽略顺序）
                        bt = before_result.get("type")
                        at = after_result.get("type")
                        bval = before_result.get("value")
                        aval = after_result.get("value")
                        passed = False
                        err = None
                        if bt == "kv_get" and at == "kv_get":
                            passed = bval == aval
                        elif bt in {"kv_set", "kv_delete"} and at in {
                            "kv_set",
                            "kv_delete",
                        }:
                            # 认为写后再次写或删除语义不应引入直接差异（缺乏更强 oracle，此处放宽）
                            passed = True
                        elif bt == "kv_range" and at == "kv_range":
                            try:
                                bset = {str(x) for x in (bval or [])}
                                aset = {str(x) for x in (aval or [])}
                                passed = bset == aset
                            except Exception:
                                passed = False
                        else:
                            # 类型不同，保守判定失败
                            passed = False
                            err = f"kv oracle type mismatch: {bt} vs {at}"
                        oracle_check_res = {"end": passed, "error": err}
                    else:
                        # -------- 关系型/通用 oracle -------- #
                        before_result_object = Result(
                            converted_before_result["column_names"],
                            converted_before_result["column_types"],
                            converted_before_result["rows"],
                        )
                        after_result_object = Result(
                            converted_after_result["column_names"],
                            converted_after_result["column_types"],
                            converted_after_result["rows"],
                        )
                        oracle_check, error = Check(
                            before_result_object, after_result_object, True, True
                        )  # check result->another_result是否符合is_upper
                        oracle_check_res = {"end": oracle_check, "error": error}
                        # 判断是否为sqlancer的特殊情况：0==None(表示个数时)
                        if converted_before_result["rows"] == [
                            ["0"]
                        ] and converted_after_result["rows"] == [["None"]]:
                            oracle_check_res = {"end": True, "error": None}

            # 如果ddls中有transfer失败的情况
            if transfer_fail_flag:
                oracle_check_res = {"end": False, "error": "transfer fail"}
            mutate_results[-1]["OracleCheck"] = oracle_check_res
            
            # ========== Mem0 记录 Bug 模式 ==========
            if mutation_mem0_manager and oracle_check_res:
                try:
                    # 如果 Oracle 检查失败且不是执行错误，说明发现了潜在 Bug
                    if oracle_check_res.get("end") == False and oracle_check_res.get("error") in [None, "None"]:
                        bug_type = oracle_check_res.get("bug_type", "oracle_violation")
                        
                        mutation_mem0_manager.record_bug_pattern(
                            original_sql=mutate_sql,
                            mutation_sql=str(mutate_results[-1].get("MutateResult", "")),
                            bug_type=bug_type,
                            oracle_type=bug["molt"],
                            db_type=actual_target_db,
                            oracle_details=oracle_check_res.get("details", {})
                        )
                        print(f"🐛 Bug pattern recorded to Mem0: {bug_type}")
                    
                    # 记录 Oracle 失败模式（包括执行错误）
                    elif oracle_check_res.get("end") == False:
                        mutation_mem0_manager.record_oracle_failure_pattern(
                            original_sql=mutate_sql,
                            mutation_sql=str(mutate_results[-1].get("MutateResult", "")),
                            failure_reason=str(oracle_check_res.get("error", "unknown")),
                            oracle_type=bug["molt"],
                            db_type=actual_target_db,
                            expected_result=before_result,
                            actual_result=after_result
                        )
                    
                    # 结束会话
                    mutation_mem0_manager.end_session(
                        success=oracle_check_res.get("end", False),
                        summary=f"Oracle: {bug['molt']}, Result: {oracle_check_res.get('end', False)}"
                    )
                    
                    # 打印性能指标
                    if hasattr(mutation_mem0_manager, 'get_metrics_report'):
                        print(mutation_mem0_manager.get_metrics_report())
                        
                except Exception as e:
                    print(f"⚠️ Failed to record to Mutation Mem0: {e}")
            
            # ========== 🔥 MVP 反向反馈机制：生成 Recommendation ==========
            if mem0_manager and oracle_check_res.get("end") == False:
                _generate_recommendation_from_oracle(
                    mem0_manager=mem0_manager,
                    oracle_result=oracle_check_res,
                    original_sql=mutate_sql,  # 使用 mutate_sql 而不是 info["sql"]
                    origin_db=a_db,
                    target_db=actual_target_db,  # 使用检测到的实际目标数据库
                    oracle_type=bug.get("molt", "unknown")
                )
            
            with open(bug_output_mutate_filename, "w", encoding="utf-8") as a:
                pass
            with open(bug_output_mutate_filename, "a", encoding="utf-8") as a:
                for item in mutate_results:
                    json.dump(make_json_safe(item), a, ensure_ascii=False)
                    a.write("\n")
    print("📥 ------------------------")


def sqlancer_qtran_run(
    input_filepath,
    tool="sqlancer",
    temperature=0.3,
    model="gpt-4o-mini",
    error_iteration=True,
    iteration_num=4,
    FewShot=False,
    with_knowledge=True,
):
    sqlancer_translate(
        input_filepath=input_filepath,
        tool="sqlancer",
        temperature=temperature,
        model=model,
        error_iteration=True,
        iteration_num=iteration_num,
        FewShot=False,
        with_knowledge=False,
    )
    getSuspicious(input_filepath=input_filepath, tool="sqlancer")


def getSuspicious(input_filepath, tool):
    input_filename = os.path.basename(input_filepath).replace(".jsonl", "")
    output_mutate_dic = os.path.join(
        current_dir, "..", "..", "Output", input_filename, "MutationLLM"
    )
    if not os.path.exists(output_mutate_dic):
        os.makedirs(
            output_mutate_dic, exist_ok=True
        )  # 如果文件夹已存在，则不会抛出异常

    suspicious_dic = os.path.join(
        current_dir, "..", "..", "Output", input_filename, "SuspiciousBugs"
    )
    if not os.path.exists(suspicious_dic):
        os.makedirs(suspicious_dic, exist_ok=True)  # 如果文件夹已存在，则不会抛出异常

    filenames = os.listdir(output_mutate_dic)
    for file in filenames:
        if os.path.exists(os.path.join(suspicious_dic, file)):
            continue
        with open(os.path.join(output_mutate_dic, file), "r", encoding="utf-8") as r:
            lines = r.readlines()
        contents = []
        for line in lines:
            contents.append(json.loads(line))
        # end False：不满足等价 / 不变量
        # error None：且不是执行失败（exec fail / transfer fail）
        # 即逻辑层差异
        if (
            contents[-1]["OracleCheck"]["end"] == False
            and contents[-1]["OracleCheck"]["error"] == None
        ):
            original_sqls = []
            results_sqls = []
            for content in contents:
                extracted_stmt = _extract_transferred_stmt(content["TransferResult"])
                new_content = {
                    "index": content["index"],
                    "sql": content["sql"],
                    "TransferResult": [extracted_stmt] if extracted_stmt else [],
                }
                original_sqls.append(content["sql"] + "\n")
                if extracted_stmt:
                    results_sqls.append(extracted_stmt + "\n")
                if "MutateResult" in content:
                    new_content["TransferSqlExecResult"] = [
                        content["TransferSqlExecResult"][-1]
                    ]
                    new_content["MutateResult"] = content["MutateResult"]
                    new_content["MutateSqlExecResult"] = content["MutateSqlExecResult"]
                    results_sqls.append(content["MutateResult"] + "\n")
                with open(
                    os.path.join(suspicious_dic, file), "a", encoding="utf-8"
                ) as a:
                    json.dump(new_content, a)
                    a.write("\n")
            with open(
                os.path.join(suspicious_dic, file.replace("jsonl", "txt")),
                "w",
                encoding="utf-8",
            ) as file:
                file.writelines(original_sqls + ["\n", "\n"] + results_sqls)


def evaluate(
    tool,
    temperature,
    model,
    error_iteration,
    iteration_num,
    FewShot,
    with_knowledge,
    fuzzer,
    a_db,
    b_db,
):
    # 总数：total_cnt
    # executable总数：mutate可执行的数目
    # valid：mutate满足oracle的数目
    # precise：mutate语义正确的数量
    total_cnt = 0
    executable_cnt = 0
    valid_cnt = 0
    precise_cnt = 0

    oracle_check_transfer_fail = {"end": False, "error": "transfer fail"}
    oracle_check_mutate_fail = {"end": False, "error": "exec fail"}
    oracle_check_mutate_success = {"end": True, "error": None}

    oracle_check_fail = {"end": False, "error": None}

    # output_mutate_dic = os.path.join(sqlancer_output_mutate_dic, fuzzer, (a_db + "_to_" + b_db).lower())
    # output_mutate_dic_ = os.path.join(sqlancer_output_mutate_dic_, fuzzer, (a_db + "_to_" + b_db).lower())
    output_mutate_dic = os.path.join(
        "sqlancer_output_mutate_dic", fuzzer, (a_db + "_to_" + b_db).lower()
    )
    output_mutate_dic_ = os.path.join(
        "sqlancer_output_mutate_dic_", fuzzer, (a_db + "_to_" + b_db).lower()
    )

    files = os.listdir(output_mutate_dic)
    for file in files:
        total_cnt += 1
        contents = []
        with open(os.path.join(output_mutate_dic, file), "r", encoding="utf-8") as r:
            lines = r.readlines()
        for line in lines:
            contents.append(json.loads(line))
        oracle_check = contents[-1]["OracleCheck"]
        mutate_sql = contents[-1]["MutateResult"]

        contents_ = []
        with open(os.path.join(output_mutate_dic_, file), "r", encoding="utf-8") as r:
            lines = r.readlines()
        for line in lines:
            contents_.append(json.loads(line))
        right_mutate_sql = contents_[-1]["MutateResult"]
        if oracle_check != oracle_check_transfer_fail:
            if oracle_check != oracle_check_mutate_fail:
                executable_cnt += 1
                if oracle_check == oracle_check_mutate_success:
                    valid_cnt += 1
                # 判断no finetuning的生成的句子和fine tuning生成的句子是否相同，相同则认为是正确的
                if mutate_sql == right_mutate_sql:
                    precise_cnt += 1
                # print("before mutate:"+contents[-1]["Sql"])
                # print("after mutate:"+mutate_sql)
                # print("right mutate:"+right_mutate_sql)
                # print('------------------')
    print("total_cnt:" + str(total_cnt))
    print("executable_cnt:" + str(executable_cnt))
    print("valid_cnt:" + str(valid_cnt))
    print("precise_cnt:" + str(precise_cnt))


# ========== 🔥 MVP 反向反馈机制辅助函数 ==========

def _generate_recommendation_from_oracle(
    mem0_manager,
    oracle_result: dict,
    original_sql: str,
    origin_db: str,
    target_db: str,
    oracle_type: str
):
    """
    根据 Oracle 检查结果生成 Recommendation 和 CoverageHotspot
    
    Args:
        mem0_manager: Mem0 管理器
        oracle_result: Oracle 检查结果
        original_sql: 原始SQL
        origin_db: 源数据库
        target_db: 目标数据库
        oracle_type: Oracle 类型 (tlp/norec/semantic)
    """
    # 只在发现潜在Bug时生成建议
    if oracle_result.get("end") == False and oracle_result.get("error") in [None, "None", ""]:
        # 提取SQL特性
        features = _extract_sql_features(original_sql)
        
        # 计算优先级（基于bug类型）
        bug_type = oracle_result.get("bug_type", "unknown")
        if bug_type == "TLP_violation":
            priority = 9
            coverage_gain = 15.0  # TLP violation 认为是高价值的覆盖
        elif bug_type == "NoREC_mismatch":
            priority = 8
            coverage_gain = 12.0
        else:
            priority = 7
            coverage_gain = 8.0
        
        try:
            # 1. 🔥 生成 CoverageHotspot（Oracle失败 = 发现了有价值的特性组合）
            if hasattr(mem0_manager, 'add_coverage_hotspot'):
                mem0_manager.add_coverage_hotspot(
                    features=features,
                    coverage_gain=coverage_gain,
                    origin_db=origin_db,
                    target_db=target_db,
                    mutation_sql=original_sql,
                    metadata={
                        "bug_type": bug_type,
                        "oracle_type": oracle_type,
                        "source": "oracle_violation"
                    }
                )
                print(f"🔥 Generated hotspot: {', '.join(features)} (gain: {coverage_gain}%)")
            
            # 2. 生成 Recommendation
            mem0_manager.add_recommendation(
                target_agent="translation",
                priority=priority,
                action="prioritize_features",
                features=features,
                reason=f"{oracle_type}_oracle_violation: {bug_type}",
                origin_db=origin_db,
                target_db=target_db,
                metadata={
                    "bug_type": bug_type,
                    "oracle_type": oracle_type,
                    "details": oracle_result.get("details", {}),
                    "coverage_gain": coverage_gain
                }
            )
            
            print(f"🔥 Generated recommendation: prioritize {', '.join(features)} (Priority: {priority})")
        except Exception as e:
            print(f"⚠️ Failed to generate recommendation: {e}")


def _extract_sql_features(sql: str) -> list:
    """
    从SQL中提取关键特性
    
    Returns:
        特性列表，如 ["HEX", "MIN", "COLLATE", "aggregate"]
    """
    features = []
    sql_upper = sql.upper()
    
    # 常见函数
    functions = [
        "HEX", "MIN", "MAX", "SUM", "AVG", "COUNT", "ABS", 
        "CONCAT", "SUBSTR", "SUBSTRING", "LENGTH", "UPPER", "LOWER",
        "ROUND", "FLOOR", "CEIL", "CAST", "COALESCE", "NULLIF"
    ]
    for func in functions:
        if f"{func}(" in sql_upper:
            features.append(func)
    
    # 特殊关键字
    keywords = [
        "COLLATE", "UNION", "INTERSECT", "EXCEPT", "JOIN", 
        "GROUP BY", "HAVING", "ORDER BY", "LIMIT", "OFFSET",
        "DISTINCT", "WHERE", "CASE WHEN"
    ]
    for kw in keywords:
        if kw in sql_upper:
            features.append(kw.replace(" ", "_"))
    
    # 聚合判断
    if any(agg in sql_upper for agg in ["MIN(", "MAX(", "SUM(", "AVG(", "COUNT("]):
        if "aggregate" not in features:
            features.append("aggregate")
    
    # JOIN 类型
    join_types = ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN", "CROSS JOIN"]
    for jt in join_types:
        if jt in sql_upper:
            features.append(jt.replace(" ", "_"))
            break  # 只添加一次
    
    # MongoDB 特定操作符（如果SQL中包含）
    mongodb_ops = ["$and", "$or", "$not", "$exists", "$type", "$gte", "$lte", "$in", "$nin"]
    for op in mongodb_ops:
        if op in sql:
            features.append(op)
    
    # 去重并限制数量
    unique_features = list(dict.fromkeys(features))  # 保持顺序去重
    return unique_features[:5]  # 限制返回最多5个特性
