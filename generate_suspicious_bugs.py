#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单独生成可疑 bug 报告
从 MutationLLM 的结果中提取 Oracle 检查失败的案例
"""

import sys
import os

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from TransferLLM.translate_sqlancer import getSuspicious

if __name__ == "__main__":
    input_file = "Input/bugs_real_relaxed.jsonl"
    
    print(f"正在为 {input_file} 生成可疑 bug 报告...")
    getSuspicious(input_filepath=input_file, tool="sqlancer")
    print("✅ 可疑 bug 报告已生成到: Output/bugs_real_relaxed/SuspiciousBugs")

