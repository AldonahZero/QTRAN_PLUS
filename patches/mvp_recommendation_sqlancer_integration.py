#!/usr/bin/env python3
"""
MVP 反向反馈机制 - translate_sqlancer.py 集成补丁

使用说明:
1. 在 translate_sqlancer.py 文件末尾添加辅助函数
2. 在 Oracle 检查后调用 Recommendation 生成函数
"""

from typing import Dict, List, Any

# ============================================================
# 在 translate_sqlancer.py 文件末尾添加以下辅助函数
# ============================================================

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
        if bug_type == "TLP_violation":
            priority = 9
        elif bug_type == "NoREC_mismatch":
            priority = 8
        else:
            priority = 7
        
        # 生成建议
        try:
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
            
            print(f"🔥 Generated recommendation: prioritize {', '.join(features)} (Priority: {priority})")
        except Exception as e:
            print(f"⚠️ Failed to generate recommendation: {e}")


def _extract_sql_features(sql: str) -> List[str]:
    """
    从SQL中提取关键特性
    
    Returns:
        特性列表，如 ["HEX", "MIN", "COLLATE", "aggregate"]
    """
    features = []
    sql_upper = sql.upper()
    
    # 常见函数
    functions = [
        "HEX", "MIN", "MAX", "SUM", "AVG", "COUNT", "ABS", 
        "CONCAT", "SUBSTR", "SUBSTRING", "LENGTH", "UPPER", "LOWER",
        "ROUND", "FLOOR", "CEIL", "CAST", "COALESCE", "NULLIF"
    ]
    for func in functions:
        if f"{func}(" in sql_upper:
            features.append(func)
    
    # 特殊关键字
    keywords = [
        "COLLATE", "UNION", "INTERSECT", "EXCEPT", "JOIN", 
        "GROUP BY", "HAVING", "ORDER BY", "LIMIT", "OFFSET",
        "DISTINCT", "WHERE", "CASE WHEN"
    ]
    for kw in keywords:
        if kw in sql_upper:
            features.append(kw.replace(" ", "_"))
    
    # 聚合判断
    if any(agg in sql_upper for agg in ["MIN(", "MAX(", "SUM(", "AVG(", "COUNT("]):
        if "aggregate" not in features:
            features.append("aggregate")
    
    # JOIN 类型
    join_types = ["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN", "CROSS JOIN"]
    for jt in join_types:
        if jt in sql_upper:
            features.append(jt.replace(" ", "_"))
            break  # 只添加一次
    
    # MongoDB 特定操作符（如果SQL中包含）
    mongodb_ops = ["$and", "$or", "$not", "$exists", "$type", "$gte", "$lte", "$in", "$nin"]
    for op in mongodb_ops:
        if op in sql:
            features.append(op)
    
    # 去重并限制数量
    unique_features = list(dict.fromkeys(features))  # 保持顺序去重
    return unique_features[:5]  # 限制返回最多5个特性


# ============================================================
# 在 sqlancer_translate 函数中的 Oracle 检查后添加调用
# 找到 line 625 附近的 TLP Oracle 检查代码，修改为:
# ============================================================

"""
原代码:
    oracle_check_res = check_tlp_oracle(tlp_results)

修改为:
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
"""

# ============================================================
# 具体集成位置：在 translate_sqlancer.py 的 line 625 附近
# ============================================================

"""
完整的修改示例:

if is_tlp_mutation(mutate_results[-1]):
    try:
        # 为 TLP 准备变异结果列表
        tlp_results = []
        
        # ... 原有的结果组装代码 ...
        
        # 调用 TLP 检查器
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
else:
    # 非 TLP 变异的默认处理
    oracle_check_res = {"end": True}
"""

# ============================================================
# 可选：为 NoREC Oracle 也添加支持
# ============================================================

"""
如果你使用 NoREC Oracle，也可以在其检查后添加:

if is_norec_mutation(mutate_results[-1]):
    try:
        oracle_check_res = check_norec_oracle(norec_results)
        
        # 🔥 生成 Recommendation
        if use_mem0 and mem0_manager:
            _generate_recommendation_from_oracle(
                mem0_manager=mem0_manager,
                oracle_result=oracle_check_res,
                original_sql=sql_statement,
                origin_db=origin_db,
                target_db=target_db,
                oracle_type="norec"
            )
    except Exception as e:
        oracle_check_res = {"end": False, "error": str(e)}
"""

