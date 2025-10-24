#!/usr/bin/env python3
"""
LangChain Agent 版本的 SQL 变异器
对比微调 LLM,展示 Agent 的优势:
1. 可以调用工具验证 SQL
2. 可以自主推理选择变异策略
3. 可以观察结果并调整
"""

import os
import json
from typing import List, Dict, Any
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


# ============================================================================
# 定义工具 (Tools) - Agent 可以调用的函数
# ============================================================================


@tool
def validate_sql_syntax(sql: str, db_type: str = "mongodb") -> str:
    """
    验证 SQL 或 NoSQL 命令的语法是否正确

    Args:
        sql: SQL 或 NoSQL 命令字符串
        db_type: 数据库类型 (mongodb, redis, mysql 等)

    Returns:
        验证结果: "valid" 或错误信息
    """
    # 简化版本 - 实际应该连接数据库验证
    # 这里只做基本检查
    if not sql or not sql.strip():
        return "错误: SQL 不能为空"

    if db_type == "mongodb":
        # 检查是否是有效的 MongoDB 命令 JSON
        try:
            if sql.strip().startswith("{"):
                cmd = json.loads(sql)
                if "op" in cmd and "collection" in cmd:
                    return "valid"
                return "错误: MongoDB 命令必须包含 'op' 和 'collection' 字段"
            else:
                return "错误: MongoDB 命令应该是 JSON 格式"
        except json.JSONDecodeError as e:
            return f"错误: JSON 解析失败 - {str(e)}"

    elif db_type == "redis":
        # 检查 Redis 命令格式
        parts = sql.strip().upper().split()
        if len(parts) < 1:
            return "错误: Redis 命令为空"

        valid_commands = [
            "SET",
            "GET",
            "DEL",
            "HSET",
            "HGET",
            "ZADD",
            "ZRANGE",
            "SADD",
            "SMEMBERS",
            "LPUSH",
            "LPOP",
            "INCR",
            "DECR",
        ]
        if parts[0] not in valid_commands:
            return f"错误: 未知的 Redis 命令 '{parts[0]}'"

        return "valid"

    return "valid"  # 其他数据库暂时通过


@tool
def get_mutation_rules(oracle_type: str) -> str:
    """
    获取指定预言机类型的变异规则

    Args:
        oracle_type: 预言机类型 (norec, tlp, pqs 等)

    Returns:
        变异规则的详细说明
    """
    rules = {
        "norec": """
NoREC (No Redundant Elimination Check) 变异规则:
1. 生成逻辑等价的查询,结果应该完全相同
2. 常见变异方式:
   - 添加冗余条件: WHERE x > 10 → WHERE x > 10 AND x > 5
   - 使用逻辑等价: WHERE x = 1 → WHERE x >= 1 AND x <= 1
   - 子查询改写: WHERE id IN (...) → WHERE EXISTS (...)
   - JOIN 顺序调整: A JOIN B → B JOIN A (等价 JOIN)
3. 验证方式: 结果集应该完全相等 (行数相同、内容一致)
""",
        "tlp": """
TLP (Ternary Logic Partitioning) 变异规则:
1. 将查询分解为三个互斥的部分
2. 变异方式:
   - 原查询: SELECT * FROM t WHERE x > 10
   - 分解为:
     * Q1: WHERE x > 10
     * Q2: WHERE x <= 10 OR x IS NULL
     * Q3: WHERE x IS NULL
   - 验证: Q1 UNION Q2 应等于全表
3. 验证方式: 部分查询的并集应等于全查询
""",
        "pqs": """
PQS (Partitioned Query Synthesis) 变异规则:
1. 通过分区条件生成子查询
2. 变异方式:
   - 将 WHERE 条件拆分为多个子条件
   - 每个子查询处理一个分区
   - UNION 所有子查询结果
3. 验证方式: UNION 结果应等于原查询
""",
    }

    return rules.get(oracle_type.lower(), "未知的预言机类型")


@tool
def analyze_sql_structure(sql: str, db_type: str = "redis") -> str:
    """
    分析 SQL/NoSQL 命令的结构,识别可以变异的部分

    Args:
        sql: SQL 或 NoSQL 命令
        db_type: 数据库类型

    Returns:
        结构分析结果,包括可变异的部分
    """
    analysis = {"command": sql, "db_type": db_type, "mutable_parts": []}

    if db_type == "redis":
        parts = sql.strip().split()
        if len(parts) < 2:
            return json.dumps({"error": "命令太短,无法分析"})

        cmd = parts[0].upper()

        if cmd in ["SET", "GET", "DEL"]:
            analysis["type"] = "key-value"
            analysis["key"] = parts[1] if len(parts) > 1 else None
            analysis["value"] = parts[2] if len(parts) > 2 else None
            analysis["mutable_parts"] = [
                "可以生成等价的键名变异",
                "可以生成值的等价表示",
                "可以使用 SETNX 或 SETEX 替代 SET",
            ]

        elif cmd in ["HSET", "HGET", "HDEL"]:
            analysis["type"] = "hash"
            analysis["key"] = parts[1] if len(parts) > 1 else None
            analysis["field"] = parts[2] if len(parts) > 2 else None
            analysis["mutable_parts"] = [
                "可以使用 HMSET 批量设置",
                "可以使用 HGETALL 然后筛选",
                "可以先 HEXISTS 再 HGET",
            ]

        elif cmd in ["ZADD", "ZRANGE"]:
            analysis["type"] = "sorted-set"
            analysis["mutable_parts"] = [
                "可以调整分数范围",
                "可以使用 ZRANGEBYSCORE",
                "可以使用 ZREVRANGE 反向",
            ]

    elif db_type == "mongodb":
        try:
            cmd_obj = json.loads(sql) if sql.strip().startswith("{") else {}
            op = cmd_obj.get("op", "")

            analysis["type"] = "document"
            analysis["operation"] = op

            if op in ["find", "findOne"]:
                analysis["mutable_parts"] = [
                    "可以添加等价的 filter 条件",
                    "可以使用 $and/$or 重组条件",
                    "可以调整 projection 字段",
                    "可以添加 sort 后取第一个 (findOne)",
                ]

            elif op in ["insert", "insertOne"]:
                analysis["mutable_parts"] = [
                    "可以改变字段顺序 (不影响逻辑)",
                    "可以添加额外字段后删除",
                ]

            elif op in ["update", "updateOne"]:
                analysis["mutable_parts"] = [
                    "可以使用 $set 的等价操作",
                    "可以拆分为多个 update",
                    "可以使用 findAndModify",
                ]

        except:
            analysis["error"] = "无法解析 MongoDB 命令"

    return json.dumps(analysis, indent=2, ensure_ascii=False)


@tool
def compare_mutation_logic(
    original_sql: str, mutated_sql: str, oracle_type: str
) -> str:
    """
    比较原始 SQL 和变异 SQL 的逻辑关系

    Args:
        original_sql: 原始 SQL
        mutated_sql: 变异后的 SQL
        oracle_type: 预言机类型

    Returns:
        逻辑关系分析结果
    """
    result = {
        "original": original_sql,
        "mutated": mutated_sql,
        "oracle": oracle_type,
        "expected_relation": "",
        "explanation": "",
    }

    if oracle_type.lower() == "norec":
        result["expected_relation"] = "完全相等 (结果集相同)"
        result["explanation"] = "NoREC 要求变异后的查询逻辑等价,应该返回完全相同的结果"

    elif oracle_type.lower() == "tlp":
        result["expected_relation"] = "分区并集等于全集"
        result["explanation"] = "TLP 将查询分解为互斥分区,所有分区的并集应等于原查询"

    elif oracle_type.lower() == "pqs":
        result["expected_relation"] = "子查询并集等于原查询"
        result["explanation"] = "PQS 将查询拆分为多个子查询,UNION 后应等于原查询"

    return json.dumps(result, indent=2, ensure_ascii=False)


# ============================================================================
# Agent 系统
# ============================================================================


class SQLMutationAgent:
    """
    基于 LangChain 的 SQL 变异 Agent
    """

    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.7):
        """
        初始化 Agent

        Args:
            model_name: OpenAI 模型名称
            temperature: 生成温度 (0-1),越高越随机
        """
        # 初始化 LLM
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_api_base=os.getenv("OPENAI_API_BASE"),
            http_client=self._get_http_client(),
        )

        # 定义工具列表
        self.tools = [
            validate_sql_syntax,
            get_mutation_rules,
            analyze_sql_structure,
            compare_mutation_logic,
        ]

        # 创建 Agent
        self.agent = self._create_agent()

        # 创建 Agent 执行器
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,  # 显示推理过程
            max_iterations=10,  # 最大迭代次数
            return_intermediate_steps=True,  # 返回中间步骤
        )

    def _get_http_client(self):
        """配置代理的 HTTP 客户端"""
        import httpx

        proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
        if proxy:
            return httpx.Client(proxies=proxy)
        return None

    def _create_agent(self):
        """创建 OpenAI Functions Agent"""
        # 定义系统 Prompt
        system_prompt = """你是一个专业的 SQL/NoSQL 变异专家。你的任务是:

1. 分析给定的 SQL/NoSQL 命令
2. 根据指定的预言机类型生成逻辑相关的变异
3. 确保变异后的命令符合预言机的期望关系
4. 验证生成的变异命令的语法正确性

你可以使用以下工具:
- validate_sql_syntax: 验证 SQL 语法
- get_mutation_rules: 获取变异规则
- analyze_sql_structure: 分析 SQL 结构
- compare_mutation_logic: 比较逻辑关系

工作流程:
1. 首先使用 get_mutation_rules 了解预言机规则
2. 使用 analyze_sql_structure 分析原始命令
3. 基于规则生成 3-5 个变异命令
4. 使用 validate_sql_syntax 验证每个变异
5. 使用 compare_mutation_logic 确认逻辑关系
6. 返回验证通过的变异列表

输出格式 (JSON):
{
    "mutations": [
        {
            "mutated_sql": "变异后的命令",
            "explanation": "变异说明",
            "expected_relation": "预期的逻辑关系"
        }
    ]
}
"""

        # 创建 Prompt 模板
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        # 创建 Agent
        agent = create_openai_functions_agent(
            llm=self.llm, tools=self.tools, prompt=prompt
        )

        return agent

    def mutate(
        self,
        sql: str,
        db_type: str = "redis",
        oracle_type: str = "norec",
        num_mutations: int = 3,
    ) -> Dict[str, Any]:
        """
        对给定的 SQL/NoSQL 命令进行变异

        Args:
            sql: 原始 SQL/NoSQL 命令
            db_type: 数据库类型
            oracle_type: 预言机类型
            num_mutations: 期望生成的变异数量

        Returns:
            包含变异结果和推理过程的字典
        """
        # 构造输入
        input_text = f"""
请对以下 {db_type} 命令生成 {num_mutations} 个符合 {oracle_type} 预言机的变异:

原始命令:
{sql}

要求:
1. 每个变异必须符合 {oracle_type} 的逻辑关系
2. 必须验证语法正确性
3. 提供详细的变异说明
"""

        # 执行 Agent
        result = self.agent_executor.invoke({"input": input_text})

        return {
            "original_sql": sql,
            "db_type": db_type,
            "oracle_type": oracle_type,
            "agent_output": result["output"],
            "intermediate_steps": result["intermediate_steps"],
        }

    def batch_mutate(
        self, sql_list: List[str], db_type: str = "redis", oracle_type: str = "norec"
    ) -> List[Dict[str, Any]]:
        """
        批量变异多个 SQL 命令

        Args:
            sql_list: SQL 命令列表
            db_type: 数据库类型
            oracle_type: 预言机类型

        Returns:
            变异结果列表
        """
        results = []
        for idx, sql in enumerate(sql_list):
            print(f"\n{'='*70}")
            print(f"处理第 {idx+1}/{len(sql_list)} 个命令: {sql[:50]}...")
            print(f"{'='*70}\n")

            try:
                result = self.mutate(sql, db_type, oracle_type)
                results.append(result)
            except Exception as e:
                print(f"❌ 错误: {str(e)}")
                results.append({"original_sql": sql, "error": str(e)})

        return results


# ============================================================================
# 主程序 - 对比微调 LLM 和 Agent
# ============================================================================


def main():
    """主函数: 演示 Agent 的工作方式"""
    print("=" * 80)
    print("LangChain Agent SQL 变异器 Demo")
    print("=" * 80)

    # 初始化 Agent
    print("\n📥 初始化 Agent...")
    agent = SQLMutationAgent(model_name="gpt-4o-mini", temperature=0.7)

    # 测试用例 1: Redis 命令
    print("\n" + "=" * 80)
    print("测试 1: Redis 命令变异 (NoREC)")
    print("=" * 80)

    redis_sql = "SET mykey hello"
    result1 = agent.mutate(
        redis_sql, db_type="redis", oracle_type="norec", num_mutations=3
    )

    print("\n📊 变异结果:")
    print(
        json.dumps(
            {"original": result1["original_sql"], "output": result1["agent_output"]},
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\n🔍 Agent 推理步骤:")
    for idx, step in enumerate(result1["intermediate_steps"], 1):
        action, observation = step
        print(f"\n步骤 {idx}:")
        print(f"  工具: {action.tool}")
        print(f"  输入: {action.tool_input}")
        print(f"  输出: {observation[:200]}...")  # 截断长输出

    # 测试用例 2: MongoDB 命令
    print("\n" + "=" * 80)
    print("测试 2: MongoDB 命令变异 (NoREC)")
    print("=" * 80)

    mongodb_sql = '{"op":"findOne","collection":"kv","filter":{"_id":"mykey"}}'
    result2 = agent.mutate(
        mongodb_sql, db_type="mongodb", oracle_type="norec", num_mutations=3
    )

    print("\n📊 变异结果:")
    print(
        json.dumps(
            {"original": result2["original_sql"], "output": result2["agent_output"]},
            indent=2,
            ensure_ascii=False,
        )
    )

    # 保存结果
    output_file = "Output/agent_mutation_demo.json"
    os.makedirs("Output", exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {"redis_test": result1, "mongodb_test": result2},
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\n✅ 结果已保存到: {output_file}")

    print("\n" + "=" * 80)
    print("🎯 Agent vs 微调 LLM 对比:")
    print("=" * 80)
    print(
        """
微调 LLM:
  ✗ 无法验证生成的 SQL 语法
  ✗ 无法主动查询变异规则
  ✗ 无法分析 SQL 结构
  ✗ 推理过程不可见
  ✓ 响应速度快
  ✓ 成本较低 (单次调用)

Agent:
  ✓ 可以调用工具验证 SQL
  ✓ 可以主动查询规则和知识
  ✓ 可以分析和推理
  ✓ 推理过程完全透明
  ✓ 可以自我纠错和调整
  ✗ 需要多次 LLM 调用 (成本稍高)
  ✗ 响应时间较长
"""
    )


if __name__ == "__main__":
    main()
