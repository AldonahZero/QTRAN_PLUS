#!/usr/bin/env python3
"""
清理bugs.json中的噪音数据

- 移除test字段中的日志、堆栈跟踪等无关内容
- 保留纯净的SQL语句
- 备份原文件
"""

import json
import re
import shutil
from pathlib import Path


def is_noise_line(line: str) -> bool:
    """判断是否是噪音行"""
    if not line or len(line.strip()) == 0:
        return True
    
    line = line.strip()
    
    # 噪音模式
    noise_patterns = [
        r'^\[.*?\]',  # [timestamp]
        r'^\d{4}[.-]\d{2}[.-]\d{2}',  # 日期
        r'^<(Fatal|Error|Warning|Info|Debug|Trace)>',  # 日志级别
        r'^(Stack trace|Fatal|Error|Warning):',  # 错误提示
        r'^\d+\.\s+.*?@\s+0x[0-9a-f]+',  # 堆栈跟踪
        r'^\d+\.\s+│',  # 表格行号
        r'^Query id:',  # 查询ID
        r'^[┏┓┃┗┛┡┩━─│]+$',  # 表格边框
        r'^│[↳↴]',  # 表格标记
        r'^\(.*?,.*?,.*?,.*?,.*?\)$',  # 数据元组（5个以上逗号）
        r'^FORMAT\s+(Pretty|Values|JSON)\s*$',  # FORMAT单独行
        r'^\s*[\(\)]+\s*$',  # 只有括号
        r'^###\s+',  # Markdown标题
        r'^Company or project name',  # GitHub issue模板
    ]
    
    for pattern in noise_patterns:
        if re.match(pattern, line, re.IGNORECASE):
            return True
    
    # 过滤数据行（大量逗号但不是SQL）
    if line.count(',') > 10 and not any(kw in line.upper() for kw in ['SELECT', 'INSERT', 'CREATE', 'VALUES']):
        return True
    
    # 过滤十六进制地址
    if line.count('0x') > 2:
        return True
    
    # 过滤很长的行（可能是日志）
    if len(line) > 500:
        return True
    
    return False


def looks_like_sql(line: str) -> bool:
    """判断是否像SQL"""
    if len(line) < 5:
        return False
    
    # SQL关键字
    sql_keywords = ['SELECT', 'CREATE', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 
                    'WITH', 'FROM', 'WHERE', 'ORDER', 'GROUP', 'HAVING', 'LIMIT']
    
    line_upper = line.upper()
    
    # 必须包含至少一个SQL关键字
    if not any(kw in line_upper for kw in sql_keywords):
        return False
    
    # SQL通常包含这些字符
    sql_chars = ['(', ')', ';', ',', '=']
    if not any(c in line for c in sql_chars):
        return False
    
    return True


def clean_test_array(test_array):
    """清理test数组"""
    if not test_array:
        return None
    
    cleaned = []
    for line in test_array:
        line = line.strip()
        
        # 跳过噪音
        if is_noise_line(line):
            continue
        
        # 只保留看起来像SQL的行
        if looks_like_sql(line):
            cleaned.append(line)
        
        # 最多保留10条
        if len(cleaned) >= 10:
            break
    
    return cleaned if cleaned else None


def clean_comment(comment):
    """清理comment字段"""
    if not comment:
        return None
    
    # 移除GitHub模板文本
    if 'Company or project name' in comment:
        return None
    
    # 移除Markdown标题
    comment = re.sub(r'^###\s+.*?\n', '', comment, flags=re.MULTILINE)
    
    # 截断过长的comment
    if len(comment) > 300:
        comment = comment[:300] + "..."
    
    return comment.strip() if comment.strip() else None


def clean_bugs_file(input_file="bugs.json", output_file=None, backup=True):
    """清理bugs文件"""
    input_path = Path(input_file)
    
    if not input_path.exists():
        print(f"❌ 文件不存在: {input_file}")
        return
    
    # 备份
    if backup:
        backup_file = input_path.with_suffix('.json.backup.dirty')
        shutil.copy2(input_path, backup_file)
        print(f"💾 备份到: {backup_file}")
    
    # 读取
    print(f"📖 读取: {input_file}")
    with open(input_path, 'r', encoding='utf-8') as f:
        bugs = json.load(f)
    
    print(f"📊 原始bug数: {len(bugs)}")
    
    # 清理
    cleaned_count = 0
    removed_test_count = 0
    removed_comment_count = 0
    
    for bug in bugs:
        original_test = bug.get('test')
        original_comment = bug.get('comment')
        
        # 清理test
        if original_test:
            cleaned_test = clean_test_array(original_test)
            if cleaned_test != original_test:
                cleaned_count += 1
                if cleaned_test:
                    bug['test'] = cleaned_test
                else:
                    bug.pop('test', None)
                    removed_test_count += 1
        
        # 清理comment
        if original_comment:
            cleaned_comment = clean_comment(original_comment)
            if cleaned_comment != original_comment:
                if cleaned_comment:
                    bug['comment'] = cleaned_comment
                else:
                    bug.pop('comment', None)
                    removed_comment_count += 1
    
    # 保存
    output_path = Path(output_file) if output_file else input_path
    print(f"💾 保存到: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(bugs, f, indent=4, ensure_ascii=False)
    
    # 统计
    print("\n" + "=" * 60)
    print("📊 清理统计:")
    print("=" * 60)
    print(f"  总bug数:            {len(bugs)}")
    print(f"  清理的bug数:        {cleaned_count}")
    print(f"  移除test的bug数:    {removed_test_count}")
    print(f"  移除comment的bug数: {removed_comment_count}")
    print("=" * 60)
    
    # 示例
    print("\n🔍 清理后的示例bug:")
    for i, bug in enumerate(bugs[:3], 1):
        print(f"\n  Bug #{i}: {bug['title'][:60]}...")
        if bug.get('test'):
            print(f"  ✅ SQL测试: {len(bug['test'])}条")
            for j, sql in enumerate(bug['test'][:2], 1):
                print(f"     {j}. {sql[:70]}...")
        else:
            print(f"  ⚠️  无SQL测试")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = "bugs.json"
    
    print("=" * 60)
    print("🧹 清理Bug数据")
    print("=" * 60)
    
    clean_bugs_file(input_file)
    
    print("\n✅ 清理完成!")

