"""
转换阶段核心：基于 LLM 的跨方言 SQL 转换与错误迭代修正

作用概述：
- 接收来源 SQL（如来自 sqlancer/pinolo），结合 Few-Shot 示例与方言特征知识库，调用 LLM 生成目标数据库可执行 SQL。
- 若执行失败，利用错误信息进行若干次迭代修正，直到成功或达上限；全程记录消耗、结果与错误。
- 提供数据加载/初始化工具（pinolo 数据）与列名预处理等辅助能力。

关联流程参考：见 abstract.md《阶段一：转换 (Transfer Phase)》《调用链概览》中的 transfer_llm。
"""

# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/7/26 17:09
# @Author  : zql
# @File    : TransferLLM.py
# @Intro   :

import os
import json
import random
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import ResponseSchema
from langchain.output_parsers import StructuredOutputParser
from langchain.callbacks import get_openai_callback
from src.Tools.DatabaseConnect.database_connector import exec_sql_statement


# Optional: Redis KB adapter for prompt augmentation (lazy import)
try:
    from src.NoSQLKnowledgeBaseConstruction.Redis.redis_kb_adapter import (
        select_redis_candidates,
        build_prompt_with_kb,
    )
    _REDIS_KB_AVAILABLE = True
except Exception:
    _REDIS_KB_AVAILABLE = False


db_names = ["mysql", "mariadb", "tidb"]

def load_data(output_name, db_name, len_low, len_high, is_random, num):
    """
    加载 pinolo 原始 SQL 及 SQLsim 数据，并按长度与是否随机抽样导出到输出集。

    参数：
    - output_name/db_name: 数据源目录定位。
    - len_low/len_high: 过滤长度 [low, high)。
    - is_random/num: 随机抽样与抽样数。

    说明：不会修改业务逻辑，仅整理并持久化筛选后的 SQL/SQLsim 与其索引。
    """
    # 加载数据：
    # 加载所有的originalSql及对应的originalSqlsim数据：长度在[len_low,len_high)。
    # len_high = float('inf')代表无穷大;len_low=1,len_high = float('inf')则表示获取所有数据
    # random=True时,则随机选择num条数据；random=False时，则返回长度在[len_low,len_high)的所有数据
    # 源文件：Pinolo Output/output(1-4)/dbname文件夹内的originalSql_all.json,originalSqlsim_all.json
    # 目标文件：Pinolo Output/output_test下ALL和RANDOM文件夹内的output1_mariadb_x_x_originalSql_all.json，output1_mariadb_x_x_originalSqlsim_all.json，output1_mariadb_x_x_originalSqlIndex_all.json
    if len_low >= len_high:
        return
    # sql语句的文件名
    filename = os.path.join("..\..\Dataset\Pinolo Output", output_name, db_name+"_merged", "originalSql_all.json")
    # sqlsim语句的文件名
    sim_filename = os.path.join("..\..\Dataset\Pinolo Output", output_name, db_name+"_merged", "originalSqlsim_all.json")
    # 存储加载所得数据的目标文件名
    dir_filename = os.path.join("..\..\Dataset\Pinolo Output", "output_test", "ALL", output_name+"_" + db_name+"_"+str(len_low)+"_"+str(len_high)+"_originalSql_all.json")
    dir_sim_filename = os.path.join("..\..\Dataset\Pinolo Output", "output_test", "ALL", output_name+"_" + db_name+"_"+str(len_low)+"_"+str(len_high)+"_originalSqlsim_all.json")
    dir_index_filename = os.path.join("..\..\Dataset\Pinolo Output", "output_test", "ALL", output_name+"_" + db_name+"_"+str(len_low)+"_"+str(len_high)+"_originalSqlIndex_all.json")

    # 文件已存在，返回
    if os.path.exists(dir_filename) and os.path.exists(dir_sim_filename) and os.path.exists(dir_index_filename):
        return

    with open(filename, "r", encoding="utf-8") as rf:
        contents = json.load(rf)
    with open(sim_filename, "r", encoding="utf-8") as f:
        sim_contents = json.load(f)

    selected_sqls = []
    selected_sqlsims = []
    selected_sql_indexes = []
    # 选取指定长度区间的数据
    for i in range(len(contents)):
        content = contents[i]
        if len_low <= len(content) < len_high:
            selected_sqls.append(content)
            selected_sqlsims.append(sim_contents[i])
            selected_sql_indexes.append(i)

    if is_random:
        # 随机加载：从指定长度区间中随机选择num条数据并返回
        random_num = 0
        random_sqls = []
        random_sqlsims = []
        random_sql_indexes = []
        if len(selected_sqls) < num:
            # [len_low,len_high)的数量小于要提取的数目num
            random_num = len(selected_sqls)
            random_sqls = selected_sqls
            random_sqlsims = selected_sqlsims
            random_sql_indexes = selected_sql_indexes
        else:
            random_num = num
            random_numbers = random.sample(range(0, len(selected_sqls)), num)
            for number in random_numbers:
                random_sqls.append(selected_sqls[number])
                random_sqlsims.append(selected_sqlsims[number])
                random_sql_indexes.append(selected_sql_indexes[number])
        random_dir_filename = os.path.join("..\..\Dataset\Pinolo Output", "output_test", "RANDOM", output_name + "_" + db_name + "_" + str(len_low) + "_" + str(len_high) + "_originalSql_random_" + str(random_num)+".json")
        random_dir_sim_filename = os.path.join("..\..\Dataset\Pinolo Output", "output_test", "RANDOM", output_name + "_" + db_name + "_" + str(len_low) + "_" + str(len_high) + "_originalSqlsim_random_" + str(random_num)+".json")
        random_dir_index_filename = os.path.join("..\..\Dataset\Pinolo Output", "output_test", "RANDOM", output_name + "_" + db_name + "_" + str(len_low) + "_" + str(len_high) + "_originalSqlIndex_ramdom_" + str(random_num)+".json")
        with open(random_dir_filename, 'w', encoding='utf-8') as f:
            json.dump(random_sqls, f, indent=4)
        with open(random_dir_sim_filename, 'w', encoding='utf-8') as f:
            json.dump(random_sqlsims, f, indent=4)
        with open(random_dir_index_filename, 'w', encoding='utf-8') as f:
            json.dump(random_sql_indexes, f, indent=4)
        print(random_dir_filename + ":" + str(len(random_sqls)))
        print(random_dir_sim_filename + ":" + str(len(random_sqlsims)))
    else:
        # 全部加载：直接存储所有[len_low,len_high)长度的数据
        with open(dir_filename, 'w', encoding='utf-8') as f:
            json.dump(selected_sqls, f, indent=4)
        with open(dir_sim_filename, 'w', encoding='utf-8') as f:
            json.dump(selected_sqlsims, f, indent=4)
        with open(dir_index_filename, 'w', encoding='utf-8') as f:
            json.dump(selected_sql_indexes, f, indent=4)

        print(dir_filename + ":" + str(len(selected_sqls)))
        print(dir_sim_filename + ":" + str(len(selected_sqlsims)))


def init_data(output_name, db_name, len_low, len_high, is_random, num):
    """
    # 初始化结果数据：
    # 根据load_data()得到的数据，初始化结果数据并存储到output_test文件夹中
    # 源文件：Pinolo Output/output_test下ALL和RANDOM文件夹内的output1_mariadb_x_x_originalSql_all.json，output1_mariadb_x_x_originalSqlsim_all.json，output1_mariadb_x_x_originalSqlIndex_all.json
    # 目标文件：Pinolo Output/output_test下ALL和RANDOM文件夹内的init_output1_mariadb_x_x_originalSql_all.json,init_output1_mariadb_x_x_originalSqlsim_all.json
    """
    prefix = os.path.join("..\..\Dataset\Pinolo Output", "output_test")
    # exec_args = database_connection_args[db_name]

    # 源文件和目标文件
    if is_random:
        sql_temp = output_name + "_" + db_name + "_" + str(len_low) + "_" + str(len_high) + "_originalSql_random_" + str(num) + ".json"
        sqlsim_temp = output_name + "_" + db_name + "_" + str(len_low) + "_" + str(len_high) + "_originalSqlsim_random_" + str(num) + ".json"
        index_temp = output_name + "_" + db_name + "_" + str(len_low) + "_" + str(len_high) + "_originalSqlIndex_ramdom_" + str(num) + ".json"
        sql_filename = os.path.join(prefix, "RANDOM", sql_temp)
        sqlsim_filename = os.path.join(prefix,  "RANDOM", sqlsim_temp)
        index_filename = os.path.join(prefix, "RANDOM", index_temp)
        sql_dir_filename = os.path.join(prefix, "RANDOM", "init_"+sql_temp)
        sqlsim_dir_filename = os.path.join(prefix, "RANDOM", "init_"+sqlsim_temp)
    else:
        sql_temp = output_name + "_" + db_name + "_" + str(len_low) + "_" + str(len_high) + "_originalSql_all.json"
        sqlsim_temp = output_name + "_" + db_name + "_" + str(len_low) + "_" + str(len_high) + "_originalSqlsim_all.json"
        index_temp = output_name + "_" + db_name + "_" + str(len_low) + "_" + str(len_high) + "_originalSqlIndex_all.json"
        sql_filename = os.path.join(prefix, "ALL", sql_temp)
        sqlsim_filename = os.path.join(prefix, "ALL", sqlsim_temp)
        index_filename = os.path.join(prefix, "ALL", index_temp)
        sql_dir_filename = os.path.join(prefix, "ALL", "init_"+sql_temp)
        sqlsim_dir_filename = os.path.join(prefix, "ALL", "init_"+sqlsim_temp)

    # 文件已存在，返回
    if os.path.exists(sql_dir_filename) and os.path.exists(sqlsim_dir_filename):
        return

    with open(sql_filename, "r", encoding="utf-8") as rf:
        sqls = json.load(rf)
    with open(sqlsim_filename, "r", encoding="utf-8") as rf:
        sqlsims = json.load(rf)
    with open(index_filename, "r", encoding="utf-8") as rf:
        sql_indexes = json.load(rf)
    # 初始化结果数据
    sql_init_results = []
    sqlsim_init_results = []
    avg_sql_length = 0
    avg_sqlsim_length = 0
    for index in range(len(sqls)):
        result = {
            "index": index,
            "origin_index": sql_indexes[index],
            "Sql": sqls[index],
            "SqlLength": len(sqls[index]),
            "SqlExecResult": "",
            "SqlExecTime": "",
            "SqlExecError": "",
            "TransferResult": [],
            "TransferCost": [],
            "TransferSqlExecResult": [],
            "TransferSqlExecTime": [],
            "TransferSqlExecError": [],
            "TransferSqlExecEqualities": []
        }
        sim_result = {
            "index": index,
            "origin_index": sql_indexes[index],
            "Sql": sqlsims[index],
            "SqlLength": len(sqlsims[index]),
            "SqlExecResult": "",
            "SqlExecTime": "",
            "SqlExecError": "",
            "TransferResult": [],
            "TransferCost": [],
            "TransferSqlExecResult": [],
            "TransferSqlExecTime": [],
            "TransferSqlExecError": [],
            "TransferSqlExecEqualities": []
        }
        avg_sql_length += len(sqls[index])
        avg_sqlsim_length += len(sqlsims[index])
        sql_init_results.append(result)
        sqlsim_init_results.append(sim_result)

    avg_sql_length /= len(sqls)
    avg_sqlsim_length /= len(sqlsims)
    print("sql平均长度："+str(avg_sql_length))
    print("sqlsim平均长度："+str(avg_sqlsim_length))
    with open(sql_dir_filename, 'w', encoding='utf-8') as f:
        json.dump(sql_init_results, f, indent=4)

    with open(sqlsim_dir_filename, 'w', encoding='utf-8') as f:
        json.dump(sqlsim_init_results, f, indent=4)

# 处理传递给transfer llm的sql statement(这是针对pinolo的process)
def sql_statement_process(origin_sql):
    """Pinolo 到 Postgres 前的列名预处理：统一某些特殊列名写法，便于后续转换与执行。"""
    map_list = {
        "col_decimal(40, 20)_undef_signed": "col_decimal_40_20_undef_signed",
        "col_decimal(40, 20)_undef_unsigned": "col_decimal_40_20_undef_unsigned",
        "col_decimal(40, 20)_key_signed": "col_decimal_40_20_key_signed",
        "col_decimal(40, 20)_key_unsigned": "col_decimal_40_20_key_unsigned",
        "col_char(20)_undef_signed": "col_char_20_undef_signed",
        "col_char(20)_key_signed": "col_char_20_key_signed",
        "col_varchar(20)_undef_signed": "col_varchar_20_undef_signed",
        "col_varchar(20)_key_signed": "col_varchar_20_key_signed"
    }
    sql_statement = origin_sql
    for key, value in map_list.items():
        if key in origin_sql:
            sql_statement = sql_statement.replace(key, value)
    return sql_statement


def get_examples_string(FewShot, origin_db, target_db):
    examples_string = ""
    examples_data = None
    if FewShot:  # 给出样例
        # example是给出的例子
        with open(os.path.join("../../Dataset/Pinolo Output/output_test/",
                               "examples_" + origin_db + "_" + target_db + ".json"), "r", encoding="utf-8") as r:
            examples_data = json.load(r)
        example = None
        for index in range(len(examples_data)):
            example = examples_data[index]
            OriginDB = example["origin_db"]
            TargetDB = example["target_db"]
            SQL = example["Sql"]
            Answer = json.dumps(example["answer"])
            # 坏了，这句好像写在for循环外面了
            examples_string = examples_string + '[Example ' + str(
                index) + ' start]: ' + '[original database]: ' + OriginDB + '\n' + '[target database]: ' + TargetDB + '\n' + '[sql statement]: ' + SQL + '\n' + '[Answer]: ' + Answer + '\n' + '[Example ' + str(
                index) + ' end]\n'
    return examples_string

def build_sql_to_redis_semantic_hints(sql_text):
        """
        根据SQL内容匹配sql_to_redis_mapping.json中的pattern，生成结构化语义提示。
        """
        import re
        mapping_path = os.path.join("..", "..", "NoSQLFeatureKnowledgeBase", "Redis", "outputs", "sql_to_redis_mapping.json")
        if not os.path.exists(mapping_path):
            return "[SQL→Redis Semantic Mapping] (mapping file not found)\n"
        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
            mappings = mapping_data.get("mappings", {})
        except Exception as e:
            return f"[SQL→Redis Semantic Mapping Load Error]: {e}\n"

        sql = sql_text.lower()
        # pattern优先级顺序，越前越优先
        pattern_keys = [
            ("join", ["join"]),
            ("group by", ["group by"]),
            ("order by limit", ["order by", "limit"]),
            ("order by", ["order by"]),
            ("distinct", ["distinct"]),
            ("count(*)", ["count(*)", "count ( * )"]),
            ("update", ["update"]),
            ("delete", ["delete"]),
            ("select+where", ["select", "where"]),
            ("select by key", ["select"]),
        ]
        matched = []
        for key, keywords in pattern_keys:
            if all(kw in sql for kw in keywords):
                if key in mappings:
                    matched.append((key, mappings[key]))
        # 只保留最多3条
        matched = matched[:3]
        if not matched:
            return "[SQL→Redis Semantic Mapping] No typical pattern matched.\n"
        out = "[SQL→Redis Semantic Mapping]\n"
        for key, val in matched:
            out += f"Pattern: {key}\n"
            if 'redis' in val:
                out += f"Redis Strategy: {val['redis']}\n"
            if 'example' in val:
                out += f"Example: {val['example']}\n"
            if 'notes' in val:
                out += f"Notes: {val['notes']}\n"
            if 'tradeoffs' in val:
                out += f"Tradeoffs: {val['tradeoffs']}\n"
            if 'pitfalls' in val:
                out += f"Pitfalls: {val['pitfalls']}\n"
            out += "\n"
        return out
"""
def get_feature_knowledge_string(origin_db, target_db, with_knowledge, mapping_indexes):
    knowledge_string = ""
    steps_string = ""
    examples_data = None
    if with_knowledge:  # 给出样例
        # 获取对应的详细信息
        names_ = "merge"
        for feature_type in ["function"]:
            names_ = names_ + "_" + feature_type
        origin_merge_feature_filename = os.path.join("..", "..", "FeatureKnowledgeBase Processed1", origin_db, "RAG_Embedding_Data",names_ + ".jsonl")
        target_merge_feature_filename = os.path.join("..", "..", "FeatureKnowledgeBase Processed1", target_db,"RAG_Embedding_Data", names_ + ".jsonl")
        with open(origin_merge_feature_filename, "r", encoding="utf-8") as r:
            origin_features = r.readlines()
        with open(target_merge_feature_filename, "r", encoding="utf-8") as r:
            target_features = r.readlines()
        cnt = 0
        for mapping_pair in mapping_indexes:
            # 获取a_db以及b_db中的feature knowledge
            origin_feature = json.loads(origin_features[mapping_pair[0]])
            target_feature = json.loads(target_features[mapping_pair[1]])
            knowledge_string = knowledge_string + "[Feature Mapping "+str(cnt) + " Start]" + "Here is the original feature.\n"
            knowledge_string = knowledge_string + "Feature Syntax(Database "+origin_db+"):"
            for item in origin_feature["Feature"]:
                knowledge_string += item
            knowledge_string += "\nDescription(Database "+origin_db+"):"
            for item in origin_feature["Description"]:
                knowledge_string += item
            knowledge_string = knowledge_string + "\nExamples(Database "+origin_db+"):"
            for item in origin_feature["Examples"]:
                knowledge_string += item

            knowledge_string += "Here is the mapping feature.\n"

            knowledge_string = knowledge_string + "Feature Syntax(Database "+target_db+"):"
            for item in target_feature["Feature"]:
                knowledge_string += item
            knowledge_string = knowledge_string + "\nDescription(Database "+origin_db+"):"
            for item in target_feature["Description"]:
                knowledge_string += item
            knowledge_string = knowledge_string + "\nExamples(Database "+origin_db+"):"
            for item in target_feature["Examples"]:
                knowledge_string += item
            knowledge_string += "\n"

            knowledge_string = knowledge_string + "[Feature Mapping " + str(cnt) + " End]"

            # 拼接steps的提示词
            steps_string = steps_string + "Replace "+str(origin_feature["Feature"])+" from "+origin_db+" in original sql with "+str(target_feature["Feature"])+" from "+target_db+"\n"
            cnt += 1
    return knowledge_string, steps_string
"""
def get_NoSQL_knowledge_string(origin_db, target_db, with_knowledge, sql_statement_processed):
    # 初始化返回字符串，避免在异常或非 Redis 分支时未定义
    knowledge_string = ""
    # 特殊处理：如果来源或目标是 Redis，则加载 NoSQL Redis 知识库
    # 目前实现：当 origin_db 为 redis 时，注入 Redis 命令/示例知识；
    # 后续可扩展 target_db == redis 的映射提示（比如 SQL -> Redis）。
    if str(origin_db).lower() == "redis":
        try:
            repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            redis_kb_path = os.path.join(repo_root, "NoSQLFeatureKnowledgeBase", "Redis", "outputs", "redis_commands_knowledge.json")
            print("Loading Redis CMD Knowledge from: " + redis_kb_path)

            if os.path.exists(redis_kb_path):
                with open(redis_kb_path, 'r', encoding='utf-8') as rf:
                    redis_kb = json.load(rf)
                commands = redis_kb.get("commands", {})
                # 根据 sql_statement_processed 中出现的命令关键词动态抽取
                import re
                statement_text = (sql_statement_processed or "").lower()

                # 提取所有字母/数字/_/: 组成的 token 作为潜在命令（单词形式）
                raw_tokens = set(re.findall(r'[a-zA-Z][a-zA-Z0-9:_]*', statement_text))

                matched = []
                for cmd_name in commands.keys():
                    cmd_lower = cmd_name.lower()
                    # 多词命令（如 CLIENT LIST）采用整体正则匹配；单词命令直接在 token 集合里判断
                    if ' ' in cmd_lower:
                        if re.search(r'\b' + re.escape(cmd_lower) + r'\b', statement_text):
                            matched.append(cmd_name)
                    else:
                        if cmd_lower in raw_tokens:
                             matched.append(cmd_name)

                # 去重保持出现顺序：按在文本中首次出现的位置排序
                def first_pos(name: str):
                    try:
                        return statement_text.index(name.lower())
                    except ValueError:
                        return 10**9
                matched = sorted(list(dict.fromkeys(matched)), key=first_pos)

                if not matched:
                    knowledge_string += "(no command keyword matched in input statement; showing fallback examples)\n"
                    # 回退挑选常见命令，避免 prompt 为空
                    fallback_order = ["GET", "SET", "DEL", "HSET", "HGET", "LPUSH", "RPUSH", "SADD", "ZADD", "EVAL"]
                    matched = [c for c in fallback_order if c in commands][:5]

                for cmd_name in matched:
                    meta = commands.get(cmd_name, {})
                    examples = meta.get("examples", [])
                    example_snippet = ""
                    if examples:
                        # 选取最短示例，避免过长
                        shortest = min(examples, key=lambda x: len(x.get("raw", "")))
                        example_snippet = shortest.get("raw", "")
                    knowledge_string += f"Command: {cmd_name}\n"
                    if meta.get("group"):
                        knowledge_string += f"Group: {meta.get('group')}\n"
                    if meta.get("summary"):
                        knowledge_string += f"Summary: {meta.get('summary')}\n"
                    if meta.get("since"):
                        knowledge_string += f"Since: {meta.get('since')}\n"
                    if meta.get("complexity"):
                        knowledge_string += f"Complexity: {meta.get('complexity')}\n"
                    if example_snippet:
                        knowledge_string += f"Example: {example_snippet}\n"
                    knowledge_string += "\n"

                # 避免 LLM 臆造任意表名
                # 仅当目标是典型关系型数据库（如 postgres / mysql / mariadb / tidb / sqlite / duckdb / clickhouse / monetdb / postgres 等）时注入
                relational_targets = {"postgres", "mysql", "mariadb", "tidb", "sqlite", "duckdb", "clickhouse", "monetdb"}
                if str(target_db).lower() in relational_targets:
                    knowledge_string += "You MUST NOT invent other table names. Always reuse tab_0 tab_1.\n"
            else:
                knowledge_string += "Knowl file not found\n"
        except Exception as e:
            knowledge_string = ""
        # Redis 当前不使用 mapping_indexes（命令之间暂未建立映射对），直接返回
        print("knowledge_string: " + knowledge_string)
        return knowledge_string
    # 非 Redis 情况返回空字符串（调用处会根据 with_knowledge 逻辑决定后续）
    return knowledge_string
    
    
# 函数定义：获取特征知识字符串，用于构建从源数据库到目标数据库的特征映射知识
def get_feature_knowledge_string(origin_db, target_db, with_knowledge, mapping_indexes, sql_statement_processed):
    # 初始化知识字符串为空，用于累积特征知识描述
    knowledge_string = ""
    # 初始化步骤字符串为空（当前未使用）
    steps_string = ""
    # 初始化示例数据为None（当前未使用）
    examples_data = None
    # 如果需要包含知识，则执行以下逻辑
    if with_knowledge:  # 给出样例
        # 获取对应的详细信息
        # 初始化文件名基础部分
        names_ = "merge"
        # 为每个特征类型添加后缀，这里只处理"function"
        for feature_type in ["function"]:
            names_ = names_ + "_" + feature_type
        # 构建源数据库的合并特征文件名路径
        origin_merge_feature_filename = os.path.join("..", "..", "FeatureKnowledgeBase", origin_db, "RAG_Embedding_Data",names_ + ".jsonl")
        print("origin_merge_feature_filename: " + origin_merge_feature_filename)
        # 构建目标数据库的合并特征文件名路径
        target_merge_feature_filename = os.path.join("..", "..", "FeatureKnowledgeBase", target_db,"RAG_Embedding_Data", names_ + ".jsonl")
        print("target_merge_feature_filename: " + target_merge_feature_filename)
        # 以只读模式打开源特征文件，并读取所有行
        with open(origin_merge_feature_filename, "r", encoding="utf-8") as r:
            origin_features = r.readlines()
        # 以只读模式打开目标特征文件，并读取所有行
        with open(target_merge_feature_filename, "r", encoding="utf-8") as r:
            target_features = r.readlines()
        # 初始化计数器，用于步骤编号
        cnt = 0
        # 遍历映射索引对，每个对包含源和目标特征的索引
        for mapping_pair in mapping_indexes:    
            # 获取a_db以及b_db中的feature knowledge
            # 从源特征列表中解析对应索引的特征JSON
            origin_feature = json.loads(origin_features[mapping_pair[0]])
            # 从目标特征列表中解析对应索引的特征JSON
            target_feature = json.loads(target_features[mapping_pair[1]])
            # 构建步骤描述字符串，说明从源到目标的转换
            knowledge_string = knowledge_string + " Step " + str(cnt) + ": Transfer " + str(origin_feature["Feature"])+" from "+origin_db+" to "+str(target_feature["Feature"])+" from "+target_db+"\n"
            # 添加源特征的介绍文本
            knowledge_string = knowledge_string + "Here is the original feature from "+origin_db +".\n"
            # 添加源特征的语法描述前缀
            knowledge_string = knowledge_string + "Feature Syntax(Database "+origin_db+"):"
            # 遍历源特征的语法项并追加到字符串
            for item in origin_feature["Feature"]:
                knowledge_string += item
            # 注释掉的代码：添加源特征的描述（当前被注释）
            """
            knowledge_string += "\nDescription(Database "+origin_db+"):"
            for item in origin_feature["Description"]:
                knowledge_string += item
            """
            # 添加源特征的示例前缀
            knowledge_string = knowledge_string + "\nExamples(Database "+origin_db+"):"
            # 遍历源特征的示例项并追加到字符串
            for item in origin_feature["Examples"]:
                knowledge_string += item
            # 添加目标特征的介绍文本
            knowledge_string = knowledge_string + "Here is the mapping feature from "+target_db +".\n"
            # 添加目标特征的语法描述前缀
            knowledge_string = knowledge_string + "Feature Syntax(Database "+target_db+"):"
            # 遍历目标特征的语法项并追加到字符串
            for item in target_feature["Feature"]:
                knowledge_string += item
            # 注释掉的代码：添加目标特征的描述（当前被注释）
            """
            knowledge_string = knowledge_string + "\nDescription(Database "+origin_db+"):"
            for item in target_feature["Description"]:
                knowledge_string += item
            """
            # 添加目标特征的示例前缀
            knowledge_string = knowledge_string + "\nExamples(Database "+origin_db+"):"
            # 遍历目标特征的示例项并追加到字符串
            for item in target_feature["Examples"]:
                knowledge_string += item
            # 添加两个换行符以分隔不同映射
            knowledge_string += "\n\n"
            # 计数器递增
            cnt += 1
    # 返回构建的知识字符串
    return knowledge_string

def transfer_llm(tool, exp, conversation, error_iteration, iteration_num, FewShot, with_knowledge, origin_db, target_db, test_info, use_redis_kb: bool = False):
    """
    # transfer llm:单条sql语句的转换及结果处理
    # 返回结果：costs, transfer_results, exec_results, exec_times, error_messages, str(origin_exec_result), str(origin_exec_time), str(origin_error_message), exec_equalities
    :return:
    # * transfer llm的花销列表"costs",结果列表"transfer_results"，
    # * 转换后语句Sql的运行结果列表"exec_results"，运行报错列表"error_messages"，
    # * 转换前语句Sql，对应运行结果"str(origin_exec_result)"，运行报错"str(origin_error_message)"
    # * 运行结果与原sql的一致性列表"exec_equalities"
    # * 列表是为返回error进行迭代设计的，能记录多次迭代的过程值
    """
    # test_info: {'index': 162, 'a_db': 'sqlite', 'b_db': 'duckdb', 'molt': 'norec', 'sql': 'CREATE TABLE t0(c0);'}
    sql_statement = test_info["sql"]
    sql_statement_processed = sql_statement
    
    # 在这里做sql预处理
    # 如果是mysql_like转postgres，先把sql语句的列名进行替换，和postgres的ddl语句中的列名保持一致，便于后续语句转换
    if target_db == "postgres" and tool.lower() == "pinolo":
        sql_statement_processed = sql_statement_process(sql_statement)

    
    # 说明：transfer_llm_string 是发送给 LLM 的主 prompt 模板。
    # 占位符说明：
    #   {origin_db}           - 来源数据库名，用于说明源语法/语义上下文
    #   {target_db}           - 目标数据库名，用于说明目标语法要求
    #   {sql_statement}       - 待转换的原始 SQL（已预处理）
    #   {feature_knowledge}   - 注入的 feature 知识（映射/示例/规则），直接写入 prompt
    #   {examples}            - few-shot 示例串（可选），帮助模型举例学习
    #   {format_instructions} - StructuredOutputParser 给出的输出格式说明，要求模型按结构返回

    transfer_llm_string = """  
    Let's think step by step.You are an expert in sql statement translation between different database.\
    With the assistance of feature knowledge,transfer the following {origin_db} statement to executable {target_db} statement with similar semantics.\
    {origin_db} statement: {sql_statement}\

    Transfer should ensure following requirements:
    1. All column names and feature variables remain unchanged.
    2. Strictly forbid meaningless features(such as NULL,0), features with random return value(such as current_time).
    3. Transfer as far as possible, and ensure similar semantics.\

    Transfer by carrying out following instructions step by step.\
    {feature_knowledge}\
    
    Check if transfer result satisfies requirements mentioned before.If not,modify the result.

    Here are some transfer examples: {examples}\
    Answer the following information: {format_instructions}
    """

    response_schemas = [
        ResponseSchema(type="string", name="TransferSQL", description='The transferred SQL statement result.'),
        ResponseSchema(type="string", name="Explanation", description='Explain the basis for the conversion.')
    ]

    output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
    format_instructions = output_parser.get_format_instructions()

    # FewShot = False 目前没有
    examples_string = get_examples_string(FewShot, origin_db,target_db)
    # examples_string = ""
    if str(origin_db).lower() == "redis":
        feature_knowledge_string = get_NoSQL_knowledge_string(origin_db, target_db, with_knowledge, sql_statement_processed)
    elif with_knowledge:
        feature_knowledge_string = get_feature_knowledge_string(origin_db, target_db, with_knowledge, test_info["SqlPotentialDialectFunctionMapping"], sql_statement_processed)
    else:
        feature_knowledge_string = ""
    
    prompt_template = ChatPromptTemplate.from_template(transfer_llm_string)

    iterate_llm_string = """  
    The corresponding executable SQL statement that you provided in your most recent response resulted in an error when executed.\
    Please modify your most recent SQL statement response based on the error message.\
    Ensure that all column names remain unchanged between the sql statements before and after the transfer.\
    error message:{error_message}  
    Answer the following information: {format_instructions}  
    """

    iterate_response_schemas = [
        ResponseSchema(type="string", name="TransferSQL", description='The new transferred SQL statement result after modification.'),
        ResponseSchema(type="string", name="Explanation", description='Explain the basis for the conversion and modification.')
    ]

    iterate_output_parser = StructuredOutputParser.from_response_schemas(iterate_response_schemas)
    iterate_format_instructions = iterate_output_parser.get_format_instructions()

    iterate_prompt_template = ChatPromptTemplate.from_template(iterate_llm_string)

    costs = []
    transfer_results = []
    exec_results = []
    exec_times = []
    error_messages = []
    exec_equalities = []
    # 执行origin sql得到结果，并和得到的所有transfer sql结果依次进行比对，确定执行结果是否相同，将对比结果存储到exec_same中
    origin_exec_result, origin_exec_time, origin_error_message = exec_sql_statement(tool, exp, origin_db, sql_statement)

    conversation_cnt = 0  # conversation_cnt = 0:初始第一条prompt
    # 边界1：达到最大迭代次数
    while conversation_cnt <= iteration_num:
        prompt_messages = None
        if conversation_cnt == 0:
            # 初始第一条prompt
            prompt_messages = prompt_template.format_messages(
                origin_db=origin_db,
                target_db=target_db,
                sql_statement=sql_statement_processed,
                examples=examples_string,
                feature_knowledge=feature_knowledge_string,
                format_instructions=format_instructions
            )
        else:
            # 边界2：判断是否需要迭代，不需要迭代则break跳出while循环
            print(error_messages)
            if error_iteration is False:
                break
            # 边界3：判断上一次得到的transfer sql执行是否执行成功，能执行成功则break直接跳出循环，执行失败则进行下面的error信息迭代处理
            if len(error_messages) and error_messages[-1] == "None":
                break

            # error信息迭代处理：
            # 针对执行失败的transfer sql，将执行的error信息返回给llm，提示llm根据error信息重新生成新的transfer sql，反复迭代
            # 此处运用了ConversationBufferMemory()，并且规定了最高迭代次数为 iteration_num

            # 迭代的prompt：每次取error_messages数组的最后一个元素，则为最新的报错信息
            prompt_messages = iterate_prompt_template.format_messages(
                error_message=error_messages[-1] if len(error_messages) else "",
                format_instructions=iterate_format_instructions
            )

        """
        try:

        except Exception as e:
            print("transfer llm:")
            print(e)
        """
        cost = {}
        with (get_openai_callback() as cb):
            print("Prompt_messages: " + prompt_messages[0].content)
            # print("Prompt_messages: " + prompt_messages[0].content)
            response = conversation.predict(input=prompt_messages[0].content)
            output_dict = output_parser.parse(response)
            # print(response)
            print("output_dict: " + str(output_dict))
            cost["Total Tokens"] = cb.total_tokens
            cost["Prompt Tokens"] = cb.prompt_tokens
            cost["Completion Tokens"] = cb.completion_tokens
            cost["Total Cost (USD)"] = cb.total_cost  # 用了4o-mini以后变成0.0了，还没修改，也可以用户token乘单价计算

            exec_result, exec_time, error_message = exec_sql_statement(tool, exp, target_db, output_dict["TransferSQL"])
            costs.append(cost)
            transfer_results.append(output_dict)
            exec_results.append(str(exec_result))
            exec_times.append(str(exec_time))
            # 简化error_message,只留下关键部分
            """
            if error_message:
                error_message = error_message.split(":")[1]
            """
            print(error_messages)
            error_messages.append(str(error_message))
            if not error_message and not origin_error_message and exec_result == origin_exec_result:
                exec_equalities.append(True)
            else:
                exec_equalities.append(False)
        conversation_cnt += 1

    return costs, transfer_results, exec_results, exec_times, error_messages, str(origin_exec_result), str(origin_exec_time), str(origin_error_message), exec_equalities

def pinolo_qtran_run(input_filename,tool,temperature=0.3, model="gpt-4o-mini",error_iteration=True,iteration_num=4,FewShot=False,with_knowledge=True):
    return

def get_feature_knowledge(value,feature_type):
    if feature_type == "function":
        mapping_indexes = value["SqlPotentialDialectFunctionMapping"]

def transfer_data(tool,temperature, model, error_iteration, iteration_num, FewShot, with_knowledge, output_name, origin_db_name, target_db_name, len_low, len_high, IsRandom, num, sqls_type):
    """
    # transfer data：将经过init_data()处理的初始化后数据，逐条进行transfer llm的转换并存储结果
    # 源文件：Pinolo Output/output_test下ALL和RANDOM文件夹内的init_output1_mariadb_x_x_originalSql_all.json,init_output1_mariadb_x_x_originalSqlsim_all.json
    # 目标文件：Pinolo Output/output_test_results下ALL和RANDOM文件夹内的文件
    """

    results_filename = None
    sqls_filename = None
    if IsRandom:
        sql_temp = output_name + "_" + origin_db_name + "_to_" + target_db_name + "_" + str(len_low) + "_" + str(
            len_high) + "_originalSql_random_" + str(num) + ".jsonl"
        sqlsim_temp = output_name + "_" + origin_db_name + "_to_" + target_db_name + "_" + str(len_low) + "_" + str(
            len_high) + "_originalSqlsim_random_" + str(num) + ".jsonl"
        res_sql_temp = output_name + "_" + origin_db_name + "_to_" + target_db_name + "_" + str(len_low) + "_" + str(
            len_high) + "_originalSql_random_" + str(num) + ".jsonl"
        res_sqlsim_temp = output_name + "_" + origin_db_name + "_to_" + target_db_name + "_" + str(len_low) + "_" + str(
            len_high) + "_originalSqlsim_random_" + str(num) + ".jsonl"
        if FewShot:
            res_sql_temp = "fewshot_"+res_sql_temp
            res_sqlsim_temp = "fewshot_" + res_sqlsim_temp
        if error_iteration:
            res_sql_temp = "iterated_"+res_sql_temp
            res_sqlsim_temp = "iterated_" + res_sqlsim_temp
        if sqls_type == "origin":
            sqls_filename = os.path.join("..\..\Output\TransferLLM\Pinolo", "PotentialDialectFeatures", "RANDOM", "init_"+sql_temp)
            results_filename = os.path.join("..\..\Output\TransferLLM\Pinolo", "Results_With_Feature_Knowledge", "RANDOM", res_sql_temp)
        elif sqls_type == "simple":
            sqls_filename = os.path.join("..\..\Output\TransferLLM\Pinolo", "PotentialDialectFeatures", "RANDOM", "init_"+sqlsim_temp)
            results_filename = os.path.join("..\..\Output\TransferLLM\Pinolo", "Results_With_Feature_Knowledge", "RANDOM", res_sqlsim_temp)
    else:
        sql_temp = output_name + "_" + origin_db_name + "_to_" + target_db_name + "_" + str(len_low) + "_" + str(
            len_high) + "_originalSql_all_" + str(num) + ".jsonl"
        sqlsim_temp = output_name + "_" + origin_db_name + "_to_" + target_db_name + "_" + str(len_low) + "_" + str(
            len_high) + "_originalSqlsim_all_" + str(num) + ".jsonl"
        res_sql_temp = output_name + "_" + origin_db_name + "_to_" + target_db_name+"_" + str(len_low) + "_" + str(len_high) + "_originalSql_all.jsonl"
        res_sqlsim_temp = output_name + "_" + origin_db_name + "_to_" + target_db_name+"_" + str(len_low) + "_" + str(len_high) + "_originalSqlsim_all.jsonl"
        if FewShot:
            res_sql_temp = "fewshot_" + res_sql_temp
            res_sqlsim_temp = "fewshot_" + res_sqlsim_temp
        if error_iteration:
            res_sql_temp = "iterated_" + res_sql_temp
            res_sqlsim_temp = "iterated_" + res_sqlsim_temp
        if sqls_type == "origin":
            sqls_filename = os.path.join("..\..\Output\TransferLLM\Pinolo", "PotentialDialectFeatures", "ALL", "init_"+sql_temp)
            results_filename = os.path.join("..\..\Output\TransferLLM\Pinolo", "Results_With_Feature_Knowledge", "ALL", res_sql_temp)
        elif sqls_type == "simple":
            sqls_filename = os.path.join("..\..\Output\TransferLLM\Pinolo", "PotentialDialectFeatures", "ALL", "init_"+sqlsim_temp)
            results_filename = os.path.join("..\..\Output\TransferLLM\Pinolo", "Results_With_Feature_Knowledge", "ALL", res_sqlsim_temp)

    processed_cnt = 0
    if os.path.exists(results_filename):
        with open(results_filename, "r", encoding="utf-8") as rf:
            processed_cnt = len(rf.readlines())

    with open(sqls_filename, "r", encoding="utf-8") as rf:
        Sqls = rf.readlines()

    for index in range(len(Sqls)):
        # for index in range(30):
        value = json.loads(Sqls[index])
        print(index)
        if value["index"] < processed_cnt:
            continue
        print(value)
        costs, transfer_results, exec_results, exec_times, error_messages, origin_exec_result, origin_exec_time, origin_error_message, exec_equalities = transfer_llm(
            tool=tool,
            temperature=temperature,
            model=model,
            error_iteration=error_iteration,
            iteration_num=iteration_num,
            FewShot=FewShot,
            with_knowledge=with_knowledge,
            origin_db=origin_db_name,
            target_db=target_db_name,
            test_info=value
        )

        value["SqlExecResult"] = origin_exec_result
        value["SqlExecTime"] = origin_exec_time
        value["SqlExecError"] = origin_error_message

        value["TransferResult"] = transfer_results
        value["TransferCost"] = costs
        value["TransferSqlExecResult"] = exec_results
        value["TransferSqlExecTime"] = exec_times
        value["TransferSqlExecError"] = error_messages  # 记录transfer sql的多次执行是否有报错：如果为None则表示成功执行，如果不是None而是具体报错则说明执行失败
        value["TransferSqlExecEqualities"] = exec_equalities  # 记录transfer sql的多次执行结果是否与origin sql一样：如果为True则说明一样，否则为不一样

        with open(results_filename, 'a', encoding='utf-8') as a:
            json.dump(value, a)
            a.write('\n')

        try:
            a = 1
        except Exception as e:
            print(e)


# sql_type:"origin"或"simple"，分别代表原始sql和简化后的sql
def exec_transfer_llm(temperature, model, error_iteration, iteration_num, FewShot, with_knowledge, output_name, origin_db_name, target_db_name, len_low, len_high, IsRandom, num, sqls_type):
    load_data(output_name, origin_db_name, len_low, len_high, IsRandom, num)
    init_data(output_name, origin_db_name, len_low, len_high, IsRandom, num)
    transfer_data("pinolo",temperature, model, error_iteration, iteration_num, FewShot, with_knowledge, output_name, origin_db_name, target_db_name, len_low, len_high, IsRandom, num, sqls_type)



