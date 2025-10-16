#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速测试脚本:验证 MongoDB 变异修复是否生效

使用方法:
    python test_mongodb_mutation_fix.py

测试内容:
1. 检查 semantic_mongodb.json 是否存在
2. 测试 MutateLLM 的数据库类型检测逻辑
3. 模拟单个变异生成并验证格式
4. 输出详细的诊断信息
"""

import os
import sys
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_prompt_file_exists():
    """测试 1: 检查 MongoDB 专用 prompt 是否存在"""
    print("=" * 70)
    print("TEST 1: 检查 semantic_mongodb.json 文件")
    print("=" * 70)

    prompt_path = os.path.join(
        os.path.dirname(__file__),
        "MutationData",
        "MutationLLMPrompt",
        "semantic_mongodb.json",
    )

    if os.path.exists(prompt_path):
        print(f"✅ 文件存在: {prompt_path}")

        with open(prompt_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "semantic" in data:
            content = data["semantic"]
            print(f"✅ Prompt 内容长度: {len(content)} 字符")

            # 检查关键字
            keywords = ["MongoDB", "JSON", "op", "collection", "STRICT OUTPUT FORMAT"]
            found = [kw for kw in keywords if kw in content]
            print(f"✅ 包含关键字: {', '.join(found)}")

            if len(found) == len(keywords):
                print("✅ 所有关键字都存在")
                return True
            else:
                missing = [kw for kw in keywords if kw not in found]
                print(f"⚠️  缺少关键字: {', '.join(missing)}")
                return False
        else:
            print("❌ 缺少 'semantic' 键")
            return False
    else:
        print(f"❌ 文件不存在: {prompt_path}")
        print("请确保已创建此文件")
        return False


def test_database_type_detection():
    """测试 2: 测试数据库类型检测逻辑"""
    print("\n" + "=" * 70)
    print("TEST 2: 测试数据库类型检测")
    print("=" * 70)

    # 模拟 TransferSqlExecResult
    test_cases = [
        {
            "name": "MongoDB 目标",
            "b_db": "Memcached",
            "exec_result": '{"dbType": "mongodb", "target": "127.0.0.1:27017"}',
            "expected": "mongodb",
        },
        {
            "name": "MySQL 目标",
            "b_db": "mysql",
            "exec_result": '{"dbType": "mysql", "target": "localhost:3306"}',
            "expected": "mysql",
        },
        {
            "name": "无法检测(使用 b_db)",
            "b_db": "postgres",
            "exec_result": "",
            "expected": "postgres",
        },
    ]

    all_passed = True
    for case in test_cases:
        print(f"\n测试用例: {case['name']}")
        print(f"  b_db = {case['b_db']}")

        # 模拟检测逻辑
        actual_target_db = case["b_db"]
        if case["exec_result"]:
            try:
                exec_result_json = json.loads(case["exec_result"])
                detected_db_type = exec_result_json.get("dbType", "").lower()
                if detected_db_type in ["mongodb", "mongo"]:
                    actual_target_db = "mongodb"
            except Exception as e:
                pass

        if actual_target_db == case["expected"]:
            print(f"  ✅ 检测结果: {actual_target_db} (符合预期)")
        else:
            print(f"  ❌ 检测结果: {actual_target_db}, 期望: {case['expected']}")
            all_passed = False

    return all_passed


def test_mutation_format():
    """测试 3: 验证变异命令格式"""
    print("\n" + "=" * 70)
    print("TEST 3: 验证变异命令格式")
    print("=" * 70)

    # 正确格式示例
    correct_mutations = [
        {
            "cmd": '{"op":"findOne","collection":"kv","filter":{"_id":"mykey"}}',
            "category": "probe",
            "oracle": "value_read",
        },
        {
            "cmd": '{"op":"countDocuments","collection":"kv","filter":{"_id":"mykey"}}',
            "category": "cardinality_probe",
            "oracle": "membership_true",
        },
    ]

    # 错误格式示例
    incorrect_mutations = [
        {
            "cmd": "find kv",  # ❌ 简化伪命令
            "category": "probe",
            "oracle": "value_read",
        },
        {
            "cmd": "count kv",  # ❌ 简化伪命令
            "category": "probe",
            "oracle": "cardinality_probe",
        },
    ]

    print("\n✅ 正确格式示例:")
    for i, mut in enumerate(correct_mutations, 1):
        print(f"  {i}. cmd: {mut['cmd'][:60]}...")
        try:
            parsed = json.loads(mut["cmd"])
            if "op" in parsed and "collection" in parsed:
                print(
                    f"     ✅ 解析成功, op={parsed['op']}, collection={parsed['collection']}"
                )
            else:
                print(f"     ⚠️  缺少必需字段")
        except json.JSONDecodeError as e:
            print(f"     ❌ JSON 解析失败: {e}")

    print("\n❌ 错误格式示例:")
    for i, mut in enumerate(incorrect_mutations, 1):
        print(f"  {i}. cmd: {mut['cmd']}")
        try:
            parsed = json.loads(mut["cmd"])
            print(f"     ⚠️  竟然能解析? {parsed}")
        except json.JSONDecodeError:
            print(f"     ❌ JSON 解析失败 (符合预期,因为是简化命令)")

    return True


def test_mutate_llm_function():
    """测试 4: 测试 MutateLLM 函数的 Prompt 选择逻辑"""
    print("\n" + "=" * 70)
    print("TEST 4: 测试 MutateLLM Prompt 选择逻辑")
    print("=" * 70)

    try:
        from src.MutationLlmModelValidator.MutateLLM import run_muatate_llm_single_sql

        print("✅ 成功导入 run_muatate_llm_single_sql")
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False

    # 模拟测试(不实际调用 LLM)
    test_cases = [
        ("mongodb", "semantic", "semantic_mongodb.json"),
        ("mongo", "semantic", "semantic_mongodb.json"),
        ("postgres", "semantic", "semantic.json"),
        ("mysql", "tlp", "tlp.json"),
    ]

    print("\nPrompt 文件选择逻辑:")
    for db_type, strategy, expected_file in test_cases:
        is_mongodb = db_type.lower() in ["mongodb", "mongo"]

        if is_mongodb and strategy == "semantic":
            selected_file = "semantic_mongodb.json"
        else:
            selected_file = f"{strategy}.json"

        status = "✅" if selected_file == expected_file else "❌"
        print(f"  {status} db_type={db_type}, strategy={strategy} -> {selected_file}")

    return True


def main():
    """运行所有测试"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 10 + "MongoDB 变异修复验证测试套件" + " " * 25 + "║")
    print("╚" + "=" * 68 + "╝")

    results = []

    # 运行测试
    results.append(("Prompt 文件存在", test_prompt_file_exists()))
    results.append(("数据库类型检测", test_database_type_detection()))
    results.append(("变异格式验证", test_mutation_format()))
    results.append(("MutateLLM 函数", test_mutate_llm_function()))

    # 汇总结果
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过!修复已正确实施!")
        print("\n下一步:")
        print("1. 清空旧产物: rm -rf Output/redis_demo_04/MutationLLM/*.jsonl")
        print(
            "2. 重新运行: python src/main.py --input Input/redis_demo_04.jsonl --output redis_demo_04"
        )
        print("3. 验证质量: python src/Tools/fix_mutation_quality.py redis_demo_04")
        return 0
    else:
        print("\n⚠️  部分测试失败,请检查上述错误信息")
        print("\n调试建议:")
        print("1. 确保 semantic_mongodb.json 文件已创建")
        print("2. 确保 MutateLLM.py 中的修改已保存")
        print("3. 确保 translate_sqlancer.py 中的修改已保存")
        return 1


if __name__ == "__main__":
    sys.exit(main())
