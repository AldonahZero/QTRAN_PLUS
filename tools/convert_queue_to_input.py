#!/usr/bin/env python3
"""
将 sync_dir 下所有 queue 文件夹中的 Redis 查询转换为项目的 Input 格式 (JSONL)

功能:
- 扫描所有 queue 文件夹
- 读取每个文件中的 Redis 命令
- 按照项目 Input 格式生成 JSONL 文件
- 支持指定目标数据库和变异策略

使用方法:
    python convert_queue_to_input.py [--output OUTPUT_FILE] [--target-db TARGET_DB] [--strategy STRATEGY]
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Set


def find_all_queue_dirs(base_dir: str = ".") -> List[Path]:
    """查找所有 queue 目录"""
    queue_dirs = []
    base_path = Path(base_dir)

    print(f"正在扫描 {base_path.absolute()} 下的 queue 目录...")

    for queue_dir in base_path.rglob("queue"):
        if queue_dir.is_dir():
            queue_dirs.append(queue_dir)

    return sorted(queue_dirs)


def read_redis_commands_from_file(file_path: Path) -> List[str]:
    """从文件中读取 Redis 命令（每行一个命令）"""
    commands = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):  # 跳过空行和注释
                    # 确保命令以分号结尾
                    if not line.endswith(";"):
                        line += ";"
                    commands.append(line)
    except Exception as e:
        print(f"  ⚠️  读取文件失败 {file_path}: {e}")
    return commands


def collect_commands_from_queue(queue_dir: Path, max_files: int = None) -> List[str]:
    """从 queue 目录收集所有命令"""
    all_commands = []
    files = sorted(queue_dir.iterdir())

    if max_files:
        files = files[:max_files]

    for file_path in files:
        if file_path.is_file():
            commands = read_redis_commands_from_file(file_path)
            all_commands.extend(commands)

    return all_commands


def create_input_entry(
    index: int,
    commands: List[str],
    target_db: str = "mongodb",
    strategy: str = "semantic",
) -> Dict:
    """创建符合项目 Input 格式的 JSON 条目"""
    return {
        "index": index,
        "a_db": "redis",
        "b_db": target_db,
        "molt": strategy,
        "sqls": commands,
    }


def convert_queues_to_input(
    base_dir: str = ".",
    output_file: str = "Input/queue_converted.jsonl",
    target_db: str = "mongodb",
    strategy: str = "semantic",
    max_commands_per_entry: int = 500,
    max_files_per_queue: int = None,
):
    """
    转换所有 queue 目录到 Input 格式

    参数:
        base_dir: 搜索 queue 的根目录
        output_file: 输出的 JSONL 文件路径
        target_db: 目标数据库 (mongodb, clickhouse, duckdb 等)
        strategy: 变异策略 (semantic, dqe, norec, tlp, pinolo)
        max_commands_per_entry: 每个 JSON 条目最多包含的命令数
        max_files_per_queue: 每个 queue 最多读取的文件数（None 表示全部）
    """

    print("=" * 70)
    print("Queue 目录 -> Input 格式转换工具")
    print("=" * 70)
    print(f"基础目录: {base_dir}")
    print(f"目标数据库: {target_db}")
    print(f"变异策略: {strategy}")
    print(f"输出文件: {output_file}")
    print(f"每条最多命令数: {max_commands_per_entry}")
    if max_files_per_queue:
        print(f"每个 queue 最多文件数: {max_files_per_queue}")
    print("=" * 70)
    print()

    # 查找所有 queue 目录
    queue_dirs = find_all_queue_dirs(base_dir)

    if not queue_dirs:
        print("❌ 未找到任何 queue 目录")
        return False

    print(f"✅ 找到 {len(queue_dirs)} 个 queue 目录\n")

    # 收集所有命令
    all_entries = []
    total_commands = 0
    entry_index = 0

    for queue_dir in queue_dirs:
        print(f"处理: {queue_dir}")

        # 收集该 queue 的所有命令
        commands = collect_commands_from_queue(queue_dir, max_files_per_queue)

        if not commands:
            print(f"  ⚠️  该目录无有效命令，跳过")
            continue

        print(f"  ✅ 收集了 {len(commands)} 个命令")
        total_commands += len(commands)

        # 将命令分批（如果超过最大限制）
        for i in range(0, len(commands), max_commands_per_entry):
            batch_commands = commands[i : i + max_commands_per_entry]
            entry = create_input_entry(
                index=entry_index,
                commands=batch_commands,
                target_db=target_db,
                strategy=strategy,
            )
            all_entries.append(entry)
            entry_index += 1

    if not all_entries:
        print("\n❌ 没有生成任何条目")
        return False

    # 写入输出文件
    print(f"\n正在写入输出文件: {output_file}")
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for entry in all_entries:
                json_line = json.dumps(entry, ensure_ascii=False)
                f.write(json_line + "\n")

        print(f"✅ 成功写入 {len(all_entries)} 个条目")
        print(f"✅ 总共 {total_commands} 个命令")
        print(f"✅ 输出文件: {output_path.absolute()}")

        # 显示统计
        print("\n" + "=" * 70)
        print("转换统计:")
        print(f"  - Queue 目录数: {len(queue_dirs)}")
        print(f"  - 生成条目数: {len(all_entries)}")
        print(f"  - 总命令数: {total_commands}")
        print(f"  - 平均每条命令数: {total_commands / len(all_entries):.1f}")
        print("=" * 70)

        return True

    except Exception as e:
        print(f"❌ 写入文件失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="将 queue 文件夹中的 Redis 命令转换为项目 Input 格式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 转换为 MongoDB 格式（默认）
  python convert_queue_to_input.py
  
  # 指定输出文件和目标数据库
  python convert_queue_to_input.py --output Input/my_redis_queries.jsonl --target-db clickhouse
  
  # 指定变异策略
  python convert_queue_to_input.py --strategy dqe --target-db duckdb
  
  # 限制每个条目的命令数
  python convert_queue_to_input.py --max-commands 100
  
  # 限制每个 queue 读取的文件数
  python convert_queue_to_input.py --max-files 50
""",
    )

    parser.add_argument(
        "--base-dir", default=".", help="搜索 queue 的根目录（默认: 当前目录）"
    )

    parser.add_argument(
        "--output",
        "-o",
        default="Input/queue_converted.jsonl",
        help="输出的 JSONL 文件路径（默认: Input/queue_converted.jsonl）",
    )

    parser.add_argument(
        "--target-db",
        "-t",
        default="mongodb",
        choices=[
            "mongodb",
            "clickhouse",
            "duckdb",
            "mysql",
            "postgres",
            "mariadb",
            "tidb",
            "monetdb",
        ],
        help="目标数据库（默认: mongodb）",
    )

    parser.add_argument(
        "--strategy",
        "-s",
        default="semantic",
        choices=["semantic", "dqe", "norec", "tlp", "pinolo"],
        help="变异策略（默认: semantic）",
    )

    parser.add_argument(
        "--max-commands",
        type=int,
        default=500,
        help="每个 JSON 条目最多包含的命令数（默认: 500）",
    )

    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="每个 queue 最多读取的文件数（默认: 全部）",
    )

    args = parser.parse_args()

    success = convert_queues_to_input(
        base_dir=args.base_dir,
        output_file=args.output,
        target_db=args.target_db,
        strategy=args.strategy,
        max_commands_per_entry=args.max_commands,
        max_files_per_queue=args.max_files,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
