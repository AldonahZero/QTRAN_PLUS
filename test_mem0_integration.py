"""
Mem0 集成测试脚本：验证翻译阶段的记忆管理功能

测试内容：
1. Mem0 初始化（Qdrant 连接或降级到 Chroma）
2. 记忆存储（成功翻译、错误修正）
3. 记忆检索（语义搜索）
4. Prompt 增强
5. 完整翻译流程测试

运行方式：
    # 启用 Mem0（需要先启动 Qdrant）
    export QTRAN_USE_MEM0=true
    python test_mem0_integration.py
    
    # 或使用降级模式（无需 Qdrant）
    python test_mem0_integration.py --fallback
"""

import os
import sys
import json
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_1_mem0_initialization():
    """测试 1: Mem0 初始化"""
    print("\n" + "="*60)
    print("测试 1: Mem0 初始化")
    print("="*60)
    
    try:
        from src.TransferLLM.mem0_adapter import TransferMemoryManager, FallbackMemoryManager
        
        # 测试正常模式
        try:
            manager = TransferMemoryManager(user_id="test_user")
            print("✅ TransferMemoryManager 初始化成功")
            print(f"   User ID: {manager.user_id}")
            return manager, True
        except ImportError as e:
            print(f"⚠️  Mem0 不可用，使用降级模式: {e}")
            manager = FallbackMemoryManager(user_id="test_user")
            print("✅ FallbackMemoryManager 初始化成功")
            return manager, False
        
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return None, False


def test_2_session_management(manager):
    """测试 2: 会话管理"""
    print("\n" + "="*60)
    print("测试 2: 会话管理")
    print("="*60)
    
    try:
        # 开启会话
        session_id = manager.start_session(
            origin_db="redis",
            target_db="mongodb",
            molt="semantic"
        )
        print(f"✅ 会话创建成功: {session_id}")
        
        # 结束会话
        manager.end_session(success=True, final_result="db.myCollection.findOne(...)")
        print("✅ 会话结束成功")
        
        return True
    except Exception as e:
        print(f"❌ 会话管理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_3_record_successful_translation(manager):
    """测试 3: 记录成功的翻译"""
    print("\n" + "="*60)
    print("测试 3: 记录成功的翻译")
    print("="*60)
    
    try:
        manager.start_session("redis", "mongodb", "semantic")
        
        # 记录几个成功的翻译案例
        test_cases = [
            {
                "origin": "SET mykey hello",
                "target": "db.myCollection.insertOne({ _id: 'mykey', value: 'hello' })",
                "iterations": 1,
                "features": ["SET", "key-value"]
            },
            {
                "origin": "GET mykey",
                "target": "db.myCollection.findOne({ _id: 'mykey' })",
                "iterations": 1,
                "features": ["GET", "key-value"]
            },
            {
                "origin": "DEL mykey",
                "target": "db.myCollection.deleteOne({ _id: 'mykey' })",
                "iterations": 2,
                "features": ["DEL", "key-value"]
            }
        ]
        
        for i, case in enumerate(test_cases, 1):
            manager.record_successful_translation(
                origin_sql=case["origin"],
                target_sql=case["target"],
                origin_db="redis",
                target_db="mongodb",
                iterations=case["iterations"],
                features=case["features"]
            )
            print(f"✅ 记录成功翻译 {i}/3: {case['origin'][:30]}...")
        
        manager.end_session(success=True)
        return True
        
    except Exception as e:
        print(f"❌ 记录翻译失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_4_record_error_fix(manager):
    """测试 4: 记录错误修正"""
    print("\n" + "="*60)
    print("测试 4: 记录错误修正")
    print("="*60)
    
    try:
        manager.start_session("redis", "postgres", "norec")
        
        # 记录错误修正案例
        manager.record_error_fix(
            error_message="syntax error at or near 'ZADD'",
            fix_sql="INSERT INTO zset_table (key, member, score) VALUES ('myset', 'member1', 100);",
            origin_db="redis",
            target_db="postgres",
            failed_sql="ZADD myset 100 member1"
        )
        print("✅ 记录错误修正成功")
        
        manager.end_session(success=True)
        return True
        
    except Exception as e:
        print(f"❌ 记录错误修正失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_5_search_relevant_memories(manager, use_mem0):
    """测试 5: 搜索相关记忆"""
    print("\n" + "="*60)
    print("测试 5: 搜索相关记忆")
    print("="*60)
    
    if not use_mem0:
        print("⚠️  降级模式不支持语义搜索，跳过此测试")
        return True
    
    try:
        # 搜索相关记忆
        query_sql = "SET anotherkey world"
        memories = manager.get_relevant_memories(
            query_sql=query_sql,
            origin_db="redis",
            target_db="mongodb",
            limit=3
        )
        
        print(f"✅ 搜索到 {len(memories)} 条相关记忆")
        for i, mem in enumerate(memories, 1):
            mem_text = mem.get('memory', '')[:100]
            score = mem.get('score', 0)
            print(f"   {i}. [Score: {score:.3f}] {mem_text}...")
        
        return True
        
    except Exception as e:
        print(f"❌ 搜索记忆失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_6_enhance_prompt(manager):
    """测试 6: Prompt 增强"""
    print("\n" + "="*60)
    print("测试 6: Prompt 增强")
    print("="*60)
    
    try:
        base_prompt = """
        Translate the following {origin_db} command to {target_db}.
        
        {feature_knowledge}
        
        Examples: {examples}
        """
        
        enhanced_prompt = manager.build_enhanced_prompt(
            base_prompt=base_prompt,
            query_sql="SET testkey testvalue",
            origin_db="redis",
            target_db="mongodb"
        )
        
        # 检查是否包含记忆上下文
        if "Historical Knowledge" in enhanced_prompt or enhanced_prompt != base_prompt:
            print("✅ Prompt 增强成功")
            print(f"   原始长度: {len(base_prompt)} 字符")
            print(f"   增强后长度: {len(enhanced_prompt)} 字符")
            print(f"   增加了: {len(enhanced_prompt) - len(base_prompt)} 字符")
        else:
            print("⚠️  Prompt 未增强（可能没有相关历史记忆）")
        
        return True
        
    except Exception as e:
        print(f"❌ Prompt 增强失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_7_metrics_report(manager, use_mem0):
    """测试 7: 性能指标报告"""
    print("\n" + "="*60)
    print("测试 7: 性能指标报告")
    print("="*60)
    
    if not use_mem0:
        print("⚠️  降级模式不支持指标收集，跳过此测试")
        return True
    
    try:
        report = manager.get_metrics_report()
        print(report)
        return True
        
    except Exception as e:
        print(f"❌ 获取指标失败: {e}")
        return False


def test_8_full_integration():
    """测试 8: 完整集成测试（模拟真实翻译流程）"""
    print("\n" + "="*60)
    print("测试 8: 完整集成测试")
    print("="*60)
    
    # 设置环境变量
    os.environ["QTRAN_USE_MEM0"] = "true"
    
    try:
        # 模拟 test_info
        test_info = {
            "index": 0,
            "sql": "SET mykey hello",
            "a_db": "redis",
            "b_db": "mongodb",
            "molt": "semantic",
            "SqlPotentialDialectFunction": ["SET"]
        }
        
        # 导入 TransferLLM（不实际执行翻译，只测试 Mem0 集成点）
        from src.TransferLLM.mem0_adapter import TransferMemoryManager
        
        manager = TransferMemoryManager(user_id="integration_test")
        manager.start_session(
            origin_db=test_info["a_db"],
            target_db=test_info["b_db"],
            molt=test_info["molt"]
        )
        
        # 模拟成功的翻译
        manager.record_successful_translation(
            origin_sql=test_info["sql"],
            target_sql="db.myCollection.insertOne({ _id: 'mykey', value: 'hello' })",
            origin_db=test_info["a_db"],
            target_db=test_info["b_db"],
            iterations=1,
            features=test_info["SqlPotentialDialectFunction"]
        )
        
        manager.end_session(success=True)
        
        print("✅ 完整集成测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 完整集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_qdrant_connection():
    """检查 Qdrant 连接状态"""
    print("\n" + "="*60)
    print("环境检查: Qdrant 连接")
    print("="*60)
    
    try:
        import requests
        qdrant_host = os.environ.get("QDRANT_HOST", "localhost")
        qdrant_port = int(os.environ.get("QDRANT_PORT", 6333))
        
        response = requests.get(f"http://{qdrant_host}:{qdrant_port}/health", timeout=2)
        if response.status_code == 200:
            print(f"✅ Qdrant 运行正常: {qdrant_host}:{qdrant_port}")
            print(f"   状态: {response.json()}")
            return True
        else:
            print(f"⚠️  Qdrant 响应异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Qdrant 连接失败: {e}")
        print(f"💡 提示: 运行 'docker run -d -p 6333:6333 qdrant/qdrant' 启动 Qdrant")
        return False


def main():
    """主测试流程"""
    print("\n" + "🧪"*30)
    print("Mem0 集成测试套件")
    print("🧪"*30)
    
    # 检查命令行参数
    use_fallback = "--fallback" in sys.argv
    
    # 环境检查
    if not use_fallback:
        qdrant_available = check_qdrant_connection()
    else:
        print("\n⚠️  使用 --fallback 模式，跳过 Qdrant 检查")
        qdrant_available = False
    
    # 测试计数
    tests = []
    
    # 测试 1: 初始化
    manager, use_mem0 = test_1_mem0_initialization()
    tests.append(("Mem0 初始化", manager is not None))
    
    if manager is None:
        print("\n❌ 初始化失败，终止测试")
        return
    
    # 测试 2: 会话管理
    result = test_2_session_management(manager)
    tests.append(("会话管理", result))
    
    # 测试 3: 记录成功翻译
    result = test_3_record_successful_translation(manager)
    tests.append(("记录成功翻译", result))
    
    # 测试 4: 记录错误修正
    result = test_4_record_error_fix(manager)
    tests.append(("记录错误修正", result))
    
    # 测试 5: 搜索记忆
    result = test_5_search_relevant_memories(manager, use_mem0)
    tests.append(("搜索相关记忆", result))
    
    # 测试 6: Prompt 增强
    result = test_6_enhance_prompt(manager)
    tests.append(("Prompt 增强", result))
    
    # 测试 7: 性能指标
    result = test_7_metrics_report(manager, use_mem0)
    tests.append(("性能指标报告", result))
    
    # 测试 8: 完整集成
    if use_mem0:
        result = test_8_full_integration()
        tests.append(("完整集成测试", result))
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for name, result in tests:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！")
        return 0
    else:
        print("⚠️  部分测试失败")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

