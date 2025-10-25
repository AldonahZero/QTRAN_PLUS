#!/usr/bin/env python3
"""
MVP 反向反馈机制 - 测试脚本

测试 Recommendation 的完整工作流：
1. 生成 Recommendation
2. 获取 Recommendation
3. 增强 Prompt
4. 验证反馈机制
"""

import os
import sys

# 启用 Mem0
os.environ["QTRAN_USE_MEM0"] = "true"

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.TransferLLM.mem0_adapter import TransferMemoryManager


def test_basic_recommendation():
    """测试基础的 Recommendation 功能"""
    print("\n" + "="*70)
    print("🧪 测试 1: 基础 Recommendation 功能")
    print("="*70)
    
    # 初始化
    manager = TransferMemoryManager(user_id="qtran_test_recommendation")
    manager.start_session("sqlite", "mongodb", "tlp")
    
    # 添加 Recommendation
    print("\n📝 添加 Recommendation...")
    manager.add_recommendation(
        target_agent="translation",
        priority=9,
        action="prioritize_features",
        features=["HEX", "MIN", "aggregate"],
        reason="tlp_violation: TLP_violation",
        origin_db="sqlite",
        target_db="mongodb"
    )
    
    # 获取 Recommendation
    print("\n🔍 获取 Recommendation...")
    recommendations = manager.get_recommendations(
        origin_db="sqlite",
        target_db="mongodb",
        limit=3
    )
    
    print(f"✅ 找到 {len(recommendations)} 条建议:")
    for i, rec in enumerate(recommendations, 1):
        print(f"   {i}. {rec['action']}: {rec['features']} (优先级: {rec['priority']})")
        print(f"      原因: {rec['reason']}")
    
    manager.end_session(success=True)
    
    assert len(recommendations) > 0, "❌ 应该至少有 1 条建议"
    print("\n✅ 测试 1 通过！")


def test_prompt_enhancement():
    """测试 Prompt 增强功能"""
    print("\n" + "="*70)
    print("🧪 测试 2: Prompt 增强功能")
    print("="*70)
    
    # 初始化
    manager = TransferMemoryManager(user_id="qtran_test_prompt")
    manager.start_session("sqlite", "mongodb", "tlp")
    
    # 添加多个不同优先级的 Recommendation
    print("\n📝 添加多个 Recommendation...")
    
    manager.add_recommendation(
        target_agent="translation",
        priority=9,
        action="prioritize_features",
        features=["HEX", "MIN"],
        reason="High coverage gain",
        origin_db="sqlite",
        target_db="mongodb"
    )
    
    manager.add_recommendation(
        target_agent="translation",
        priority=8,
        action="prioritize_features",
        features=["COLLATE", "NOCASE"],
        reason="TLP violation detected",
        origin_db="sqlite",
        target_db="mongodb"
    )
    
    manager.add_recommendation(
        target_agent="translation",
        priority=6,  # 低优先级，不应该被包含
        action="avoid_pattern",
        features=["UNION", "ALL"],
        reason="Frequent failures",
        origin_db="sqlite",
        target_db="mongodb"
    )
    
    # 构建增强 Prompt
    print("\n🔨 构建增强 Prompt...")
    base_prompt = "Translate the following SQL from SQLite to MongoDB."
    query_sql = "SELECT HEX(MIN(a)) FROM t1;"
    
    enhanced_prompt = manager.build_enhanced_prompt(
        base_prompt=base_prompt,
        query_sql=query_sql,
        origin_db="sqlite",
        target_db="mongodb",
        include_knowledge_base=False  # 简化测试
    )
    
    print("\n📄 增强后的 Prompt:")
    print("-" * 70)
    print(enhanced_prompt)
    print("-" * 70)
    
    # 验证
    assert "HIGH PRIORITY RECOMMENDATIONS" in enhanced_prompt, "❌ Prompt 应包含 Recommendation"
    assert "HEX" in enhanced_prompt, "❌ Prompt 应包含 HEX 特性"
    assert "Priority: 9" in enhanced_prompt or "Priority: 8" in enhanced_prompt, "❌ Prompt 应显示高优先级"
    
    # 低优先级的不应该被包含（min_priority=7）
    # 注意：由于我们设置了 min_priority=7，优先级6的应该被过滤
    
    manager.end_session(success=True)
    print("\n✅ 测试 2 通过！")


def test_recommendation_filtering():
    """测试 Recommendation 过滤功能"""
    print("\n" + "="*70)
    print("🧪 测试 3: Recommendation 过滤功能")
    print("="*70)
    
    # 初始化
    manager = TransferMemoryManager(user_id="qtran_test_filter")
    manager.start_session("sqlite", "mongodb", "tlp")
    
    # 添加不同数据库对的 Recommendation
    print("\n📝 添加不同数据库对的 Recommendation...")
    
    # SQLite -> MongoDB
    manager.add_recommendation(
        target_agent="translation",
        priority=9,
        action="prioritize_features",
        features=["HEX"],
        reason="Test for SQLite->MongoDB",
        origin_db="sqlite",
        target_db="mongodb"
    )
    
    # MySQL -> PostgreSQL (不同的数据库对)
    manager.add_recommendation(
        target_agent="translation",
        priority=9,
        action="prioritize_features",
        features=["AUTO_INCREMENT"],
        reason="Test for MySQL->PostgreSQL",
        origin_db="mysql",
        target_db="postgres"
    )
    
    # 只获取 SQLite -> MongoDB 的建议
    print("\n🔍 获取 SQLite -> MongoDB 的建议...")
    sqlite_mongo_recs = manager.get_recommendations(
        origin_db="sqlite",
        target_db="mongodb",
        limit=10
    )
    
    print(f"✅ 找到 {len(sqlite_mongo_recs)} 条 SQLite->MongoDB 建议")
    for rec in sqlite_mongo_recs:
        print(f"   - {rec['features']}")
        assert "HEX" in rec['features'], "❌ 应该包含 HEX 特性"
    
    # 获取所有建议（不过滤数据库）
    print("\n🔍 获取所有建议...")
    all_recs = manager.get_recommendations(
        origin_db=None,
        target_db=None,
        limit=10
    )
    
    print(f"✅ 总共找到 {len(all_recs)} 条建议")
    
    manager.end_session(success=True)
    print("\n✅ 测试 3 通过！")


def test_performance_metrics():
    """测试性能指标"""
    print("\n" + "="*70)
    print("🧪 测试 4: 性能指标")
    print("="*70)
    
    # 初始化
    manager = TransferMemoryManager(user_id="qtran_test_perf", enable_metrics=True)
    manager.start_session("sqlite", "mongodb", "tlp")
    
    # 执行多次操作
    print("\n⚡ 执行多次 Recommendation 操作...")
    for i in range(5):
        manager.add_recommendation(
            target_agent="translation",
            priority=8 + i % 2,
            action="prioritize_features",
            features=[f"FEATURE_{i}"],
            reason=f"Test {i}",
            origin_db="sqlite",
            target_db="mongodb"
        )
    
    for i in range(3):
        recs = manager.get_recommendations(limit=2)
        print(f"   查询 {i+1}: 找到 {len(recs)} 条建议")
    
    # 获取性能报告
    print("\n📊 性能报告:")
    print(manager.get_metrics_report())
    
    manager.end_session(success=True)
    print("\n✅ 测试 4 通过！")


def test_integration_workflow():
    """测试完整的集成工作流"""
    print("\n" + "="*70)
    print("🧪 测试 5: 完整集成工作流")
    print("="*70)
    
    print("\n📖 模拟完整的工作流:")
    print("   1. 翻译阶段开始")
    print("   2. 执行翻译")
    print("   3. 变异测试发现问题")
    print("   4. 生成 Recommendation")
    print("   5. 下一次翻译使用 Recommendation")
    
    # 第一次翻译（无 Recommendation）
    print("\n🔄 第一次翻译...")
    manager = TransferMemoryManager(user_id="qtran_integration_test")
    manager.start_session("sqlite", "mongodb", "tlp")
    
    sql1 = "SELECT HEX(MIN(a)) FROM t1;"
    prompt1 = manager.build_enhanced_prompt(
        "Translate SQL",
        sql1,
        "sqlite",
        "mongodb",
        include_knowledge_base=False
    )
    
    print(f"   SQL: {sql1}")
    print(f"   Prompt 长度: {len(prompt1)} 字符")
    has_rec_1 = "HIGH PRIORITY RECOMMENDATIONS" in prompt1
    print(f"   包含 Recommendation: {has_rec_1}")
    
    # 模拟变异测试发现问题
    print("\n🔬 变异测试发现 TLP violation...")
    manager.add_recommendation(
        target_agent="translation",
        priority=9,
        action="prioritize_features",
        features=["HEX", "MIN", "aggregate"],
        reason="tlp_violation: TLP_violation",
        origin_db="sqlite",
        target_db="mongodb"
    )
    
    # 第二次翻译（有 Recommendation）
    print("\n🔄 第二次翻译...")
    sql2 = "SELECT MAX(b) FROM t2;"
    prompt2 = manager.build_enhanced_prompt(
        "Translate SQL",
        sql2,
        "sqlite",
        "mongodb",
        include_knowledge_base=False
    )
    
    print(f"   SQL: {sql2}")
    print(f"   Prompt 长度: {len(prompt2)} 字符")
    has_rec_2 = "HIGH PRIORITY RECOMMENDATIONS" in prompt2
    print(f"   包含 Recommendation: {has_rec_2}")
    
    # 验证
    assert not has_rec_1, "❌ 第一次翻译不应有 Recommendation"
    assert has_rec_2, "❌ 第二次翻译应该有 Recommendation"
    assert "HEX" in prompt2, "❌ 第二次翻译应该提到 HEX 特性"
    
    manager.end_session(success=True)
    print("\n✅ 测试 5 通过！")
    print("\n🎉 反向反馈机制工作正常！")


def main():
    """运行所有测试"""
    print("\n" + "="*70)
    print("🚀 MVP 反向反馈机制 - 完整测试套件")
    print("="*70)
    
    try:
        test_basic_recommendation()
        test_prompt_enhancement()
        test_recommendation_filtering()
        test_performance_metrics()
        test_integration_workflow()
        
        print("\n" + "="*70)
        print("✅ 所有测试通过！MVP 反向反馈机制验证成功！")
        print("="*70)
        
        print("\n📊 测试总结:")
        print("   ✅ Recommendation 存储/检索")
        print("   ✅ Prompt 增强")
        print("   ✅ 数据库对过滤")
        print("   ✅ 性能监控")
        print("   ✅ 完整工作流")
        
        print("\n🎯 下一步:")
        print("   1. 集成到实际的 translate_sqlancer.py")
        print("   2. 运行真实的翻译任务")
        print("   3. 观察 Bug 发现率提升")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

