"""
测试协调器（SimpleCoordinator）功能

运行方法：
    pytest tests/test_coordinator.py -v
或：
    python tests/test_coordinator.py
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.Coordinator import SimpleCoordinator


def test_coordinator_initialization():
    """测试协调器初始化"""
    coordinator = SimpleCoordinator(user_id="test_user")
    
    assert coordinator.user_id == "test_user"
    assert coordinator.memory_manager is None
    assert coordinator.stats["total_recommendations"] == 0
    assert coordinator.stats["high_priority_count"] == 0
    print("✅ 测试通过：协调器初始化")


def test_poll_state_without_memory():
    """测试无 Mem0 时的状态轮询"""
    coordinator = SimpleCoordinator(user_id="test_user")
    
    state = coordinator.poll_state()
    
    assert state["recommendations"] == []
    assert state["hotspots"] == []
    assert state["has_high_priority"] is False
    assert state["top_recommendation"] is None
    print("✅ 测试通过：无 Mem0 时的状态轮询")


def test_decide_strategy_no_feedback():
    """测试无反馈时的策略决策"""
    coordinator = SimpleCoordinator(user_id="test_user")
    
    state = {
        "recommendations": [],
        "hotspots": [],
        "has_high_priority": False,
        "top_recommendation": None,
    }
    
    strategy = coordinator.decide_strategy(state)
    
    assert strategy["adjust_temperature"] is None
    assert strategy["adjust_iterations"] is None
    assert strategy["priority_boost"] is False
    assert strategy["focus_features"] == []
    assert "探索模式" in strategy["recommended_action"]
    print("✅ 测试通过：无反馈时的策略决策")


def test_decide_strategy_high_priority():
    """测试高优先级建议时的策略决策"""
    coordinator = SimpleCoordinator(user_id="test_user")
    
    state = {
        "recommendations": [
            {
                "priority": 9,
                "action": "prioritize_high_coverage_features",
                "features": ["HEX", "MIN", "aggregate"],
                "reason": "建议优先生成包含 HEX() 和 MIN() 的 SQL"
            }
        ],
        "hotspots": [],
        "has_high_priority": True,
        "top_recommendation": {
            "priority": 9,
            "action": "prioritize_high_coverage_features",
            "features": ["HEX", "MIN", "aggregate"],
            "reason": "建议优先生成包含 HEX() 和 MIN() 的 SQL"
        },
    }
    
    strategy = coordinator.decide_strategy(state)
    
    assert strategy["adjust_temperature"] == 0.2
    assert strategy["priority_boost"] is True
    assert "HEX" in strategy["focus_features"]
    assert "MIN" in strategy["focus_features"]
    assert "AGGREGATE" in strategy["focus_features"]
    assert strategy["recommended_action"] == "prioritize_high_coverage_features"
    assert coordinator.stats["applied_recommendations"] == 1
    print("✅ 测试通过：高优先级建议时的策略决策")


def test_decide_strategy_high_coverage_hotspot():
    """测试高覆盖率 Hotspot 时的策略决策"""
    coordinator = SimpleCoordinator(user_id="test_user")
    
    state = {
        "recommendations": [],
        "hotspots": [
            {
                "features": ["HEX", "MIN", "aggregate"],
                "avg_coverage_gain": 15.5,
                "occurrence_count": 5,
            }
        ],
        "has_high_priority": False,
        "top_recommendation": None,
    }
    
    strategy = coordinator.decide_strategy(state)
    
    assert strategy["adjust_iterations"] == 6
    print("✅ 测试通过：高覆盖率 Hotspot 时的策略决策")


def test_adjust_workflow_params():
    """测试工作流参数调整"""
    coordinator = SimpleCoordinator(user_id="test_user")
    
    base_params = {
        "temperature": 0.3,
        "iteration_num": 4,
        "model": "gpt-4o-mini",
        "error_iteration": True,
        "FewShot": False,
        "with_knowledge": True,
    }
    
    strategy = {
        "adjust_temperature": 0.2,
        "adjust_iterations": 6,
        "priority_boost": True,
        "focus_features": ["HEX", "MIN"],
        "recommended_action": "优先测试 HEX 函数"
    }
    
    adjusted = coordinator.adjust_workflow_params(base_params, strategy)
    
    assert adjusted["temperature"] == 0.2
    assert adjusted["iteration_num"] == 6
    assert adjusted["model"] == "gpt-4o-mini"
    assert coordinator.stats["strategy_adjustments"] == 2
    print("✅ 测试通过：工作流参数调整")


def test_adjust_workflow_params_no_change():
    """测试无策略调整时的参数保持"""
    coordinator = SimpleCoordinator(user_id="test_user")
    
    base_params = {
        "temperature": 0.3,
        "iteration_num": 4,
        "model": "gpt-4o-mini",
    }
    
    strategy = {
        "adjust_temperature": None,
        "adjust_iterations": None,
        "priority_boost": False,
        "focus_features": [],
        "recommended_action": None
    }
    
    adjusted = coordinator.adjust_workflow_params(base_params, strategy)
    
    assert adjusted == base_params
    assert coordinator.stats["strategy_adjustments"] == 0
    print("✅ 测试通过：无策略调整时的参数保持")


def test_report_stats():
    """测试统计报告输出"""
    coordinator = SimpleCoordinator(user_id="test_user")
    
    coordinator.stats = {
        "total_recommendations": 12,
        "high_priority_count": 3,
        "applied_recommendations": 3,
        "hotspots_count": 5,
        "strategy_adjustments": 4,
    }
    
    # 应该正常输出，不抛出异常
    coordinator.report_stats()
    print("✅ 测试通过：统计报告输出")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("🧪 开始测试协调器功能")
    print("="*60 + "\n")
    
    try:
        test_coordinator_initialization()
        test_poll_state_without_memory()
        test_decide_strategy_no_feedback()
        test_decide_strategy_high_priority()
        test_decide_strategy_high_coverage_hotspot()
        test_adjust_workflow_params()
        test_adjust_workflow_params_no_change()
        test_report_stats()
        
        print("\n" + "="*60)
        print("🎉 所有测试通过！")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}\n")
        raise
    except Exception as e:
        print(f"\n❌ 测试出错: {e}\n")
        raise


if __name__ == "__main__":
    run_all_tests()

