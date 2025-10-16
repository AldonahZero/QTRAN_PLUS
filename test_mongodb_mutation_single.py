#!/usr/bin/env python3
"""
单独测试 MongoDB 变异 Prompt 是否生成正确格式
直接调用 MutateLLM 函数,不需要运行完整 pipeline
"""
import os
import sys
import json

# 确保能导入 src 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from MutationLlmModelValidator.MutateLLM import run_muatate_llm_single_sql


def test_mongodb_mutation():
    """测试 MongoDB 变异是否生成正确格式"""

    # 模拟一个 MongoDB JSON 命令(从 TransferLLM 转换后的正确格式)
    test_seed_cmd = '{"op":"insertOne","collection":"kv","document":{"mykey":"hello"}}'

    print("=" * 70)
    print("测试 MongoDB 变异 Prompt - 单命令测试")
    print("=" * 70)
    print(f"\n种子命令: {test_seed_cmd}")
    print(f"目标数据库: mongodb")
    print(f"变异策略: semantic")

    try:
        # 需要创建 OpenAI client
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # 调用变异函数（注意：实际函数签名）
        result = run_muatate_llm_single_sql(
            tool="sqlancer",
            client=client,
            model_id=os.getenv("SEMANTIC_MUTATION_LLM_ID", "gpt-4o-mini"),
            mutate_name="semantic",  # 用于确定策略
            oracle="semantic",  # oracle 类型
            db_type="mongodb",  # 明确指定 mongodb
            sql=test_seed_cmd,
        )

        print("\n" + "=" * 70)
        print("变异结果")
        print("=" * 70)

        # 解析结果（可能是 list, tuple 或 str）
        if isinstance(result, (list, tuple)) and len(result) > 0:
            # 取第一个元素
            result_str = result[0]
        elif isinstance(result, str):
            result_str = result
        else:
            result_str = str(result)

        try:
            result_data = json.loads(result_str)
        except Exception as e:
            print(f"❌ 无法解析为 JSON: {e}")
            print(f"原始返回: {result_str[:200]}...")
            return False

        # 检查是否有 mutations 字段
        if "mutations" not in result_data:
            print(f"❌ 缺少 'mutations' 字段")
            print(
                f"实际返回: {json.dumps(result_data, indent=2, ensure_ascii=False)[:500]}..."
            )
            return False

        mutations = result_data["mutations"]
        print(f"\n✅ 生成了 {len(mutations)} 个变异")

        # 检查每个变异的格式
        valid_count = 0
        invalid_count = 0

        for i, mutation in enumerate(mutations, 1):
            print(f"\n--- 变异 {i} ---")
            cmd = mutation.get("cmd", "")
            print(f"cmd: {cmd[:100]}...")

            # 检查是否是简化伪命令
            if any(
                pattern in cmd.lower()
                for pattern in ["find kv", "count kv", "delete kv", "insert kv"]
            ):
                print(f"  ❌ 简化伪命令")
                invalid_count += 1
                continue

            # 尝试解析为 MongoDB JSON
            try:
                cmd_json = json.loads(cmd)
                if "op" in cmd_json and "collection" in cmd_json:
                    print(f"  ✅ 有效的 MongoDB JSON")
                    print(
                        f"     op={cmd_json.get('op')}, collection={cmd_json.get('collection')}"
                    )
                    valid_count += 1
                else:
                    print(f"  ❌ JSON 缺少 op 或 collection 字段")
                    invalid_count += 1
            except json.JSONDecodeError as e:
                print(f"  ❌ JSON 解析失败: {e}")
                invalid_count += 1

        print("\n" + "=" * 70)
        print(f"质量统计:")
        print(f"  有效: {valid_count}")
        print(f"  无效: {invalid_count}")
        print(f"  质量率: {valid_count/(valid_count+invalid_count)*100:.1f}%")
        print("=" * 70)

        # 判断是否通过
        quality_rate = (
            valid_count / (valid_count + invalid_count)
            if (valid_count + invalid_count) > 0
            else 0
        )
        if quality_rate >= 0.8:  # 至少 80% 质量率
            print("\n🎉 测试通过! 质量率 ≥ 80%")
            return True
        else:
            print(f"\n❌ 测试失败! 质量率 {quality_rate*100:.1f}% < 80%")
            return False

    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 检查环境变量
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ 请设置 OPENAI_API_KEY 环境变量")
        sys.exit(1)

    # 运行测试
    success = test_mongodb_mutation()
    sys.exit(0 if success else 1)
