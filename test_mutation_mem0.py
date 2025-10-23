#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Mem0 变异阶段集成测试
测试 MutationMemoryManager 的各项功能
"""

import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def test_mutation_memory_manager():
    """测试 MutationMemoryManager 基本功能"""
    print("=" * 60)
    print("测试 1: MutationMemoryManager 初始化")
    print("=" * 60)
    
    try:
        from src.MutationLlmModelValidator.mutation_mem0_adapter import MutationMemoryManager
        
        manager = MutationMemoryManager(user_id="test_mutation_user")
        print("✅ MutationMemoryManager 初始化成功")
        
        # 测试会话管理
        print("\n" + "=" * 60)
        print("测试 2: 会话管理")
        print("=" * 60)
        
        manager.start_session(
            db_type="mongodb",
            oracle_type="tlp",
            sql_type="SELECT"
        )
        print("✅ 会话启动成功")
        
        # 测试记录成功的变异
        print("\n" + "=" * 60)
        print("测试 3: 记录成功的变异模式")
        print("=" * 60)
        
        original_sql = "db.myCollection.findOne({ _id: 'counter' });"
        mutated_sqls = [
            "db.myCollection.findOne({ _id: 'counter', type: { $exists: true } });",
            "db.myCollection.findOne({ _id: 'counter', type: { $not: { $exists: true } } });",
        ]
        
        manager.record_successful_mutation(
            original_sql=original_sql,
            mutated_sqls=mutated_sqls,
            oracle_type="tlp",
            db_type="mongodb",
            mutation_strategy="tlp_partition",
            execution_time=1.5
        )
        print(f"✅ 记录了 {len(mutated_sqls)} 个变异")
        
        # 测试记录 Bug 模式
        print("\n" + "=" * 60)
        print("测试 4: 记录 Bug 模式")
        print("=" * 60)
        
        manager.record_bug_pattern(
            original_sql=original_sql,
            mutation_sql=mutated_sqls[0],
            bug_type="tlp_violation",
            oracle_type="tlp",
            db_type="mongodb",
            oracle_details={"expected": 1, "actual": 2}
        )
        print("✅ Bug 模式记录成功")
        
        # 测试获取相关模式
        print("\n" + "=" * 60)
        print("测试 5: 检索相关变异模式")
        print("=" * 60)
        
        similar_sql = "db.myCollection.findOne({ _id: 'mykey' });"
        patterns = manager.get_relevant_patterns(
            query_sql=similar_sql,
            oracle_type="tlp",
            db_type="mongodb",
            limit=3
        )
        print(f"✅ 找到 {len(patterns)} 个相关模式")
        
        # 测试增强 Prompt
        print("\n" + "=" * 60)
        print("测试 6: 增强变异 Prompt")
        print("=" * 60)
        
        base_prompt = "You are a SQL mutation expert. Generate TLP mutations."
        enhanced_prompt = manager.build_enhanced_prompt(
            base_prompt=base_prompt,
            query_sql=similar_sql,
            oracle_type="tlp",
            db_type="mongodb"
        )
        
        if len(enhanced_prompt) > len(base_prompt):
            print("✅ Prompt 成功增强")
            print(f"   原始长度: {len(base_prompt)}")
            print(f"   增强后长度: {len(enhanced_prompt)}")
        else:
            print("⚠️ Prompt 未增强（可能没有历史记忆）")
        
        # 结束会话
        manager.end_session(success=True, summary="Test session completed")
        print("\n✅ 会话结束")
        
        # 打印性能指标
        print("\n" + "=" * 60)
        print("测试 7: 性能指标")
        print("=" * 60)
        print(manager.get_metrics_report())
        
        return True
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("   提示: 请确保已安装 mem0ai 和 qdrant-client")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fallback_manager():
    """测试降级模式的记忆管理器"""
    print("\n" + "=" * 60)
    print("测试 8: FallbackMutationMemoryManager")
    print("=" * 60)
    
    try:
        from src.MutationLlmModelValidator.mutation_mem0_adapter import FallbackMutationMemoryManager
        
        manager = FallbackMutationMemoryManager(user_id="test_fallback")
        print("✅ FallbackMutationMemoryManager 初始化成功")
        
        manager.start_session(db_type="mongodb", oracle_type="tlp")
        manager.record_successful_mutation(
            original_sql="test",
            mutated_sqls=["mutation1", "mutation2"],
            oracle_type="tlp",
            db_type="mongodb"
        )
        manager.record_bug_pattern(
            original_sql="test",
            mutation_sql="bug_mutation",
            bug_type="test_bug",
            oracle_type="tlp",
            db_type="mongodb"
        )
        manager.end_session(success=True)
        
        print("✅ 降级管理器所有操作正常")
        print(manager.get_metrics_report())
        
        return True
        
    except Exception as e:
        print(f"❌ 降级管理器测试失败: {e}")
        return False


def test_integration_check():
    """检查集成是否正确"""
    print("\n" + "=" * 60)
    print("测试 9: 集成检查")
    print("=" * 60)
    
    checks = []
    
    # 检查文件是否存在
    files_to_check = [
        "src/MutationLlmModelValidator/mutation_mem0_adapter.py",
        "src/MutationLlmModelValidator/MutateLLM.py",
        "src/TransferLLM/translate_sqlancer.py",
    ]
    
    for filepath in files_to_check:
        if os.path.exists(filepath):
            print(f"✅ {filepath} 存在")
            checks.append(True)
        else:
            print(f"❌ {filepath} 不存在")
            checks.append(False)
    
    # 检查关键函数是否有 mem0_manager 参数
    print("\n检查函数签名...")
    try:
        from src.MutationLlmModelValidator.MutateLLM import run_muatate_llm_single_sql
        import inspect
        
        sig = inspect.signature(run_muatate_llm_single_sql)
        if 'mem0_manager' in sig.parameters:
            print("✅ run_muatate_llm_single_sql 包含 mem0_manager 参数")
            checks.append(True)
        else:
            print("❌ run_muatate_llm_single_sql 缺少 mem0_manager 参数")
            checks.append(False)
    except Exception as e:
        print(f"⚠️ 无法检查函数签名: {e}")
        checks.append(False)
    
    # 检查环境变量
    print("\n检查环境变量...")
    if os.environ.get("QTRAN_USE_MEM0"):
        print(f"✅ QTRAN_USE_MEM0 = {os.environ.get('QTRAN_USE_MEM0')}")
    else:
        print("⚠️ QTRAN_USE_MEM0 未设置（默认为 false）")
    
    # 检查 Qdrant 连接
    print("\n检查 Qdrant 服务...")
    try:
        import requests
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = os.getenv("QDRANT_PORT", "6333")
        response = requests.get(f"http://{qdrant_host}:{qdrant_port}/health", timeout=2)
        if response.status_code == 200:
            print(f"✅ Qdrant 服务运行正常 ({qdrant_host}:{qdrant_port})")
            checks.append(True)
        else:
            print(f"⚠️ Qdrant 服务响应异常: {response.status_code}")
            checks.append(False)
    except Exception as e:
        print(f"⚠️ 无法连接到 Qdrant: {e}")
        print("   提示: 请运行 ./docker_start_qdrant.sh 启动 Qdrant")
        checks.append(False)
    
    return all(checks)


def main():
    """主测试函数"""
    print("\n" + "🧬" * 30)
    print("Mem0 变异阶段集成测试")
    print("🧬" * 30 + "\n")
    
    results = []
    
    # 运行所有测试
    results.append(("集成检查", test_integration_check()))
    results.append(("降级管理器", test_fallback_manager()))
    results.append(("完整功能", test_mutation_memory_manager()))
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！变异阶段 Mem0 集成完成！")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())

