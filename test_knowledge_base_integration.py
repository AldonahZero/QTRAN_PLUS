#!/usr/bin/env python3
"""
测试知识库到 Mem0 的集成

运行方法:
    # 完整测试（需要先导入知识库）
    python test_knowledge_base_integration.py
    
    # 快速测试（导入少量数据）
    python test_knowledge_base_integration.py --quick
"""

import sys
import argparse
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from src.TransferLLM.mem0_adapter import TransferMemoryManager, FallbackMemoryManager
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False


def test_knowledge_base_query():
    """测试知识库查询功能"""
    print("\n" + "=" * 60)
    print("测试 1: 知识库查询")
    print("=" * 60)
    
    try:
        manager = TransferMemoryManager(user_id="qtran_test")
        
        # 测试 MongoDB 知识查询
        print("\n📖 测试查询 MongoDB 知识...")
        results = manager.get_knowledge_base_info(
            query="$and operator",
            database="mongodb",
            limit=3
        )
        
        print(f"找到 {len(results)} 条相关知识:")
        for i, result in enumerate(results, 1):
            memory_text = result.get('memory', '')[:200]
            metadata = result.get('metadata', {})
            print(f"\n  {i}. {memory_text}...")
            print(f"     类型: {metadata.get('type', 'unknown')}")
            print(f"     特征: {metadata.get('feature_name', 'N/A')}")
        
        if len(results) > 0:
            print("\n✅ MongoDB 知识查询成功")
        else:
            print("\n⚠️ 未找到 MongoDB 知识（可能尚未导入）")
        
        # 测试 MySQL 知识查询
        print("\n📖 测试查询 MySQL 知识...")
        results = manager.get_knowledge_base_info(
            query="INTEGER data type",
            database="mysql",
            limit=3
        )
        
        print(f"找到 {len(results)} 条相关知识:")
        for i, result in enumerate(results, 1):
            memory_text = result.get('memory', '')[:200]
            metadata = result.get('metadata', {})
            print(f"\n  {i}. {memory_text}...")
            print(f"     类型: {metadata.get('type', 'unknown')}")
        
        if len(results) > 0:
            print("\n✅ MySQL 知识查询成功")
        else:
            print("\n⚠️ 未找到 MySQL 知识（可能尚未导入）")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prompt_enhancement():
    """测试 Prompt 增强功能"""
    print("\n" + "=" * 60)
    print("测试 2: Prompt 增强（包含知识库）")
    print("=" * 60)
    
    try:
        manager = TransferMemoryManager(user_id="qtran_test")
        manager.start_session(origin_db="redis", target_db="mongodb", molt="test")
        
        base_prompt = """
Translate the following SQL from {origin_db} to {target_db}:

{sql}

{feature_knowledge}

{examples}

Please provide the translated SQL.
"""
        
        test_sql = "SET mykey 'hello world'"
        
        # 测试增强 prompt
        print("\n📝 原始 Prompt 长度:", len(base_prompt))
        
        enhanced_prompt = manager.build_enhanced_prompt(
            base_prompt=base_prompt,
            query_sql=test_sql,
            origin_db="redis",
            target_db="mongodb",
            include_knowledge_base=True
        )
        
        print(f"📝 增强后 Prompt 长度: {len(enhanced_prompt)}")
        print(f"📊 增加了 {len(enhanced_prompt) - len(base_prompt)} 个字符")
        
        # 检查是否包含知识库信息
        has_kb_info = "Knowledge Base" in enhanced_prompt
        has_memory_info = "Relevant Historical Knowledge" in enhanced_prompt or len(enhanced_prompt) > len(base_prompt)
        
        print(f"\n📖 包含知识库信息: {'是' if has_kb_info else '否'}")
        print(f"📚 包含历史记忆: {'是' if has_memory_info else '否'}")
        
        if len(enhanced_prompt) > len(base_prompt):
            print("\n✅ Prompt 增强成功")
            print("\n增强部分预览:")
            # 显示增强部分的前 500 字符
            added_content = enhanced_prompt[len(base_prompt):]
            print(added_content[:500])
            if len(added_content) > 500:
                print("...")
        else:
            print("\n⚠️ Prompt 未增强（可能是知识库为空）")
        
        manager.end_session(success=True)
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_keyword_extraction():
    """测试关键词提取功能"""
    print("\n" + "=" * 60)
    print("测试 3: SQL 关键词提取")
    print("=" * 60)
    
    try:
        manager = TransferMemoryManager(user_id="qtran_test")
        
        test_cases = [
            "SELECT COUNT(*) FROM users WHERE age > 18",
            "CREATE TABLE students (id INTEGER PRIMARY KEY, name VARCHAR(100))",
            "INSERT INTO products VALUES (1, 'Apple', 1.99)",
            "UPDATE orders SET status = 'completed' WHERE id = 123",
        ]
        
        for i, sql in enumerate(test_cases, 1):
            print(f"\n测试案例 {i}:")
            print(f"SQL: {sql}")
            
            keywords = manager._extract_keywords_from_sql(sql)
            print(f"提取的关键词: {keywords}")
        
        print("\n✅ 关键词提取测试完成")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_quick_import():
    """快速导入测试数据"""
    print("\n" + "=" * 60)
    print("快速测试: 导入少量测试数据")
    print("=" * 60)
    
    try:
        manager = TransferMemoryManager(user_id="qtran_test")
        
        # 添加一些测试知识
        test_knowledge = [
            {
                "memory": "MongoDB Operator: $eq\nEquality operator for matching exact values\nUsed with methods: find, update",
                "user_id": "qtran_kb_mongodb",
                "metadata": {
                    "database": "mongodb",
                    "type": "operator",
                    "feature_name": "$eq",
                    "source": "test"
                }
            },
            {
                "memory": "MySQL Function: COUNT(*)\nReturns the number of rows in a result set\nExample SQL: SELECT COUNT(*) FROM table;",
                "user_id": "qtran_kb_mysql",
                "metadata": {
                    "database": "mysql",
                    "type": "function",
                    "feature_name": "COUNT",
                    "source": "test"
                }
            },
            {
                "memory": "Redis Command: SET\nSet key to hold the string value\nExample: SET mykey 'Hello'",
                "user_id": "qtran_kb_redis",
                "metadata": {
                    "database": "redis",
                    "type": "command",
                    "feature_name": "SET",
                    "source": "test"
                }
            }
        ]
        
        print("\n📥 导入测试知识...")
        for item in test_knowledge:
            manager.memory.add(
                item["memory"],
                user_id=item["user_id"],
                metadata=item["metadata"]
            )
        
        print(f"✅ 已导入 {len(test_knowledge)} 条测试知识")
        
        # 验证导入
        print("\n🔍 验证导入...")
        results = manager.get_knowledge_base_info("$eq", "mongodb", limit=1)
        if results:
            print("✅ MongoDB 知识验证成功")
        
        results = manager.get_knowledge_base_info("COUNT", "mysql", limit=1)
        if results:
            print("✅ MySQL 知识验证成功")
        
        results = manager.get_knowledge_base_info("SET", "redis", limit=1)
        if results:
            print("✅ Redis 知识验证成功")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 快速导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="测试知识库集成")
    parser.add_argument("--quick", action="store_true", help="快速测试（导入少量测试数据）")
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("  QTRAN 知识库集成测试")
    print("=" * 60)
    
    if not MEM0_AVAILABLE:
        print("\n❌ Mem0 未安装，请先运行: pip install mem0ai")
        return 1
    
    results = []
    
    # 快速模式：导入测试数据
    if args.quick:
        print("\n🚀 运行快速测试模式...")
        results.append(("快速导入", test_quick_import()))
    
    # 测试知识库查询
    results.append(("知识库查询", test_knowledge_base_query()))
    
    # 测试 Prompt 增强
    results.append(("Prompt 增强", test_prompt_enhancement()))
    
    # 测试关键词提取
    results.append(("关键词提取", test_keyword_extraction()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{test_name}: {status}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"总计: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    if args.quick:
        print("\n💡 提示: 这是快速测试模式")
        print("   要测试完整功能，请先导入知识库:")
        print("   python tools/knowledge_base_importer.py --nosql mongodb")
        print("   python tools/knowledge_base_importer.py --sql mysql")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

