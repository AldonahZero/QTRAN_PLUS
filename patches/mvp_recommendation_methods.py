#!/usr/bin/env python3
"""
MVP 反向反馈机制 - 代码补丁

使用说明:
1. 这个文件包含了需要添加到 mem0_adapter.py 的新方法
2. 复制这些方法到 TransferMemoryManager 类中
3. 修改 build_enhanced_prompt 方法添加 Recommendation 支持
"""

from typing import Dict, List, Any
from datetime import datetime
import time

# ============================================================
# 以下方法添加到 TransferMemoryManager 类中 (mem0_adapter.py)
# ============================================================

def add_recommendation(
    self,
    target_agent: str,
    priority: int,
    action: str,
    features: List[str],
    reason: str,
    origin_db: str = None,
    target_db: str = None,
    metadata: Dict[str, Any] = None
):
    """
    添加反向反馈建议
    
    Args:
        target_agent: 目标Agent（如 'translation'）
        priority: 优先级 (1-10，越高越重要)
        action: 建议动作类型
        features: 相关SQL特性列表
        reason: 生成原因
        origin_db: 源数据库
        target_db: 目标数据库
        metadata: 额外元数据
    """
    start_time = time.time()
    
    # 构建建议消息
    features_str = ", ".join(features) if features else "N/A"
    message = (
        f"Recommendation for {target_agent}: {action}. "
        f"Focus on features: {features_str}. "
        f"Reason: {reason}. Priority: {priority}/10"
    )
    
    # 合并元数据
    full_metadata = {
        "type": "recommendation",
        "target_agent": target_agent,
        "priority": priority,
        "action": action,
        "features": features,
        "reason": reason,
        "origin_db": origin_db or "unknown",
        "target_db": target_db or "unknown",
        "created_at": datetime.now().isoformat(),
        "used": False,
        "session_id": self.session_id
    }
    
    if metadata:
        full_metadata.update(metadata)
    
    try:
        self.memory.add(
            message,
            user_id=self.user_id,
            metadata=full_metadata
        )
        print(f"🔥 Added recommendation: {action} (Priority: {priority})")
        
        if self.enable_metrics:
            self.metrics["add_times"].append(time.time() - start_time)
            
    except Exception as e:
        print(f"⚠️ Failed to add recommendation: {e}")


def get_recommendations(
    self,
    origin_db: str = None,
    target_db: str = None,
    limit: int = 3,
    min_priority: int = 7,
    only_unused: bool = True
) -> List[Dict[str, Any]]:
    """
    获取未使用的高优先级建议
    
    Args:
        origin_db: 过滤源数据库
        target_db: 过滤目标数据库
        limit: 返回数量
        min_priority: 最低优先级
        only_unused: 只返回未使用的建议
    
    Returns:
        建议列表，按优先级降序排序
    """
    start_time = time.time()
    
    # 构建查询
    query = f"Recommendation for translation. Priority >= {min_priority}"
    if origin_db and target_db:
        query += f" from {origin_db} to {target_db}"
    
    try:
        # 搜索所有建议
        all_memories = self.memory.search(
            query=query,
            user_id=self.user_id,
            limit=limit * 2  # 多获取一些，然后过滤
        )
        
        # 过滤和排序
        recommendations = []
        for mem in all_memories:
            metadata = mem.get("metadata", {})
            
            # 检查类型
            if metadata.get("type") != "recommendation":
                continue
            
            # 检查优先级
            if metadata.get("priority", 0) < min_priority:
                continue
            
            # 检查是否已使用
            if only_unused and metadata.get("used", False):
                continue
            
            # 检查数据库匹配
            if origin_db and metadata.get("origin_db") != origin_db:
                continue
            if target_db and metadata.get("target_db") != target_db:
                continue
            
            recommendations.append({
                "memory_id": mem.get("id"),
                "action": metadata.get("action"),
                "features": metadata.get("features", []),
                "priority": metadata.get("priority"),
                "reason": metadata.get("reason"),
                "created_at": metadata.get("created_at"),
                "metadata": metadata
            })
        
        # 按优先级降序排序
        recommendations.sort(key=lambda x: x["priority"], reverse=True)
        
        if self.enable_metrics:
            self.metrics["search_times"].append(time.time() - start_time)
            self.metrics["hits"].append(1 if recommendations else 0)
        
        return recommendations[:limit]
        
    except Exception as e:
        print(f"⚠️ Failed to get recommendations: {e}")
        return []


def mark_recommendation_used(self, memory_id: str):
    """
    标记建议已使用
    
    注意：Mem0 不支持直接更新，这里通过添加使用记录来标记
    """
    try:
        # 添加使用记录
        self.memory.add(
            f"Used recommendation {memory_id}",
            user_id=self.user_id,
            metadata={
                "type": "recommendation_usage",
                "recommendation_id": memory_id,
                "used_at": datetime.now().isoformat()
            }
        )
        print(f"✅ Marked recommendation {memory_id} as used")
    except Exception as e:
        print(f"⚠️ Failed to mark recommendation as used: {e}")


# ============================================================
# 修改 build_enhanced_prompt 方法
# 在原方法的最后（return 之前）添加以下代码:
# ============================================================

"""
在 build_enhanced_prompt 方法中，找到最后的 return 语句之前，添加:

    # ========== 🔥 新增：Recommendation 增强 ==========
    recommendations = self.get_recommendations(
        origin_db=origin_db,
        target_db=target_db,
        limit=3,
        min_priority=7
    )
    
    if recommendations:
        enhanced_context += "\n\n" + "="*60 + "\n"
        enhanced_context += "🔥 HIGH PRIORITY RECOMMENDATIONS (from mutation feedback):\n"
        enhanced_context += "="*60 + "\n\n"
        
        for i, rec in enumerate(recommendations, 1):
            features_str = ", ".join(rec['features']) if rec['features'] else "N/A"
            enhanced_context += f"{i}. **{rec['action']}** (Priority: {rec['priority']}/10)\n"
            enhanced_context += f"   - Focus on: {features_str}\n"
            enhanced_context += f"   - Reason: {rec['reason']}\n"
            enhanced_context += f"   - Created: {rec['created_at']}\n\n"
            
            # 标记为已使用
            if rec.get('memory_id'):
                self.mark_recommendation_used(rec['memory_id'])
        
        enhanced_context += "Please prioritize these features in your translation.\n"
        enhanced_context += "="*60 + "\n"
"""

