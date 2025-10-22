"""
TLP (Ternary Logic Partitioning) Oracle 检查器

专门用于验证 TLP 不变式: count(Q) == count(Q_true) + count(Q_false) + count(Q_null)
"""

from typing import Dict, List, Any, Optional
import json
from src.Tools.json_utils import safe_parse_result


def convert_result_to_count(result: Any) -> int:
    """
    将查询结果转换为计数值

    对于 TLP Oracle,我们只关心文档数量,不关心具体内容
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
        Oracle 检查结果字典
    """
    try:
        # 原始查询结果
        original_result = None
        if len(mutations_results) > 0:
            original_raw = mutations_results[0].get("MutateSqlExecResult")
            original_result = safe_parse_result(original_raw)

        # 三个分区的结果
        tlp_true_result = None
        if len(mutations_results) > 1:
            tlp_true_raw = mutations_results[1].get("MutateSqlExecResult")
            tlp_true_result = safe_parse_result(tlp_true_raw)

        tlp_false_result = None
        if len(mutations_results) > 2:
            tlp_false_raw = mutations_results[2].get("MutateSqlExecResult")
            tlp_false_result = safe_parse_result(tlp_false_raw)

        tlp_null_result = None
        if len(mutations_results) > 3:
            tlp_null_raw = mutations_results[3].get("MutateSqlExecResult")
            tlp_null_result = safe_parse_result(tlp_null_raw)

    except Exception as e:
        # 尽可能将出错时的原始 payload 和异常信息返还到 details 中，便于调查
        try:
            payload_sample = {
                "mutations_results_len": len(mutations_results),
                "mutations_results": mutations_results,
            }
        except Exception:
            payload_sample = {"mutations_results_repr": repr(mutations_results)}

        return {
            "end": False,
            "error": f"Failed to parse mutation results: {str(e)}",
            "bug_type": "parse_error",
            "details": {"payload": payload_sample, "exception": repr(e)},
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
                "explanation": f"TLP invariant violated: {count_original} ≠ {count_true} + {count_false} + {count_null}",
            },
        }

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
            "explanation": f"TLP invariant holds: {count_original} == {count_true} + {count_false} + {count_null}",
        },
    }


def is_tlp_mutation(mutation_result: Dict[str, Any]) -> bool:
    """
    判断是否为 TLP 变异

    检查 MutateResult 中的 oracle 字段是否包含 tlp_partition 或 tlp_base
    """
    try:
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
            "MutateSqlExecResult": "{'type': 'findOne', 'value': {'_id': 'counter', 'value': 2}}",
        },
        {
            "MutateResult": '{"mutations":[{"oracle":"tlp_partition"}]}',
            "MutateSqlExecResult": "{'type': 'findOne', 'value': {'_id': 'counter', 'value': 2}}",
        },
        {
            "MutateResult": '{"mutations":[{"oracle":"tlp_partition"}]}',
            "MutateSqlExecResult": "{'type': 'findOne', 'value': None}",
        },
        {
            "MutateResult": '{"mutations":[{"oracle":"tlp_partition"}]}',
            "MutateSqlExecResult": "{'type': 'findOne', 'value': None}",
        },
    ]

    result = check_tlp_oracle(example_results)
    print("TLP Oracle Check Result:")
    print(f"  Passed: {result['end']}")
    print(f"  Bug Type: {result.get('bug_type', 'None')}")
    print(f"  Details: {result['details']}")
