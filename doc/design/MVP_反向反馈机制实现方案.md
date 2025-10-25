# 最小可行方案（MVP）：反向反馈机制实现方案

**版本**: v1.0  
**日期**: 2025-10-25  
**作者**: QTRAN Team  
**状态**: ✅ 设计完成

---

## 📋 目标

在 **~100-200 行代码** 内实现核心的反向反馈机制，验证其有效性。

### 核心思想

```
变异测试发现 → 生成 Recommendation → 翻译阶段读取 → 调整策略
```

---

## 🎯 实现步骤

### 1️⃣ 在 Mem0 中添加 Recommendation 实体

**文件**: `src/TransferLLM/mem0_adapter.py`

**需要添加的方法**:
- `add_recommendation()` - 添加建议
- `get_recommendations()` - 获取建议
- `mark_recommendation_used()` - 标记建议已使用

**代码量**: ~60 行

---

### 2️⃣ 在变异测试后生成 Recommendation

**文件**: `src/TransferLLM/translate_sqlancer.py`

**触发条件**:
- TLP Oracle 发现违反（`oracle_check_res["end"] == False` 且无执行错误）
- 覆盖率增长显著（如果有覆盖率数据）
- 发现高价值的SQL特性组合

**生成逻辑**:
```python
if oracle_check_res["end"] == False and oracle_check_res.get("error") in [None, "None"]:
    # 发现潜在Bug，生成高优先级 Recommendation
    mem0_manager.add_recommendation(
        target_agent="translation",
        priority=9,
        action="prioritize_features",
        features=extract_sql_features(original_sql),
        reason="tlp_violation"
    )
```

**代码量**: ~40 行

---

### 3️⃣ 在翻译前读取并调整 Prompt

**文件**: `src/TransferLLM/mem0_adapter.py` (修改 `build_enhanced_prompt`)

**调整逻辑**:
```python
# 在 build_enhanced_prompt 中添加
recommendations = self.get_recommendations(limit=3)
if recommendations:
    rec_text = "\n🔥 HIGH PRIORITY RECOMMENDATIONS:\n"
    for rec in recommendations:
        rec_text += f"- {rec['action']}: {rec['features']} (Priority: {rec['priority']})\n"
        rec_text += f"  Reason: {rec['reason']}\n"
    
    enhanced_prompt += rec_text
```

**代码量**: ~30 行

---

## 🗂️ Recommendation 数据结构

### Mem0 存储格式

```python
{
    "type": "recommendation",
    "target_agent": "translation",  # 目标Agent
    "priority": 9,                   # 优先级 (1-10)
    "action": "prioritize_features", # 动作类型
    "features": ["HEX", "MIN", "aggregate"],  # SQL特性列表
    "reason": "tlp_violation",       # 生成原因
    "origin_db": "sqlite",
    "target_db": "mongodb",
    "created_at": "2025-10-25T10:30:00",
    "used": False,                   # 是否已使用
    "effectiveness_score": None      # 有效性评分（可选）
}
```

### 建议类型

| Action 类型 | 说明 | 示例 |
|------------|------|------|
| `prioritize_features` | 优先测试某些SQL特性 | "HEX + MIN + aggregate" |
| `avoid_pattern` | 避免某种模式（频繁失败） | "COLLATE with MongoDB" |
| `combine_features` | 组合特定特性 | "UNION + LIMIT" |
| `focus_on_edge_case` | 关注边界情况 | "NULL handling in JOIN" |

---

## 💻 完整代码实现

### 文件 1: `src/TransferLLM/mem0_adapter.py` (新增方法)

```python
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
    标记建议已使用（简化版：通过更新metadata）
    
    注意：Mem0 不支持直接更新，这里我们只记录日志
    实际应用中可以通过添加新记忆来标记使用
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
```

---

### 文件 2: `src/TransferLLM/mem0_adapter.py` (修改 `build_enhanced_prompt`)

在 `build_enhanced_prompt` 方法的最后，添加 Recommendation 增强：

```python
def build_enhanced_prompt(
    self,
    base_prompt: str,
    query_sql: str,
    origin_db: str,
    target_db: str,
    include_knowledge_base: bool = None
) -> str:
    """
    使用历史记忆、知识库和 Recommendation 增强 prompt
    """
    # ... 原有逻辑（历史记忆 + 知识库）...
    
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
    
    # 返回增强后的 prompt
    if enhanced_context:
        return f"{base_prompt}\n\n{enhanced_context}"
    return base_prompt
```

---

### 文件 3: `src/TransferLLM/translate_sqlancer.py` (在 Oracle 检查后生成 Recommendation)

在 `sqlancer_translate` 函数的 Oracle 检查后，添加 Recommendation 生成逻辑：

```python
# 在 line 585-650 附近，TLP Oracle 检查之后
if is_tlp_mutation(mutate_results[-1]):
    try:
        # ... 原有的 TLP 检查逻辑 ...
        oracle_check_res = check_tlp_oracle(tlp_results)
        
        # 🔥 新增：生成 Recommendation
        if use_mem0 and mem0_manager:
            _generate_recommendation_from_oracle(
                mem0_manager=mem0_manager,
                oracle_result=oracle_check_res,
                original_sql=sql_statement,
                origin_db=origin_db,
                target_db=target_db,
                oracle_type="tlp"
            )
            
    except Exception as e:
        print(f"TLP oracle check failed: {e}")
        oracle_check_res = {"end": False, "error": str(e)}
```

**新增辅助函数** (在文件末尾添加)：

```python
def _generate_recommendation_from_oracle(
    mem0_manager,
    oracle_result: Dict[str, Any],
    original_sql: str,
    origin_db: str,
    target_db: str,
    oracle_type: str
):
    """
    根据 Oracle 检查结果生成 Recommendation
    
    Args:
        mem0_manager: Mem0 管理器
        oracle_result: Oracle 检查结果
        original_sql: 原始SQL
        origin_db: 源数据库
        target_db: 目标数据库
        oracle_type: Oracle 类型 (tlp/norec/semantic)
    """
    # 只在发现潜在Bug时生成建议
    if oracle_result.get("end") == False and oracle_result.get("error") in [None, "None", ""]:
        # 提取SQL特性
        features = _extract_sql_features(original_sql)
        
        # 计算优先级（基于bug类型）
        bug_type = oracle_result.get("bug_type", "unknown")
        priority = 9 if bug_type == "TLP_violation" else 8
        
        # 生成建议
        mem0_manager.add_recommendation(
            target_agent="translation",
            priority=priority,
            action="prioritize_features",
            features=features,
            reason=f"{oracle_type}_oracle_violation: {bug_type}",
            origin_db=origin_db,
            target_db=target_db,
            metadata={
                "bug_type": bug_type,
                "oracle_type": oracle_type,
                "details": oracle_result.get("details", {})
            }
        )
        
        print(f"🔥 Generated recommendation: prioritize {', '.join(features)}")


def _extract_sql_features(sql: str) -> List[str]:
    """
    从SQL中提取关键特性
    
    Returns:
        特性列表，如 ["HEX", "MIN", "COLLATE", "aggregate"]
    """
    features = []
    sql_upper = sql.upper()
    
    # 函数
    functions = ["HEX", "MIN", "MAX", "SUM", "AVG", "COUNT", "ABS", "CONCAT", "SUBSTR"]
    for func in functions:
        if f"{func}(" in sql_upper:
            features.append(func)
    
    # 特殊关键字
    keywords = ["COLLATE", "UNION", "INTERSECT", "EXCEPT", "JOIN", "GROUP BY", "HAVING"]
    for kw in keywords:
        if kw in sql_upper:
            features.append(kw.replace(" ", "_"))
    
    # 聚合判断
    if any(agg in sql_upper for agg in ["MIN(", "MAX(", "SUM(", "AVG(", "COUNT("]):
        if "aggregate" not in features:
            features.append("aggregate")
    
    # MongoDB特定操作符（如果是NoSQL翻译）
    mongodb_ops = ["$and", "$or", "$not", "$exists", "$type", "$gte", "$lte"]
    for op in mongodb_ops:
        if op in sql:
            features.append(op)
    
    return features[:5]  # 限制返回最多5个特性
```

---

## 🧪 测试验证

### 测试脚本: `test_recommendation_mvp.py`

```python
#!/usr/bin/env python3
"""测试反向反馈机制 MVP"""

import os
os.environ["QTRAN_USE_MEM0"] = "true"

from src.TransferLLM.mem0_adapter import TransferMemoryManager

def test_recommendation_workflow():
    """测试完整的 Recommendation 工作流"""
    
    # 1. 初始化
    manager = TransferMemoryManager(user_id="qtran_sqlite_to_mongodb")
    manager.start_session("sqlite", "mongodb", "tlp")
    
    # 2. 模拟变异测试后生成 Recommendation
    print("\n=== 步骤1: 生成 Recommendation ===")
    manager.add_recommendation(
        target_agent="translation",
        priority=9,
        action="prioritize_features",
        features=["HEX", "MIN", "aggregate"],
        reason="tlp_violation: TLP_violation",
        origin_db="sqlite",
        target_db="mongodb"
    )
    
    # 3. 获取 Recommendation
    print("\n=== 步骤2: 获取 Recommendation ===")
    recommendations = manager.get_recommendations(
        origin_db="sqlite",
        target_db="mongodb",
        limit=3
    )
    print(f"Found {len(recommendations)} recommendations")
    for rec in recommendations:
        print(f"  - {rec['action']}: {rec['features']} (Priority: {rec['priority']})")
    
    # 4. 增强 Prompt
    print("\n=== 步骤3: 增强 Prompt ===")
    base_prompt = "Translate the following SQL from SQLite to MongoDB."
    query_sql = "SELECT HEX(MIN(a)) FROM t1;"
    
    enhanced_prompt = manager.build_enhanced_prompt(
        base_prompt=base_prompt,
        query_sql=query_sql,
        origin_db="sqlite",
        target_db="mongodb",
        include_knowledge_base=False  # 简化测试
    )
    
    print("\n=== Enhanced Prompt ===")
    print(enhanced_prompt)
    
    # 5. 性能报告
    print("\n" + manager.get_metrics_report())
    
    manager.end_session(success=True)
    print("\n✅ Test completed!")


if __name__ == "__main__":
    test_recommendation_workflow()
```

### 运行测试

```bash
cd /root/QTRAN
python test_recommendation_mvp.py
```

**预期输出**:
```
=== 步骤1: 生成 Recommendation ===
🔥 Added recommendation: prioritize_features (Priority: 9)

=== 步骤2: 获取 Recommendation ===
Found 1 recommendations
  - prioritize_features: ['HEX', 'MIN', 'aggregate'] (Priority: 9)

=== 步骤3: 增强 Prompt ===

=== Enhanced Prompt ===
Translate the following SQL from SQLite to MongoDB.

============================================================
🔥 HIGH PRIORITY RECOMMENDATIONS (from mutation feedback):
============================================================

1. **prioritize_features** (Priority: 9/10)
   - Focus on: HEX, MIN, aggregate
   - Reason: tlp_violation: TLP_violation
   - Created: 2025-10-25T10:30:00

Please prioritize these features in your translation.
============================================================

=== Mem0 Performance Metrics ===
⏱️  Average search time: 0.089s
🔍 Total searches: 1
💾 Total additions: 2
🎯 Memory hit rate: 100.0%
================================

✅ Test completed!
```

---

## 📊 预期效果

### 短期效果（1-2周验证）

| 指标 | 当前 | 预期 (MVP) |
|------|------|-----------|
| 高价值特性命中率 | 随机 | **+30-40%** |
| TLP violation 重现率 | 低 | **+50%** |
| 翻译首次成功率 | ~85% | **~88%** |

### 验证方式

1. **A/B 测试**：
   - 对照组：不启用 Recommendation
   - 实验组：启用 Recommendation
   - 比较 Bug 发现速度和覆盖率增长

2. **案例分析**：
   - 记录哪些 Recommendation 被采纳
   - 分析采纳后的翻译质量变化

3. **日志监控**：
   - 统计 Recommendation 生成频率
   - 统计 Recommendation 使用率

---

## 🚀 后续优化方向

### 阶段 2: 智能优先级计算 (~50 行)

```python
def calculate_recommendation_priority(
    oracle_result: Dict,
    historical_success_rate: float,
    feature_rarity: float
) -> int:
    """基于多因素计算优先级"""
    base_priority = 5
    
    # Bug 严重性
    if oracle_result.get("bug_type") == "TLP_violation":
        base_priority += 3
    
    # 历史成功率（低成功率 = 高优先级）
    if historical_success_rate < 0.5:
        base_priority += 2
    
    # 特性稀有度（罕见特性 = 高优先级）
    if feature_rarity > 0.8:
        base_priority += 1
    
    return min(base_priority, 10)
```

### 阶段 3: 有效性反馈 (~50 行)

```python
def update_recommendation_effectiveness(
    memory_id: str,
    was_effective: bool,
    outcome: Dict
):
    """更新 Recommendation 的有效性评分"""
    # 记录使用结果
    # 用于未来的优先级调整
    pass
```

---

## 📝 代码总结

| 文件 | 修改类型 | 代码量 |
|------|---------|--------|
| `src/TransferLLM/mem0_adapter.py` | 新增方法 | ~120 行 |
| `src/TransferLLM/translate_sqlancer.py` | 添加调用 | ~60 行 |
| `test_recommendation_mvp.py` | 测试脚本 | ~80 行 |
| **总计** | | **~260 行** |

实际集成代码（不含测试和注释）：**~150 行**

---

## ✅ 验收标准

1. ✅ Mem0 成功存储 Recommendation
2. ✅ TLP violation 后自动生成 Recommendation
3. ✅ 翻译前成功读取并注入 Prompt
4. ✅ 测试脚本运行通过
5. ✅ 对现有功能无影响（可通过环境变量禁用）

---

**更新日期**: 2025-10-25  
**版本**: v1.0  
**下一步**: 实现代码并验证效果


