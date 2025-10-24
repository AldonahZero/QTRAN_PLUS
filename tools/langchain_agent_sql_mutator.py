#!/usr/bin/env python3
"""
LangChain Agent 实现的 SQL 变异工具
展示 Agent 如何通过工具调用和推理来生成高质量的 SQL 变异
"""

import os
import json
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import tool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

# 设置代理
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

# ============================================================================
# 定义工具 (Tools)
# ============================================================================


@tool
def get_oracle_rules(oracle_type: str) -> str:
    """获取预言机规则说明

    Args:
        oracle_type: 预言机类型 (norec, tlp, pqs)

    Returns:
        预言机规则详细说明
    """
    rules = {
        "norec": """
NoREC (No Regression Checking) 预言机:
- 目标: 生成逻辑等价的 SQL 变异
- 预期: 两个查询的结果集应该完全相同
- 策略:
  1. 条件重组: WHERE x>10 AND x<20 → WHERE x BETWEEN 11 AND 19
  2. 冗余条件: WHERE x>10 → WHERE x>10 AND x>5
  3. 逻辑等价: WHERE x=1 OR x=2 → WHERE x IN (1,2)
  4. 子查询转换: JOIN → WHERE EXISTS
- 注意: 不改变查询语义,只改变表达方式
""",
        "tlp": """
TLP (Ternary Logic Partitioning) 预言机:
- 目标: 将查询结果集分区
- 预期: Q = Q_true UNION Q_false UNION Q_null
- 策略:
  1. 原始查询: SELECT * FROM t WHERE condition
  2. True分区: SELECT * FROM t WHERE condition IS TRUE
  3. False分区: SELECT * FROM t WHERE condition IS FALSE
  4. Null分区: SELECT * FROM t WHERE condition IS NULL
- 注意: 三个结果集的并集应该等于原始结果
""",
        "pqs": """
PQS (Partitioned Query Synthesis) 预言机:
- 目标: 通过分区条件重构查询
- 预期: 原始结果 = 所有分区结果的并集
- 策略:
  1. 识别分区列: SELECT * FROM t WHERE x>10
  2. 分区查询: WHERE x BETWEEN 11 AND 20 UNION WHERE x>20
  3. 验证完整性: 所有分区覆盖原始条件
- 注意: 分区必须互斥且完整
""",
    }
    return rules.get(oracle_type.lower(), "未知的预言机类型")


@tool
def validate_sql_syntax(sql: str, db_type: str) -> str:
    """验证 SQL 语法是否正确

    Args:
        sql: SQL 语句
        db_type: 数据库类型 (mysql, postgres, mongodb, redis)

    Returns:
        验证结果 (valid/invalid + 错误信息)
    """
    # 简单的语法检查
    sql = sql.strip()

    # 基本关键字检查
    if db_type in ["mysql", "postgres"]:
        if not any(
            keyword in sql.upper()
            for keyword in ["SELECT", "INSERT", "UPDATE", "DELETE"]
        ):
            return "❌ 无效: SQL 必须包含 SELECT/INSERT/UPDATE/DELETE"

        # 检查括号匹配
        if sql.count("(") != sql.count(")"):
            return "❌ 无效: 括号不匹配"

        # 检查分号
        if not sql.endswith(";"):
            return "⚠️ 警告: SQL 应该以分号结尾"

        return "✅ 语法有效"

    elif db_type == "mongodb":
        try:
            # 检查是否是有效的 JSON
            if sql.startswith("{"):
                parsed = json.loads(sql)
                if "op" not in parsed:
                    return "❌ 无效: MongoDB 命令必须包含 'op' 字段"
                if "collection" not in parsed:
                    return "❌ 无效: MongoDB 命令必须包含 'collection' 字段"
                return "✅ 语法有效"
            else:
                return "❌ 无效: MongoDB 命令必须是 JSON 格式"
        except json.JSONDecodeError as e:
            return f"❌ 无效: JSON 解析错误 - {str(e)}"

    elif db_type == "redis":
        parts = sql.strip().rstrip(";").split()
        if not parts:
            return "❌ 无效: 空命令"

        redis_commands = [
            "SET",
            "GET",
            "DEL",
            "ZADD",
            "ZRANGE",
            "HSET",
            "HGET",
            "LPUSH",
            "RPUSH",
            "SADD",
            "SMEMBERS",
        ]
        if parts[0].upper() not in redis_commands:
            return f"❌ 无效: 未知的 Redis 命令 '{parts[0]}'"

        return "✅ 语法有效"

    return "⚠️ 未知数据库类型"


@tool
def analyze_sql_structure(sql: str) -> str:
    """分析 SQL 结构,识别可变异的部分

    Args:
        sql: SQL 语句

    Returns:
        SQL 结构分析结果
    """
    sql_upper = sql.upper()
    analysis = {
        "has_where": "WHERE" in sql_upper,
        "has_join": "JOIN" in sql_upper,
        "has_aggregate": any(
            agg in sql_upper for agg in ["COUNT", "SUM", "AVG", "MAX", "MIN"]
        ),
        "has_group_by": "GROUP BY" in sql_upper,
        "has_order_by": "ORDER BY" in sql_upper,
        "has_subquery": "SELECT" in sql_upper and sql_upper.count("SELECT") > 1,
        "mutation_points": [],
    }

    # 识别可变异点
    if analysis["has_where"]:
        analysis["mutation_points"].append("WHERE 条件可以重组或添加冗余条件")
    if analysis["has_join"]:
        analysis["mutation_points"].append("JOIN 可以转换为子查询或 WHERE EXISTS")
    if analysis["has_aggregate"]:
        analysis["mutation_points"].append("聚合函数可以用不同方式表达")
    if analysis["has_order_by"]:
        analysis["mutation_points"].append("ORDER BY 可以添加或删除(不影响集合语义)")

    return json.dumps(analysis, indent=2, ensure_ascii=False)


# ============================================================================
# LangChain Agent 配置
# ============================================================================


def create_sql_mutation_agent(model: str = "gpt-4o-mini") -> AgentExecutor:
    """创建 SQL 变异 Agent

    Args:
        model: OpenAI 模型名称

    Returns:
        配置好的 Agent Executor
    """

    # 初始化 LLM
    llm = ChatOpenAI(model=model, temperature=0.7, model_kwargs={"seed": 42})

    # 定义 Prompt 模板
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """你是一个专业的 SQL 变异专家。你的任务是:

1. 理解用户提供的原始 SQL 和预言机类型
2. 使用工具获取预言机规则
3. 分析 SQL 结构,找出可变异的部分
4. 生成 3-5 个符合预言机规则的变异 SQL
5. 使用工具验证生成的 SQL 语法
6. 提供变异的解释和预期关系

**输出格式**:
```json
{{
  "original_sql": "原始SQL",
  "oracle": "预言机类型",
  "mutations": [
    {{
      "mutated_sql": "变异后的SQL",
      "explanation": "变异说明",
      "expected_relation": "预期关系(equal/subset/superset/disjoint)",
      "syntax_valid": true
    }}
  ]
}}
```

使用工具来辅助你的推理和验证过程。""",
            ),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    # 定义工具列表
    tools = [get_oracle_rules, validate_sql_syntax, analyze_sql_structure]

    # 创建 Agent
    agent = create_openai_functions_agent(llm, tools, prompt)

    # 创建 Agent Executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=10,
        return_intermediate_steps=True,
    )

    return agent_executor


# ============================================================================
# 测试函数
# ============================================================================


def test_agent_mutation():
    """测试 Agent 的变异能力"""

    print("=" * 80)
    print("LangChain Agent SQL 变异测试")
    print("=" * 80)

    # 创建 Agent
    agent = create_sql_mutation_agent()

    # 测试用例
    test_cases = [
        {
            "sql": "SELECT * FROM users WHERE age > 18 AND city = 'Beijing';",
            "oracle": "norec",
            "db_type": "mysql",
        },
        {
            "sql": "SELECT COUNT(*) FROM orders WHERE status = 'completed';",
            "oracle": "tlp",
            "db_type": "postgres",
        },
        {
            "sql": '{"op":"find","collection":"users","filter":{"age":{"$gt":18}}}',
            "oracle": "norec",
            "db_type": "mongodb",
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"测试用例 {i}/{len(test_cases)}")
        print(f"{'='*80}")
        print(f"原始 SQL: {test_case['sql']}")
        print(f"预言机: {test_case['oracle']}")
        print(f"数据库: {test_case['db_type']}")
        print()

        # 构建输入
        input_text = f"""
请为以下 SQL 生成变异:

原始 SQL: {test_case['sql']}
预言机类型: {test_case['oracle']}
数据库类型: {test_case['db_type']}

要求:
1. 生成 3 个高质量的变异
2. 每个变异都要验证语法
3. 解释变异的逻辑关系
"""

        try:
            # 执行 Agent
            result = agent.invoke({"input": input_text})

            print("\n" + "=" * 80)
            print("Agent 最终输出:")
            print("=" * 80)
            print(result["output"])

            print("\n" + "=" * 80)
            print("Agent 推理过程:")
            print("=" * 80)
            for step in result.get("intermediate_steps", []):
                action, observation = step
                print(f"\n🔧 工具调用: {action.tool}")
                print(f"📥 输入: {action.tool_input}")
                print(
                    f"📤 输出: {observation[:200]}..."
                    if len(str(observation)) > 200
                    else f"📤 输出: {observation}"
                )

        except Exception as e:
            print(f"\n❌ 错误: {str(e)}")

        print("\n" + "=" * 80 + "\n")


def compare_with_finetune():
    """对比 Agent 和微调 LLM 的输出"""

    print("=" * 80)
    print("Agent vs 微调 LLM 对比测试")
    print("=" * 80)

    test_sql = "SELECT * FROM products WHERE price > 100 AND stock > 0;"
    oracle = "norec"

    # 1. Agent 方式
    print("\n【方式 1: LangChain Agent】")
    print("-" * 80)
    agent = create_sql_mutation_agent()

    try:
        result = agent.invoke({"input": f"为以下 SQL 生成 NoREC 变异:\n{test_sql}"})
        print("输出:", result["output"][:500])
        print(f"推理步骤数: {len(result.get('intermediate_steps', []))}")
    except Exception as e:
        print(f"❌ Agent 错误: {str(e)}")

    # 2. 微调 LLM 方式 (模拟)
    print("\n【方式 2: 微调 LLM (模拟)】")
    print("-" * 80)
    from openai import OpenAI

    client = OpenAI()

    try:
        response = client.chat.completions.create(
            model=os.environ.get("SEMANTIC_MUTATION_LLM_ID", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "你是 SQL 变异专家,生成 NoREC 变异。"},
                {"role": "user", "content": f"为以下 SQL 生成变异:\n{test_sql}"},
            ],
            temperature=0.7,
        )
        print("输出:", response.choices[0].message.content[:500])
        print("推理步骤数: 1 (一次性输出)")
    except Exception as e:
        print(f"❌ 微调 LLM 错误: {str(e)}")

    print("\n" + "=" * 80)
    print("对比总结:")
    print("=" * 80)
    print(
        """
Agent 优势:
✅ 可以调用工具获取规则、验证语法
✅ 多步推理,逻辑更清晰
✅ 可以自我纠错和验证
✅ 可观察的推理过程

微调 LLM 优势:
✅ 一次调用即可输出
✅ 响应速度快
✅ 成本较低(单次调用)
✅ 适合批量处理
"""
    )


# ============================================================================
# 主函数
# ============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "compare":
        compare_with_finetune()
    else:
        test_agent_mutation()
