"""
SimpleCoordinator - 轻量级协调器

基于黑板模式的状态轮询和策略调整，实现动态工作流优化。

功能：
1. 从 Mem0（黑板）读取 Recommendation 和 CoverageHotspot
2. 根据优先级动态调整工作流策略
3. 监控反馈效果，生成统计报告

设计理念：
- 最小侵入：不修改现有翻译/变异逻辑
- 策略增强：通过参数调整影响工作流
- 数据驱动：基于实时反馈做决策
"""

from typing import Dict, Any


class SimpleCoordinator:
    """
    轻量级协调器：基于黑板模式的状态轮询和策略调整
    
    使用示例：
    ```python
    coordinator = SimpleCoordinator(user_id="qtran_redis_to_mongodb")
    coordinator.initialize_memory_manager()
    
    # 轮询黑板状态
    state = coordinator.poll_state()
    
    # 决策策略
    strategy = coordinator.decide_strategy(state)
    
    # 应用策略
    base_params = {"temperature": 0.3, "iteration_num": 4}
    adjusted_params = coordinator.adjust_workflow_params(base_params, strategy)
    
    # 输出统计
    coordinator.report_stats()
    ```
    """
    
    def __init__(self, user_id: str = "qtran_redis_to_mongodb"):
        """
        初始化协调器
        
        参数:
        - user_id: Mem0 用户标识
        """
        self.user_id = user_id
        self.memory_manager = None
        self.stats = {
            "total_recommendations": 0,
            "high_priority_count": 0,
            "applied_recommendations": 0,
            "hotspots_count": 0,
            "strategy_adjustments": 0,
        }
        
    def initialize_memory_manager(self):
        """
        延迟初始化 Mem0 Manager（避免循环依赖）
        
        返回:
        - bool: 初始化是否成功
        """
        try:
            # 尝试多种导入路径以确保兼容性
            try:
                from src.TransferLLM.mem0_adapter import TransferMemoryManager
            except ImportError:
                # 如果从 src 导入失败，尝试相对路径
                import sys
                import os
                current_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(os.path.dirname(current_dir))
                if project_root not in sys.path:
                    sys.path.insert(0, project_root)
                from src.TransferLLM.mem0_adapter import TransferMemoryManager
            
            self.memory_manager = TransferMemoryManager(user_id=self.user_id)
            print("✅ 协调器：Mem0 连接成功")
            return True
        except Exception as e:
            print(f"⚠️ 协调器：Mem0 初始化失败 ({e})，协调功能部分受限")
            return False
    
    def poll_state(self) -> Dict[str, Any]:
        """
        轮询黑板状态：从 Mem0 读取当前的 Recommendation 和 Hotspot
        
        返回:
        - state: 包含 recommendations 和 hotspots 的字典
          {
              "recommendations": List[Dict],
              "hotspots": List[Dict],
              "has_high_priority": bool,
              "top_recommendation": Optional[Dict]
          }
        """
        state = {
            "recommendations": [],
            "hotspots": [],
            "has_high_priority": False,
            "top_recommendation": None,
        }
        
        if not self.memory_manager:
            return state
        
        try:
            # 读取所有 Recommendation (限制返回最近10条)
            # get_recommendations 参数: origin_db, target_db, limit, min_priority, only_unused
            recs = self.memory_manager.get_recommendations(
                limit=10,
                min_priority=7,
                only_unused=False  # 获取所有建议，包括已使用的
            )
            state["recommendations"] = recs
            self.stats["total_recommendations"] = len(recs)
            
            # 筛选高优先级 Recommendation (priority >= 8)
            high_priority_recs = [r for r in recs if r.get("priority", 0) >= 8]
            state["has_high_priority"] = len(high_priority_recs) > 0
            self.stats["high_priority_count"] = len(high_priority_recs)
            
            # 获取最高优先级的 Recommendation
            if high_priority_recs:
                state["top_recommendation"] = max(
                    high_priority_recs, 
                    key=lambda r: r.get("priority", 0)
                )
            
            # 读取 CoverageHotspot (限制返回前5个)
            # get_coverage_hotspots 参数: features, origin_db, target_db, min_coverage_gain, min_occurrence, limit
            hotspots = self.memory_manager.get_coverage_hotspots(
                limit=5,
                min_coverage_gain=5.0,
                min_occurrence=1
            )
            state["hotspots"] = hotspots
            self.stats["hotspots_count"] = len(hotspots)
            
        except Exception as e:
            print(f"⚠️ 协调器：轮询状态失败 ({e})")
        
        return state
    
    def decide_strategy(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        策略决策：根据黑板状态决定工作流调整
        
        参数:
        - state: poll_state() 返回的状态字典
        
        返回:
        - strategy: 策略调整建议
          {
              "adjust_temperature": Optional[float],
              "adjust_iterations": Optional[int],
              "priority_boost": bool,
              "focus_features": List[str],
              "recommended_action": Optional[str]
          }
        """
        strategy = {
            "adjust_temperature": None,  # 是否调整 LLM temperature
            "adjust_iterations": None,   # 是否调整迭代次数
            "priority_boost": False,     # 是否提升优先级处理
            "focus_features": [],        # 需要重点关注的特性
            "recommended_action": None,  # 推荐动作
        }
        
        # 规则1: 如果有高优先级 Recommendation，降低 temperature 提升稳定性
        if state["has_high_priority"]:
            top_rec = state["top_recommendation"]
            if top_rec:
                strategy["adjust_temperature"] = 0.2  # 降低随机性
                strategy["priority_boost"] = True
                
                # 获取推荐动作（从 action 或 reason 字段）
                action = top_rec.get("action", "")
                reason = top_rec.get("reason", "")
                strategy["recommended_action"] = action if action else reason
                
                # 提取建议关注的特性
                features = top_rec.get("features", [])
                for feature in features:
                    feature_upper = feature.upper()
                    if feature_upper not in strategy["focus_features"]:
                        strategy["focus_features"].append(feature_upper)
                
                # 如果没有从 features 字段获取，尝试从 reason 文本提取
                if not strategy["focus_features"]:
                    if "HEX" in reason or "hex" in reason.lower():
                        strategy["focus_features"].append("HEX")
                    if "MIN" in reason or "min" in reason.lower():
                        strategy["focus_features"].append("MIN")
                    if "aggregate" in reason.lower():
                        strategy["focus_features"].append("aggregate")
                
                self.stats["applied_recommendations"] += 1
        
        # 规则2: 如果有高覆盖率 Hotspot，增加迭代次数
        high_coverage_hotspots = [
            h for h in state["hotspots"] 
            if h.get("avg_coverage_gain", 0) > 10
        ]
        if high_coverage_hotspots:
            strategy["adjust_iterations"] = 6  # 增加迭代次数
        
        # 规则3: 如果没有任何反馈，保持默认策略
        if not state["recommendations"] and not state["hotspots"]:
            strategy["recommended_action"] = "探索模式：正常执行翻译流程"
        
        return strategy
    
    def adjust_workflow_params(
        self, 
        base_params: Dict[str, Any], 
        strategy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        应用策略：根据策略调整工作流参数
        
        参数:
        - base_params: 原始参数（temperature, iteration_num等）
        - strategy: decide_strategy() 返回的策略
        
        返回:
        - adjusted_params: 调整后的参数
        """
        adjusted = base_params.copy()
        
        if strategy["adjust_temperature"] is not None:
            adjusted["temperature"] = strategy["adjust_temperature"]
            self.stats["strategy_adjustments"] += 1
            print(f"🎯 协调器：调整 temperature → {strategy['adjust_temperature']}")
        
        if strategy["adjust_iterations"] is not None:
            adjusted["iteration_num"] = strategy["adjust_iterations"]
            self.stats["strategy_adjustments"] += 1
            print(f"🎯 协调器：调整 iteration_num → {strategy['adjust_iterations']}")
        
        if strategy["priority_boost"]:
            print(f"🚀 协调器：高优先级模式激活")
            if strategy["recommended_action"]:
                print(f"   推荐动作: {strategy['recommended_action']}")
        
        if strategy["focus_features"]:
            print(f"🔍 协调器：重点关注特性 → {', '.join(strategy['focus_features'])}")
        
        return adjusted
    
    def report_stats(self):
        """输出协调器运行统计"""
        print("\n" + "="*60)
        print("📊 协调器运行统计")
        print("="*60)
        # print(f"  总 Recommendation 数: {self.stats['total_recommendations']}")
        print(f"  高优先级建议数: {self.stats['high_priority_count']}")
        # print(f"  应用的建议数: {self.stats['applied_recommendations']}")
        # print(f"  检测到的 Hotspot 数: {self.stats['hotspots_count']}")
        print(f"  策略调整次数: {self.stats['strategy_adjustments']}")
        print("="*60 + "\n")

