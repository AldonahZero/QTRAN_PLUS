#!/usr/bin/env python3
"""
测试数据库检测功能
验证 scan_databases_from_input 函数是否正确识别输入文件中的数据库
"""

import sys
import os
import json

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)


def scan_databases_from_input(input_filepath):
    """
    扫描输入文件，提取所有涉及的 a_db 和 b_db 数据库。

    参数：
    - input_filepath: JSONL 输入文件路径

    返回：
    - set: 包含所有需要初始化的数据库名称集合
    """
    databases = set()
    try:
        with open(input_filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "a_db" in data:
                        databases.add(data["a_db"].lower())
                    if "b_db" in data:
                        databases.add(data["b_db"].lower())
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        print(f"Warning: Input file not found: {input_filepath}")

    return databases


def test_demo1():
    """测试 demo1.jsonl 文件"""
    input_file = os.path.join(current_dir, "Input", "demo1.jsonl")

    if not os.path.exists(input_file):
        print(f"❌ 测试文件不存在: {input_file}")
        return False

    print(f"📄 测试文件: {input_file}")
    databases = scan_databases_from_input(input_file)

    print(f"✅ 检测到的数据库: {sorted(databases)}")
    print(f"📊 数据库数量: {len(databases)}")

    # 验证预期的数据库
    expected_dbs = {
        "sqlite",
        "duckdb",
        "monetdb",
        "tidb",
        "mariadb",
        "mysql",
        "postgres",
    }
    if databases == expected_dbs:
        print("✅ 数据库检测完全正确！")
        return True
    else:
        missing = expected_dbs - databases
        extra = databases - expected_dbs
        if missing:
            print(f"⚠️  缺少数据库: {missing}")
        if extra:
            print(f"⚠️  额外数据库: {extra}")
        return False


def test_empty_file():
    """测试空文件处理"""
    print("\n📄 测试空文件处理")

    # 创建临时空文件
    temp_file = os.path.join(current_dir, "temp_empty.jsonl")
    with open(temp_file, "w") as f:
        f.write("")

    databases = scan_databases_from_input(temp_file)
    os.remove(temp_file)

    if len(databases) == 0:
        print("✅ 空文件处理正确（返回空集合）")
        return True
    else:
        print(f"❌ 空文件处理错误，返回: {databases}")
        return False


def test_nonexistent_file():
    """测试不存在的文件处理"""
    print("\n📄 测试不存在的文件处理")
    databases = scan_databases_from_input("/nonexistent/path/file.jsonl")

    if len(databases) == 0:
        print("✅ 不存在文件处理正确（返回空集合）")
        return True
    else:
        print(f"❌ 不存在文件处理错误，返回: {databases}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 数据库检测功能测试")
    print("=" * 60)

    results = []

    results.append(("demo1.jsonl 检测", test_demo1()))
    results.append(("空文件处理", test_empty_file()))
    results.append(("不存在文件处理", test_nonexistent_file()))

    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")

    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("🎉 所有测试通过！")
        sys.exit(0)
    else:
        print("⚠️  部分测试失败")
        sys.exit(1)
