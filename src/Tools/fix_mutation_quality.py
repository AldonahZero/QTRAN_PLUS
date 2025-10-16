#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复和验证 MongoDB 变异产物质量

功能:
1. 检测不合格的变异命令(非 MongoDB JSON 格式)
2. 提供格式转换建议
3. 重新运行变异生成(可选)
4. 生成质量报告
"""

import json
import os
import re
from typing import Dict, List, Tuple
from collections import Counter


def is_valid_mongodb_json(cmd: str) -> Tuple[bool, str]:
    """
    检查命令是否是有效的 MongoDB JSON 格式

    返回: (是否有效, 错误原因)
    """
    try:
        parsed = json.loads(cmd)
        if not isinstance(parsed, dict):
            return False, "Not a JSON object"

        if "op" not in parsed:
            return False, "Missing 'op' field"

        valid_ops = [
            "findOne",
            "find",
            "updateOne",
            "updateMany",
            "insertOne",
            "deleteOne",
            "countDocuments",
        ]
        if parsed["op"] not in valid_ops:
            return False, f"Invalid op: {parsed['op']}"

        if "collection" not in parsed:
            return False, "Missing 'collection' field"

        return True, ""
    except json.JSONDecodeError as e:
        return False, f"JSON parse error: {str(e)}"
    except Exception as e:
        return False, f"Validation error: {str(e)}"


def detect_simple_command_pattern(cmd: str) -> bool:
    """
    检测是否是简化伪命令格式 (如 "find kv", "delete kv")
    """
    simple_patterns = [
        r"^find\s+\w+",
        r"^count\s+\w+",
        r"^insert\s+\w+",
        r"^delete\s+\w+",
        r"^update\s+\w+",
    ]
    return any(re.match(pattern, cmd.strip()) for pattern in simple_patterns)


def analyze_mutation_quality(jsonl_file: str) -> Dict:
    """
    分析单个 JSONL 文件中的变异质量
    """
    report = {
        "file": os.path.basename(jsonl_file),
        "total_records": 0,
        "records_with_mutations": 0,
        "total_mutations": 0,
        "valid_mutations": 0,
        "invalid_mutations": 0,
        "simple_command_count": 0,
        "json_parse_errors": 0,
        "missing_fields_count": 0,
        "invalid_ops_count": 0,
        "issues": [],
    }

    try:
        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue

                try:
                    record = json.loads(line)
                    report["total_records"] += 1

                    mutate_result = record.get("MutateResult")
                    if not mutate_result:
                        continue

                    # 尝试解析 MutateResult
                    if isinstance(mutate_result, str):
                        try:
                            mutate_data = json.loads(mutate_result)
                        except json.JSONDecodeError:
                            report["issues"].append(
                                {
                                    "line": line_num,
                                    "index": record.get("index"),
                                    "type": "MutateResult parse error",
                                    "detail": "Cannot parse MutateResult as JSON",
                                }
                            )
                            continue
                    else:
                        mutate_data = mutate_result

                    mutations = mutate_data.get("mutations", [])
                    if not mutations:
                        continue

                    report["records_with_mutations"] += 1

                    for mut_idx, mutation in enumerate(mutations):
                        report["total_mutations"] += 1
                        cmd = mutation.get("cmd", "")

                        # 检测简化命令
                        if detect_simple_command_pattern(cmd):
                            report["simple_command_count"] += 1
                            report["invalid_mutations"] += 1
                            report["issues"].append(
                                {
                                    "line": line_num,
                                    "index": record.get("index"),
                                    "mutation_idx": mut_idx,
                                    "type": "simple_command",
                                    "cmd": cmd,
                                    "detail": "Uses simplified pseudo-command instead of MongoDB JSON",
                                }
                            )
                            continue

                        # 验证 MongoDB JSON 格式
                        is_valid, error = is_valid_mongodb_json(cmd)
                        if is_valid:
                            report["valid_mutations"] += 1
                        else:
                            report["invalid_mutations"] += 1

                            if "JSON parse error" in error:
                                report["json_parse_errors"] += 1
                            elif "Missing" in error:
                                report["missing_fields_count"] += 1
                            elif "Invalid op" in error:
                                report["invalid_ops_count"] += 1

                            report["issues"].append(
                                {
                                    "line": line_num,
                                    "index": record.get("index"),
                                    "mutation_idx": mut_idx,
                                    "type": "invalid_mongodb_json",
                                    "cmd": cmd[:100]
                                    + ("..." if len(cmd) > 100 else ""),
                                    "detail": error,
                                }
                            )

                except json.JSONDecodeError as e:
                    report["issues"].append(
                        {
                            "line": line_num,
                            "type": "line_parse_error",
                            "detail": f"Cannot parse line: {str(e)}",
                        }
                    )

    except FileNotFoundError:
        report["error"] = f"File not found: {jsonl_file}"

    return report


def analyze_directory(dir_path: str) -> Dict:
    """
    分析整个目录中的变异质量
    """
    all_reports = []
    summary = {
        "directory": dir_path,
        "total_files": 0,
        "total_records": 0,
        "total_mutations": 0,
        "valid_mutations": 0,
        "invalid_mutations": 0,
        "quality_rate": 0.0,
        "error_breakdown": Counter(),
        "files": [],
    }

    if not os.path.isdir(dir_path):
        summary["error"] = f"Directory not found: {dir_path}"
        return summary

    for fname in os.listdir(dir_path):
        if not fname.endswith(".jsonl"):
            continue

        fpath = os.path.join(dir_path, fname)
        report = analyze_mutation_quality(fpath)
        all_reports.append(report)

        summary["total_files"] += 1
        summary["total_records"] += report["total_records"]
        summary["total_mutations"] += report["total_mutations"]
        summary["valid_mutations"] += report["valid_mutations"]
        summary["invalid_mutations"] += report["invalid_mutations"]
        summary["error_breakdown"]["simple_command"] += report["simple_command_count"]
        summary["error_breakdown"]["json_parse"] += report["json_parse_errors"]
        summary["error_breakdown"]["missing_fields"] += report["missing_fields_count"]
        summary["error_breakdown"]["invalid_ops"] += report["invalid_ops_count"]

        summary["files"].append(
            {
                "name": fname,
                "total_mutations": report["total_mutations"],
                "valid_mutations": report["valid_mutations"],
                "invalid_mutations": report["invalid_mutations"],
                "quality_rate": (
                    (report["valid_mutations"] / report["total_mutations"] * 100)
                    if report["total_mutations"] > 0
                    else 0
                ),
            }
        )

    if summary["total_mutations"] > 0:
        summary["quality_rate"] = (
            summary["valid_mutations"] / summary["total_mutations"] * 100
        )

    summary["error_breakdown"] = dict(summary["error_breakdown"])
    return summary, all_reports


def generate_report(output_name: str, save_path: str = None):
    """
    生成质量报告并保存
    """
    base_dir = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "..", "Output", output_name, "MutationLLM"
        )
    )

    print(f"Analyzing: {base_dir}")
    summary, detailed_reports = analyze_directory(base_dir)

    # 打印摘要
    print("\n" + "=" * 70)
    print("MUTATION QUALITY REPORT")
    print("=" * 70)
    print(f"Directory: {summary['directory']}")
    print(f"Total Files: {summary['total_files']}")
    print(f"Total Records: {summary['total_records']}")
    print(f"Total Mutations: {summary['total_mutations']}")
    print(f"Valid Mutations: {summary['valid_mutations']}")
    print(f"Invalid Mutations: {summary['invalid_mutations']}")
    print(f"Quality Rate: {summary['quality_rate']:.2f}%")
    print("\nError Breakdown:")
    for error_type, count in summary["error_breakdown"].items():
        print(f"  - {error_type}: {count}")
    print("\nPer-File Quality:")
    for file_info in summary["files"]:
        print(
            f"  - {file_info['name']}: {file_info['quality_rate']:.1f}% "
            f"({file_info['valid_mutations']}/{file_info['total_mutations']})"
        )
    print("=" * 70)

    # 保存详细报告
    if save_path is None:
        save_path = os.path.join(
            os.path.dirname(base_dir), "mutation_quality_report.json"
        )

    full_report = {"summary": summary, "detailed_reports": detailed_reports}

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(full_report, f, ensure_ascii=False, indent=2)

    print(f"\nDetailed report saved to: {save_path}")

    # 显示前5个问题示例
    if detailed_reports and detailed_reports[0].get("issues"):
        print("\n" + "=" * 70)
        print("SAMPLE ISSUES (first 5):")
        print("=" * 70)
        issues = detailed_reports[0]["issues"][:5]
        for i, issue in enumerate(issues, 1):
            print(
                f"\n{i}. Line {issue.get('line', 'N/A')}, "
                f"Index {issue.get('index', 'N/A')}"
            )
            print(f"   Type: {issue['type']}")
            print(f"   Detail: {issue['detail']}")
            if "cmd" in issue:
                print(f"   Command: {issue['cmd'][:80]}...")

    return summary, detailed_reports


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python fix_mutation_quality.py <output_name>")
        print("Example: python fix_mutation_quality.py redis_demo_04")
        sys.exit(1)

    output_name = sys.argv[1]
    generate_report(output_name)
