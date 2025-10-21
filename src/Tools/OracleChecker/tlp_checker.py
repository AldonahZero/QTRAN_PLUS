"""
TLP (Ternary Logic Partitioning) Oracle 检查器

专门用于验证 TLP 不变式: count(Q) == count(Q_true) + count(Q_false) + count(Q_null)
"""

from typing import Dict, List, Any, Optional


def convert_result_to_count(result: Any) -> int:
    """
    将查询结果转换为计数值
    
    对于 TLP Oracle,我们只关心文档数量,不关心具体内容
    
    Args:
        result: 查询结果,可能是:
            - None (findOne 未找到)
            - dict (findOne 找到单个文档)
            - list (find 找到多个文档)
            - dict with type field (NoSQL 统一格式)
    
    Returns:
        文档计数 (0 或正整数)
    """
    # Case 1: None → 0 (未找到文档)
    if result is None:
        return 0
    
    # Case 2: 统一的 NoSQL 结果格式 {type: ..., value: ...}
    if isinstance(result, dict) and "type" in result and "value" in result:
        value = result.get("value")
        
        # value 是 None → 0
        if value is None:
            return 0
        
        # value 是 list → len(list)
        if isinstance(value, list):
            return len(value)
        
        # value 是 dict (单个文档) → 1
        if isinstance(value, dict):
            return 1
        
        # value 是标量 → 1
        return 1
    
    # Case 3: dict (单个文档) → 1
    if isinstance(result, dict):
        return 1
    
    # Case 4: list (多个文档) → len(list)
    if isinstance(result, list):
        return len(result)
    
    # Case 5: 其他标量值 → 1
    return 1


def check_tlp_oracle(mutations_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    验证 TLP 不变式
    
    Args:
        mutations_results: 包含 4 个变异结果的列表
            - mutations_results[0]: 原始查询 (category: "original")
            - mutations_results[1]: P=true 分区 (category: "tlp_true")
            - mutations_results[2]: P=false 分区 (category: "tlp_false")
            - mutations_results[3]: P=null 分区 (category: "tlp_null")
    
    Returns:
        Oracle 检查结果:
        {
            "end": True/False,  # True 表示通过,False 表示发现 Bug
            "error": str/None,  # 错误信息
            "bug_type": str,    # 如果有 Bug,说明 Bug 类型
            "details": {...}    # 详细信息
        }
    """
    # 提取各分区的执行结果
    try:
        # 原始查询结果
        original_result = mutations_results[0].get("MutateSqlExecResult")
        if isinstance(original_result, str):
            # 如果是字符串,尝试 eval
            import ast
            original_result = ast.literal_eval(original_result)
        
        # 三个分区的结果
        tlp_true_result = mutations_results[1].get("MutateSqlExecResult") if len(mutations_results) > 1 else None
        if isinstance(tlp_true_result, str):
            tlp_true_result = ast.literal_eval(tlp_true_result)
        
        tlp_false_result = mutations_results[2].get("MutateSqlExecResult") if len(mutations_results) > 2 else None
        if isinstance(tlp_false_result, str):
            tlp_false_result = ast.literal_eval(tlp_false_result)
        
        tlp_null_result = mutations_results[3].get("MutateSqlExecResult") if len(mutations_results) > 3 else None
        if isinstance(tlp_null_result, str):
            tlp_null_result = ast.literal_eval(tlp_null_result)
    
    except Exception as e:
        return {
            "end": False,
            "error": f"Failed to parse mutation results: {str(e)}",
            "bug_type": "parse_error",
            "details": {}
        }
    
    # 转换为计数
    count_original = convert_result_to_count(original_result)
    count_true = convert_result_to_count(tlp_true_result)
    count_false = convert_result_to_count(tlp_false_result)
    count_null = convert_result_to_count(tlp_null_result)
    
    count_partitions = count_true + count_false + count_null
    
    # TLP 不变式检查
    if count_original != count_partitions:
        return {
            "end": False,
            "error": None,
            "bug_type": "TLP_violation",
            "details": {
                "original_count": count_original,
                "tlp_true_count": count_true,
                "tlp_false_count": count_false,
                "tlp_null_count": count_null,
                "partition_sum": count_partitions,
                "difference": count_original - count_partitions,
                "explanation": f"TLP invariant violated: {count_original} ≠ {count_true} + {count_false} + {count_null}"
            }
        }
    
    # 检查分区是否互斥 (可选,需要实际文档 ID)
    # 由于我们只有计数,暂时跳过互斥检查
    
    # 通过检查
    return {
        "end": True,
        "error": None,
        "bug_type": None,
        "details": {
            "original_count": count_original,
            "tlp_true_count": count_true,
            "tlp_false_count": count_false,
            "tlp_null_count": count_null,
            "partition_sum": count_partitions,
            "explanation": f"TLP invariant holds: {count_original} == {count_true} + {count_false} + {count_null}"
        }
    }


def is_tlp_mutation(mutation_result: Dict[str, Any]) -> bool:
    """
    判断是否为 TLP 变异
    
    检查 MutateResult 中的 oracle 字段是否包含 tlp_partition 或 tlp_base
    """
    try:
        import json
        mutate_result_str = mutation_result.get("MutateResult", "{}")
        if isinstance(mutate_result_str, str):
            mutate_result = json.loads(mutate_result_str)
        else:
            mutate_result = mutate_result_str
        
        mutations = mutate_result.get("mutations", [])
        for mut in mutations:
            oracle = mut.get("oracle", "")
            if oracle in ["tlp_base", "tlp_partition"]:
                return True
        return False
    except Exception:
        return False


# 示例用法
if __name__ == "__main__":
    # 模拟 TLP 变异结果
    example_results = [
        {
            "MutateResult": '{"mutations":[{"oracle":"tlp_base"}]}',
            "MutateSqlExecResult": "{'type': 'findOne', 'value': {'_id': 'counter', 'value': 2}}"
        },
        {
            "MutateResult": '{"mutations":[{"oracle":"tlp_partition"}]}',
            "MutateSqlExecResult": "{'type': 'findOne', 'value': {'_id': 'counter', 'value': 2}}"
        },
        {
            "MutateResult": '{"mutations":[{"oracle":"tlp_partition"}]}',
            "MutateSqlExecResult": "{'type': 'findOne', 'value': None}"
        },
        {
            "MutateResult": '{"mutations":[{"oracle":"tlp_partition"}]}',
            "MutateSqlExecResult": "{'type': 'findOne', 'value': None}"
        }
    ]
    
    result = check_tlp_oracle(example_results)
    print("TLP Oracle Check Result:")
    print(f"  Passed: {result['end']}")
    print(f"  Bug Type: {result.get('bug_type', 'None')}")
    print(f"  Details: {result['details']}")
