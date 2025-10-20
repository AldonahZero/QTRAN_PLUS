#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSONL 文件拆分工具

功能：将单个 JSONL 文件按 index 字段拆分到目录中，每个 index 对应一个单独的 JSONL 文件。

用法：
    python split_jsonl_to_directory.py <input_jsonl_path>
    
示例：
    python split_jsonl_to_directory.py Input/demo1.jsonl
    # 将创建 Input/demo1/ 目录，包含 0.jsonl, 1.jsonl 等文件

输入：
    - input_jsonl_path: 输入的 JSONL 文件路径（如 Input/demo1.jsonl）

输出：
    - 创建与输入文件同名的目录（去掉 .jsonl 后缀）
    - 目录中每个 JSON 记录按其 index 字段保存为单独的 JSONL 文件
    - 如果记录没有 index 字段，使用行号作为文件名

注意：
    - 如果目标目录已存在，会清空后重新创建
    - 支持相对路径和绝对路径
"""

import json
import os
import sys
from pathlib import Path
import shutil


def split_jsonl_to_directory(input_file: str, output_dir: str = None, verbose: bool = True):
    """
    将 JSONL 文件按 index 拆分到目录中。
    
    参数：
        input_file: 输入的 JSONL 文件路径
        output_dir: 输出目录路径（默认为输入文件名去掉 .jsonl 后缀）
        verbose: 是否打印详细信息
    
    返回：
        创建的文件数量
    """
    input_path = Path(input_file)
    
    # 检查输入文件是否存在
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_file}")
    
    if not input_path.is_file():
        raise ValueError(f"输入路径不是文件: {input_file}")
    
    # 确定输出目录
    if output_dir is None:
        # 去掉 .jsonl 后缀作为目录名
        if input_path.suffix.lower() == '.jsonl':
            output_dir = str(input_path.with_suffix(''))
        else:
            output_dir = str(input_path) + '_split'
    
    output_path = Path(output_dir)
    
    # 如果输出目录已存在，清空它
    if output_path.exists():
        if verbose:
            print(f"输出目录已存在，清空: {output_path}")
        shutil.rmtree(output_path)
    
    # 创建输出目录
    output_path.mkdir(parents=True, exist_ok=True)
    if verbose:
        print(f"创建输出目录: {output_path}")
    
    # 读取并拆分 JSONL 文件
    file_count = 0
    line_number = 0
    
    with open(input_path, 'r', encoding='utf-8') as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"警告: 第 {line_number} 行 JSON 解析失败: {e}")
                continue
            
            # 获取 index 字段，如果没有则使用行号
            if 'index' in record:
                index = record['index']
            else:
                index = line_number - 1  # 从 0 开始编号
                if verbose:
                    print(f"警告: 第 {line_number} 行缺少 'index' 字段，使用行号 {index}")
            
            # 构造输出文件路径
            output_file = output_path / f"{index}.jsonl"
            
            # 写入单行 JSONL 文件
            with open(output_file, 'w', encoding='utf-8') as out_f:
                json.dump(record, out_f, ensure_ascii=False)
                out_f.write('\n')
            
            file_count += 1
            
            if verbose and file_count % 10 == 0:
                print(f"已处理 {file_count} 条记录...")
    
    if verbose:
        print(f"\n完成! 共创建 {file_count} 个文件到目录: {output_path}")
        print(f"输入文件: {input_path}")
        print(f"输出目录: {output_path}")
    
    return file_count


def main():
    """命令行入口"""
    if len(sys.argv) < 2:
        print("用法: python split_jsonl_to_directory.py <input_jsonl_path> [output_dir]")
        print("\n示例:")
        print("  python split_jsonl_to_directory.py Input/demo1.jsonl")
        print("  python split_jsonl_to_directory.py Input/demo1.jsonl Input/demo1_output")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        file_count = split_jsonl_to_directory(input_file, output_dir, verbose=True)
        print(f"\n✓ 成功拆分 {file_count} 个记录")
    except Exception as e:
        print(f"\n✗ 错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
