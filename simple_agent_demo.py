#!/usr/bin/env python3
"""
纯 OpenAI Function Calling 实现的 Agent (无需 LangChain)
展示 Agent 和微调 LLM 的核心区别

特点:
1. 只依赖 openai 库 (已安装)
2. 使用 OpenAI 原生 Function Calling
3. 完整展示 Agent 的推理循环
"""

import os
import json
import httpx
from typing import List, Dict, Any, Callable
from openai import OpenAI


# ============================================================================
# 定义工具函数
# ============================================================================


def validate_sql_syntax(sql: str, db_type: str = "mongodb") -> str:
    """验证 SQL/NoSQL 语法"""
    if not sql or not sql.strip():
        return json.dumps({"valid": False, "error": "SQL 不能为空"})

    if db_type == "mongodb":
        try:
            if sql.strip().startswith("{"):
                cmd = json.loads(sql)
                if "op" in cmd and "collection" in cmd:
                    return json.dumps({"valid": True})
                return json.dumps(
                    {"valid": False, "error": "必须包含 op 和 collection"}
                )
        except json.JSONDecodeError as e:
            return json.dumps({"valid": False, "error": f"JSON 解析失败: {str(e)}"})

    elif db_type == "redis":
        parts = sql.strip().split()
        if len(parts) < 1:
            return json.dumps({"valid": False, "error": "命令为空"})

        valid_cmds = ["SET", "GET", "DEL", "HSET", "HGET", "ZADD", "LPUSH", "SADD"]
        if parts[0].upper() not in valid_cmds:
            return json.dumps({"valid": False, "error": f"未知命令: {parts[0]}"})

        return json.dumps({"valid": True})

    return json.dumps({"valid": True})


def get_mutation_rules(oracle_type: str) -> str:
    """获取变异规则"""
    rules = {
        "norec": """
NoREC 变异规则:
1. 生成逻辑等价的查询
2. 结果必须完全相同
3. 常见变异:
   - 冗余条件: WHERE x > 10 AND x > 5
   - 逻辑等价: WHERE x = 1 等价于 WHERE x >= 1 AND x <= 1
   - 顺序调整: JOIN 顺序、字段顺序
""",
        "tlp": """
TLP 变异规则:
1. 将查询分解为互斥分区
2. 分区并集等于全集
3. 示例: WHERE x > 10, WHERE x <= 10, WHERE x IS NULL
""",
    }
    return rules.get(oracle_type.lower(), "未知预言机类型")


def analyze_sql_structure(sql: str, db_type: str = "redis") -> str:
    """分析 SQL 结构"""
    result = {"command": sql, "db_type": db_type, "mutable_parts": []}

    if db_type == "redis":
        parts = sql.strip().split()
        if len(parts) < 1:
            return json.dumps({"error": "命令太短"})

        cmd = parts[0].upper()

        if cmd == "SET":
            result["type"] = "key-value"
            result["key"] = parts[1] if len(parts) > 1 else None
            result["value"] = parts[2] if len(parts) > 2 else None
            result["mutable_parts"] = [
                "可以使用 SETNX 替代",
                "可以使用 SETEX 添加过期时间",
                "可以先 DEL 再 SET",
            ]

        elif cmd == "GET":
            result["type"] = "key-value"
            result["key"] = parts[1] if len(parts) > 1 else None
            result["mutable_parts"] = [
                "可以使用 MGET 单键查询",
                "可以先 EXISTS 再 GET",
                "可以使用 GETEX 添加过期逻辑",
            ]

        elif cmd in ["HSET", "HGET"]:
            result["type"] = "hash"
            result["mutable_parts"] = [
                "可以使用 HMSET 批量操作",
                "可以使用 HGETALL 后筛选",
            ]

    elif db_type == "mongodb":
        try:
            cmd_obj = json.loads(sql) if sql.strip().startswith("{") else {}
            op = cmd_obj.get("op", "")

            if op in ["find", "findOne"]:
                result["type"] = "query"
                result["operation"] = op
                result["mutable_parts"] = [
                    "可以添加等价 filter 条件",
                    "可以使用 $and/$or 重组",
                    "可以添加 limit(1) 等价于 findOne",
                ]
        except:
            result["error"] = "无法解析"

    return json.dumps(result, ensure_ascii=False, indent=2)


# ============================================================================
# Agent 核心实现
# ============================================================================


class SimpleAgent:
    """
    纯 OpenAI Function Calling 实现的 Agent
    """

    # 定义可用工具
    TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "validate_sql_syntax",
                "description": "验证 SQL/NoSQL 命令的语法是否正确",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "要验证的 SQL/NoSQL 命令",
                        },
                        "db_type": {
                            "type": "string",
                            "description": "数据库类型",
                            "enum": ["redis", "mongodb", "mysql"],
                        },
                    },
                    "required": ["sql", "db_type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_mutation_rules",
                "description": "获取指定预言机类型的变异规则",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "oracle_type": {
                            "type": "string",
                            "description": "预言机类型",
                            "enum": ["norec", "tlp", "pqs"],
                        }
                    },
                    "required": ["oracle_type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "analyze_sql_structure",
                "description": "分析 SQL/NoSQL 命令的结构,识别可变异的部分",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "要分析的 SQL/NoSQL 命令",
                        },
                        "db_type": {"type": "string", "description": "数据库类型"},
                    },
                    "required": ["sql", "db_type"],
                },
            },
        },
    ]

    # 工具函数映射
    TOOL_FUNCTIONS = {
        "validate_sql_syntax": validate_sql_syntax,
        "get_mutation_rules": get_mutation_rules,
        "analyze_sql_structure": analyze_sql_structure,
    }

    def __init__(self, model: str = "gpt-4o-mini"):
        """初始化 Agent"""
        proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
        http_client = httpx.Client(proxies=proxy) if proxy else None

        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"), http_client=http_client
        )
        self.model = model

    def run(
        self, task: str, max_iterations: int = 10, verbose: bool = True
    ) -> Dict[str, Any]:
        """
        运行 Agent 主循环

        这是 Agent 和微调 LLM 的核心区别:
        - 微调 LLM: 一次调用,直接输出
        - Agent: 多轮循环,可以调用工具、观察结果、继续推理
        """
        messages = [
            {
                "role": "system",
                "content": """你是 SQL 变异专家。你的任务是生成符合预言机规则的 SQL 变异。

工作流程:
1. 使用 get_mutation_rules 了解预言机规则
2. 使用 analyze_sql_structure 分析原始命令
3. 基于分析结果生成 3 个变异命令
4. 使用 validate_sql_syntax 验证每个变异
5. 返回验证通过的变异列表 (JSON 格式)

输出格式:
{
  "mutations": [
    {
      "mutated_sql": "变异后的命令",
      "explanation": "为什么这样变异",
      "validated": true/false
    }
  ]
}""",
            },
            {"role": "user", "content": task},
        ]

        reasoning_steps = []

        for iteration in range(max_iterations):
            if verbose:
                print(f"\n{'='*70}")
                print(f"📥 Agent 迭代 {iteration + 1}/{max_iterations}")
                print(f"{'='*70}")

            # 调用 LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.TOOLS,
                tool_choice="auto",
                temperature=0.7,
            )

            message = response.choices[0].message
            messages.append(message.model_dump())

            # 如果没有工具调用,说明 Agent 完成任务
            if not message.tool_calls:
                if verbose:
                    print(f"\n✅ Agent 完成任务")
                    print(f"📝 最终输出:\n{message.content[:500]}...")

                return {
                    "status": "success",
                    "output": message.content,
                    "reasoning_steps": reasoning_steps,
                    "num_iterations": iteration + 1,
                    "num_llm_calls": iteration + 1,
                }

            # 执行工具调用
            if verbose:
                print(f"\n🔧 Agent 调用工具:")

            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                if verbose:
                    print(
                        f"  - {function_name}({json.dumps(function_args, ensure_ascii=False)})"
                    )

                # 执行工具函数
                function_to_call = self.TOOL_FUNCTIONS[function_name]
                function_result = function_to_call(**function_args)

                if verbose:
                    print(f"    → {function_result[:150]}...")

                # 记录推理步骤
                reasoning_steps.append(
                    {
                        "iteration": iteration + 1,
                        "tool": function_name,
                        "input": function_args,
                        "output": function_result,
                    }
                )

                # 将工具结果添加到对话
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": function_result,
                    }
                )

        return {
            "status": "max_iterations_reached",
            "reasoning_steps": reasoning_steps,
            "num_iterations": max_iterations,
        }


# ============================================================================
# 对比测试
# ============================================================================


def compare_agent_vs_finetune():
    """对比 Agent 和微调 LLM"""
    print("=" * 80)
    print("Agent vs 微调 LLM 对比测试 (纯 OpenAI 实现)")
    print("=" * 80)

    test_cases = [
        {"sql": "SET mykey hello", "db_type": "redis", "oracle": "norec"},
        {"sql": "GET mykey", "db_type": "redis", "oracle": "norec"},
    ]

    for idx, test in enumerate(test_cases, 1):
        print(f"\n{'#'*80}")
        print(f"测试 {idx}: {test['sql']}")
        print(f"{'#'*80}")

        task = f"""
请为以下 {test['db_type']} 命令生成 3 个符合 {test['oracle']} 预言机的变异:

原始命令: {test['sql']}

要求:
1. 每个变异必须符合 {test['oracle']} 规则
2. 必须验证语法正确性
3. 提供详细的变异说明
"""

        # 运行 Agent
        print("\n" + "=" * 80)
        print("📥 方法 1: Agent (带工具调用)")
        print("=" * 80)

        agent = SimpleAgent(model="gpt-4o-mini")
        result = agent.run(task, max_iterations=10, verbose=True)

        print("\n" + "=" * 80)
        print("📊 Agent 执行总结")
        print("=" * 80)
        print(f"状态: {result['status']}")
        print(f"迭代次数: {result.get('num_iterations', 0)}")
        print(f"LLM 调用次数: {result.get('num_llm_calls', 0)}")
        print(f"工具调用次数: {len(result.get('reasoning_steps', []))}")

        # 对比微调 LLM
        print("\n" + "=" * 80)
        print("🎯 方法 2: 微调 LLM (一次调用)")
        print("=" * 80)

        finetune_model = os.getenv("SEMANTIC_MUTATION_LLM_ID")
        if finetune_model:
            print(f"使用微调模型: {finetune_model}")
            print("特点: 一次调用直接输出,无工具调用,无推理过程")
            print("(这里不实际调用,仅对比概念)")
        else:
            print("⚠️  未设置 SEMANTIC_MUTATION_LLM_ID")

    # 总结对比
    print("\n" + "=" * 80)
    print("📋 核心区别总结")
    print("=" * 80)

    comparison = """
┌─────────────────────┬──────────────────────┬──────────────────────┐
│      特性           │    微调 LLM          │       Agent          │
├─────────────────────┼──────────────────────┼──────────────────────┤
│ 执行方式            │ 一次调用,直接输出    │ 多轮循环,逐步推理    │
│ 工具使用            │ ✗ 不能调用工具       │ ✓ 可以调用工具       │
│ 自我验证            │ ✗ 无法验证生成结果   │ ✓ 可以验证并修正     │
│ 推理过程            │ ✗ 黑盒,不可见        │ ✓ 完全透明可追踪     │
│ 错误处理            │ ✗ 无法自我纠正       │ ✓ 可以重试和调整     │
│ LLM 调用次数        │ 1 次                 │ 3-10 次 (视任务复杂度)│
│ 响应速度            │ 快 (1-2秒)           │ 较慢 (5-15秒)        │
│ 开发成本            │ 高 (需要训练数据)    │ 低 (只需定义工具)    │
│ 维护成本            │ 高 (需要重新训练)    │ 低 (修改 Prompt)     │
│ 适用场景            │ 固定格式输出         │ 复杂推理任务         │
└─────────────────────┴──────────────────────┴──────────────────────┘

💡 关键洞察:
1. Agent = 通用 LLM + 工具 + 推理循环
2. 微调 LLM = 特定任务的权重更新
3. Agent 更灵活,微调 LLM 更快速
4. 可以结合: Agent 做决策,微调 LLM 做执行
"""

    print(comparison)


if __name__ == "__main__":
    compare_agent_vs_finetune()
