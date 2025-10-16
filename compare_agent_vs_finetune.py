#!/usr/bin/env python3
"""
对比 Agent 和微调 LLM 在 SQL 变异任务上的表现
"""

import os
import sys
import json
import time
from typing import List, Dict, Any

# 添加项目路径
sys.path.append(os.path.dirname(__file__))

from openai import OpenAI
import httpx


# ============================================================================
# 方法 1: 微调 LLM (Fine-tuned LLM)
# ============================================================================


class FinetunedMutator:
    """使用微调 LLM 进行 SQL 变异"""

    def __init__(self, model_id: str):
        # 配置代理
        proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
        http_client = httpx.Client(proxies=proxy) if proxy else None

        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"), http_client=http_client
        )
        self.model_id = model_id

    def mutate(
        self, sql: str, db_type: str = "redis", oracle_type: str = "norec"
    ) -> Dict[str, Any]:
        """
        使用微调模型生成变异

        特点:
        - 一次调用直接输出
        - 快速、简单
        - 但无法验证、无法自我纠正
        """
        start_time = time.time()

        # 构造 Prompt (微调模型已经学会了格式,所以 Prompt 很简单)
        prompt = f"""原始命令: {sql}
数据库类型: {db_type}
预言机: {oracle_type}

请生成3个变异命令。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": "你是SQL变异专家。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=1000,
            )

            output = response.choices[0].message.content
            elapsed_time = time.time() - start_time

            return {
                "method": "finetuned_llm",
                "original_sql": sql,
                "output": output,
                "elapsed_time": elapsed_time,
                "num_llm_calls": 1,  # 微调模型只调用一次
                "can_validate": False,
                "can_reason": False,
                "cost_tokens": response.usage.total_tokens,
            }

        except Exception as e:
            return {"method": "finetuned_llm", "error": str(e)}


# ============================================================================
# 方法 2: Agent (使用 LangChain)
# ============================================================================


def run_agent_mutation(
    sql: str, db_type: str = "redis", oracle_type: str = "norec"
) -> Dict[str, Any]:
    """
    使用 Agent 生成变异

    特点:
    - 可以调用工具
    - 可以验证和推理
    - 但调用次数多、时间长
    """
    from agent_sql_mutator import SQLMutationAgent

    start_time = time.time()

    try:
        agent = SQLMutationAgent(model_name="gpt-4o-mini", temperature=0.7)
        result = agent.mutate(sql, db_type, oracle_type, num_mutations=3)

        elapsed_time = time.time() - start_time

        # 统计 LLM 调用次数
        num_llm_calls = len(result["intermediate_steps"]) + 1  # 工具调用 + 最终输出

        return {
            "method": "agent",
            "original_sql": sql,
            "output": result["agent_output"],
            "elapsed_time": elapsed_time,
            "num_llm_calls": num_llm_calls,
            "can_validate": True,
            "can_reason": True,
            "reasoning_steps": [
                {
                    "tool": step[0].tool,
                    "input": step[0].tool_input,
                    "output": step[1][:100] + "..." if len(step[1]) > 100 else step[1],
                }
                for step in result["intermediate_steps"]
            ],
        }

    except Exception as e:
        return {"method": "agent", "error": str(e)}


# ============================================================================
# 主对比程序
# ============================================================================


def compare_methods():
    """对比两种方法"""
    print("=" * 100)
    print("Agent vs 微调 LLM 对比测试")
    print("=" * 100)

    # 测试用例
    test_cases = [
        {
            "sql": "SET mykey hello",
            "db_type": "redis",
            "oracle_type": "norec",
            "description": "Redis 简单 SET 命令",
        },
        {
            "sql": "GET mykey",
            "db_type": "redis",
            "oracle_type": "norec",
            "description": "Redis GET 命令",
        },
        {
            "sql": "HSET user:1001 name Alice age 25",
            "db_type": "redis",
            "oracle_type": "norec",
            "description": "Redis Hash 命令",
        },
    ]

    results = []

    for idx, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*100}")
        print(f"测试用例 {idx}: {test_case['description']}")
        print(f"{'='*100}")
        print(f"原始命令: {test_case['sql']}")
        print(f"数据库: {test_case['db_type']}")
        print(f"预言机: {test_case['oracle_type']}")

        test_result = {"test_case": test_case, "results": {}}

        # 方法 1: 微调 LLM
        print(f"\n{'-'*50}")
        print("方法 1: 微调 LLM")
        print(f"{'-'*50}")

        finetuned_model_id = os.getenv("SEMANTIC_MUTATION_LLM_ID")
        if not finetuned_model_id:
            print("⚠️  未设置 SEMANTIC_MUTATION_LLM_ID,跳过微调 LLM 测试")
            test_result["results"]["finetuned_llm"] = {"error": "未配置模型"}
        else:
            mutator = FinetunedMutator(finetuned_model_id)
            finetune_result = mutator.mutate(
                test_case["sql"], test_case["db_type"], test_case["oracle_type"]
            )

            if "error" not in finetune_result:
                print(f"✓ 耗时: {finetune_result['elapsed_time']:.2f}s")
                print(f"✓ LLM 调用次数: {finetune_result['num_llm_calls']}")
                print(f"✓ Token 消耗: {finetune_result.get('cost_tokens', 'N/A')}")
                print(f"✓ 输出:\n{finetune_result['output'][:300]}...")
            else:
                print(f"✗ 错误: {finetune_result['error']}")

            test_result["results"]["finetuned_llm"] = finetune_result

        # 方法 2: Agent
        print(f"\n{'-'*50}")
        print("方法 2: LangChain Agent")
        print(f"{'-'*50}")

        agent_result = run_agent_mutation(
            test_case["sql"], test_case["db_type"], test_case["oracle_type"]
        )

        if "error" not in agent_result:
            print(f"✓ 耗时: {agent_result['elapsed_time']:.2f}s")
            print(f"✓ LLM 调用次数: {agent_result['num_llm_calls']}")
            print(f"✓ 推理步骤数: {len(agent_result.get('reasoning_steps', []))}")
            print(f"✓ 工具调用:")
            for step in agent_result.get("reasoning_steps", []):
                print(f"    - {step['tool']}: {step['input']}")
            print(f"✓ 输出:\n{agent_result['output'][:300]}...")
        else:
            print(f"✗ 错误: {agent_result['error']}")

        test_result["results"]["agent"] = agent_result
        results.append(test_result)

    # 汇总对比
    print("\n" + "=" * 100)
    print("对比总结")
    print("=" * 100)

    print(f"\n{'指标':<20} {'微调 LLM':<30} {'Agent':<30}")
    print("-" * 80)

    # 计算平均值
    finetune_times = [
        r["results"].get("finetuned_llm", {}).get("elapsed_time", 0)
        for r in results
        if "error" not in r["results"].get("finetuned_llm", {})
    ]
    agent_times = [
        r["results"].get("agent", {}).get("elapsed_time", 0)
        for r in results
        if "error" not in r["results"].get("agent", {})
    ]

    finetune_calls = [
        r["results"].get("finetuned_llm", {}).get("num_llm_calls", 0)
        for r in results
        if "error" not in r["results"].get("finetuned_llm", {})
    ]
    agent_calls = [
        r["results"].get("agent", {}).get("num_llm_calls", 0)
        for r in results
        if "error" not in r["results"].get("agent", {})
    ]

    if finetune_times and agent_times:
        avg_finetune_time = sum(finetune_times) / len(finetune_times)
        avg_agent_time = sum(agent_times) / len(agent_times)
        avg_finetune_calls = sum(finetune_calls) / len(finetune_calls)
        avg_agent_calls = sum(agent_calls) / len(agent_calls)

        print(
            f"{'平均耗时':<20} {avg_finetune_time:.2f}s{'':<23} {avg_agent_time:.2f}s"
        )
        print(
            f"{'平均 LLM 调用':<20} {avg_finetune_calls:.1f} 次{'':<22} {avg_agent_calls:.1f} 次"
        )

    print(f"{'可以验证语法':<20} {'✗':<30} {'✓':<30}")
    print(f"{'可以推理决策':<20} {'✗':<30} {'✓':<30}")
    print(f"{'可以自我纠错':<20} {'✗':<30} {'✓':<30}")
    print(f"{'可观察性':<20} {'✗ (黑盒)':<30} {'✓ (完全透明)':<30}")
    print(f"{'维护成本':<20} {'高 (需重新训练)':<30} {'低 (改 Prompt)':<30}")

    # 保存结果
    output_file = "Output/agent_vs_finetune_comparison.json"
    os.makedirs("Output", exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n✅ 详细结果已保存到: {output_file}")

    print("\n" + "=" * 100)
    print("💡 结论")
    print("=" * 100)
    print(
        """
1. 微调 LLM 适合场景:
   - 任务格式固定、模式清晰
   - 需要快速响应
   - 不需要验证和推理
   - 有大量高质量训练数据

2. Agent 适合场景:
   - 需要调用外部工具 (数据库、知识库)
   - 需要多步推理和决策
   - 需要验证和错误修复
   - 任务逻辑复杂、需要灵活应对

3. 建议:
   - 简单任务 (如格式转换) → 微调 LLM
   - 复杂任务 (如需要验证的变异) → Agent
   - 混合方案: Agent 做决策,微调 LLM 做执行
"""
    )


if __name__ == "__main__":
    compare_methods()
