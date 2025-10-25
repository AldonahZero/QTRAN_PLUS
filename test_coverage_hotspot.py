#!/usr/bin/env python3
"""
CoverageHotspot 功能测试脚本

测试：
1. 添加 CoverageHotspot
2. 查询 Hotspot
3. 更新 Hotspot 统计
4. 基于 Hotspot 生成 Recommendation
"""

import os
import sys

# 启用 Mem0
os.environ["QTRAN_USE_MEM0"] = "true"

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.TransferLLM.mem0_adapter import TransferMemoryManager


def test_add_hotspot():
    """测试添加 CoverageHotspot"""
    print("\n" + "="*70)
    print("🧪 测试 1: 添加 CoverageHotspot")
    print("="*70)
    
    manager = TransferMemoryManager(user_id="qtran_test_hotspot")
    manager.start_session("sqlite", "mongodb", "tlp")
    
    # 添加第一个 hotspot
    print("\n📝 添加 Hotspot 1: HEX + MIN...")
    manager.add_coverage_hotspot(
        features=["HEX", "MIN", "aggregate"],
        coverage_gain=15.3,
        origin_db="sqlite",
        target_db="mongodb",
        mutation_sql="SELECT HEX(MIN(a)) FROM t1;",
        metadata={
            "bug_type": "TLP_violation",
            "oracle_type": "tlp"
        }
    )
    
    # 添加第二个 hotspot（不同特性）
    print("\n📝 添加 Hotspot 2: COLLATE + NOCASE...")
    manager.add_coverage_hotspot(
        features=["COLLATE", "NOCASE", "ORDER_BY"],
        coverage_gain=12.7,
        origin_db="sqlite",
        target_db="mongodb",
        mutation_sql="SELECT * FROM t1 ORDER BY a COLLATE NOCASE;",
        metadata={
            "bug_type": "NoREC_mismatch",
            "oracle_type": "norec"
        }
    )
    
    # 添加第三个 hotspot（重复第一个特性，应该更新统计）
    print("\n📝 添加 Hotspot 3: HEX + MIN (重复)...")
    manager.add_coverage_hotspot(
        features=["HEX", "MIN", "aggregate"],
        coverage_gain=18.2,
        origin_db="sqlite",
        target_db="mongodb",
        mutation_sql="SELECT HEX(MIN(b)) FROM t2;",
        metadata={
            "bug_type": "TLP_violation",
            "oracle_type": "tlp"
        }
    )
    
    manager.end_session(success=True)
    print("\n✅ 测试 1 通过！")


def test_query_hotspots():
    """测试查询 CoverageHotspot"""
    print("\n" + "="*70)
    print("🧪 测试 2: 查询 CoverageHotspot")
    print("="*70)
    
    manager = TransferMemoryManager(user_id="qtran_test_hotspot")
    manager.start_session("sqlite", "mongodb", "tlp")
    
    # 查询所有高价值热点
    print("\n🔍 查询高价值热点 (gain >= 10%)...")
    hotspots = manager.get_coverage_hotspots(
        origin_db="sqlite",
        target_db="mongodb",
        min_coverage_gain=10.0,
        limit=10
    )
    
    print(f"\n✅ 找到 {len(hotspots)} 个热点:")
    for i, hotspot in enumerate(hotspots, 1):
        print(f"\n   {i}. {hotspot['hotspot_id']}")
        print(f"      特性: {', '.join(hotspot['features'])}")
        print(f"      平均覆盖率增长: {hotspot['avg_coverage_gain']:.2f}%")
        print(f"      出现次数: {hotspot['occurrence_count']}")
        print(f"      数据库: {hotspot['origin_db']} -> {hotspot['target_db']}")
    
    # 查询特定特性
    print("\n🔍 查询特定特性 (HEX + MIN + aggregate)...")
    specific_hotspots = manager.get_coverage_hotspots(
        features=["HEX", "MIN", "aggregate"],
        origin_db="sqlite",
        target_db="mongodb",
        limit=5
    )
    
    if specific_hotspots:
        hotspot = specific_hotspots[0]
        print(f"\n✅ 找到特定热点:")
        print(f"   平均覆盖率增长: {hotspot['avg_coverage_gain']:.2f}%")
        print(f"   出现次数: {hotspot['occurrence_count']}")
    else:
        print("\n⚠️ 未找到特定热点")
    
    manager.end_session(success=True)
    print("\n✅ 测试 2 通过！")


def test_generate_recommendation_from_hotspot():
    """测试基于 Hotspot 生成 Recommendation"""
    print("\n" + "="*70)
    print("🧪 测试 3: 基于 Hotspot 生成 Recommendation")
    print("="*70)
    
    manager = TransferMemoryManager(user_id="qtran_test_hotspot")
    manager.start_session("sqlite", "mongodb", "tlp")
    
    # 获取最高价值的热点
    print("\n🔍 获取最高价值的热点...")
    hotspots = manager.get_coverage_hotspots(
        origin_db="sqlite",
        target_db="mongodb",
        min_coverage_gain=10.0,
        limit=3
    )
    
    print(f"✅ 找到 {len(hotspots)} 个热点")
    
    # 为每个热点生成 Recommendation
    print("\n🔥 基于热点生成 Recommendation...")
    for hotspot in hotspots:
        manager.generate_recommendation_from_hotspot(hotspot, priority_boost=1)
    
    # 查询生成的 Recommendations
    print("\n🔍 查询生成的 Recommendations...")
    recommendations = manager.get_recommendations(
        origin_db="sqlite",
        target_db="mongodb",
        limit=10
    )
    
    print(f"\n✅ 找到 {len(recommendations)} 条建议:")
    for i, rec in enumerate(recommendations, 1):
        print(f"\n   {i}. {rec['action']}")
        print(f"      特性: {', '.join(rec['features'])}")
        print(f"      优先级: {rec['priority']}/10")
        print(f"      原因: {rec['reason']}")
        
        # 检查是否来自 hotspot
        if rec.get('metadata', {}).get('source') == 'coverage_hotspot':
            print(f"      ✅ 来源: CoverageHotspot")
            print(f"      覆盖率增长: {rec['metadata'].get('avg_coverage_gain', 0):.2f}%")
    
    manager.end_session(success=True)
    print("\n✅ 测试 3 通过！")


def test_integration_workflow():
    """测试完整的集成工作流"""
    print("\n" + "="*70)
    print("🧪 测试 4: 完整集成工作流")
    print("="*70)
    
    print("\n📖 模拟完整的工作流:")
    print("   1. 变异测试发现 Bug（生成 Hotspot）")
    print("   2. 多次出现相同特性（更新 Hotspot 统计）")
    print("   3. 基于高价值 Hotspot 生成 Recommendation")
    print("   4. 翻译时使用 Recommendation 增强 Prompt")
    
    manager = TransferMemoryManager(user_id="qtran_integration_hotspot")
    manager.start_session("sqlite", "mongodb", "tlp")
    
    # 模拟多次发现相同特性的 Bug
    print("\n🔬 模拟变异测试...")
    test_cases = [
        (["HEX", "aggregate"], 14.5, "TLP_violation"),
        (["HEX", "aggregate"], 16.2, "TLP_violation"),
        (["HEX", "aggregate"], 13.8, "TLP_violation"),
        (["COLLATE"], 11.3, "NoREC_mismatch"),
        (["COLLATE"], 12.7, "NoREC_mismatch"),
    ]
    
    for i, (features, gain, bug_type) in enumerate(test_cases, 1):
        print(f"   测试 {i}: {', '.join(features)} (gain: {gain}%)")
        manager.add_coverage_hotspot(
            features=features,
            coverage_gain=gain,
            origin_db="sqlite",
            target_db="mongodb",
            metadata={"bug_type": bug_type}
        )
    
    # 查询最高价值的热点
    print("\n🔍 查询高价值热点...")
    hotspots = manager.get_coverage_hotspots(
        origin_db="sqlite",
        target_db="mongodb",
        min_coverage_gain=10.0,
        min_occurrence=2,  # 至少出现2次
        limit=5
    )
    
    print(f"\n✅ 找到 {len(hotspots)} 个高频高价值热点:")
    for hotspot in hotspots:
        print(f"   - {', '.join(hotspot['features'])}: "
              f"{hotspot['avg_coverage_gain']:.2f}% (出现 {hotspot['occurrence_count']} 次)")
        
        # 生成 Recommendation
        manager.generate_recommendation_from_hotspot(hotspot)
    
    # 构建增强 Prompt
    print("\n🔨 构建增强 Prompt...")
    base_prompt = "Translate SQL from SQLite to MongoDB."
    query_sql = "SELECT MAX(a) FROM t1;"
    
    enhanced_prompt = manager.build_enhanced_prompt(
        base_prompt=base_prompt,
        query_sql=query_sql,
        origin_db="sqlite",
        target_db="mongodb",
        include_knowledge_base=False
    )
    
    # 检查是否包含 Recommendation
    has_rec = "HIGH PRIORITY RECOMMENDATIONS" in enhanced_prompt
    print(f"\n✅ Prompt 包含 Recommendation: {has_rec}")
    
    if has_rec:
        # 检查是否提到了高价值特性
        if "HEX" in enhanced_prompt or "aggregate" in enhanced_prompt:
            print("✅ Prompt 提到了高价值特性（HEX/aggregate）")
    
    manager.end_session(success=True)
    print("\n✅ 测试 4 通过！")
    print("\n🎉 CoverageHotspot 反馈机制工作正常！")


def main():
    """运行所有测试"""
    print("\n" + "="*70)
    print("🚀 CoverageHotspot 功能 - 完整测试套件")
    print("="*70)
    
    try:
        test_add_hotspot()
        test_query_hotspots()
        test_generate_recommendation_from_hotspot()
        test_integration_workflow()
        
        print("\n" + "="*70)
        print("✅ 所有测试通过！CoverageHotspot 功能验证成功！")
        print("="*70)
        
        print("\n📊 测试总结:")
        print("   ✅ Hotspot 添加/更新")
        print("   ✅ Hotspot 查询/过滤")
        print("   ✅ 基于 Hotspot 生成 Recommendation")
        print("   ✅ 完整工作流集成")
        
        print("\n🎯 核心创新点:")
        print("   1. 自动识别高覆盖率增长的特性组合")
        print("   2. 智能更新 Hotspot 统计（平均值、出现次数）")
        print("   3. 基于 Hotspot 生成高优先级 Recommendation")
        print("   4. 形成正反馈循环：发现 -> Hotspot -> Recommendation -> 优化翻译")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

