#!/usr/bin/env python3
"""
Bug数据统计脚本
"""

import json
from collections import Counter
from datetime import datetime


def analyze_bugs(filename="bugs.json"):
    """分析bugs.json的统计信息"""
    
    with open(filename, 'r', encoding='utf-8') as f:
        bugs = json.load(f)
    
    print("=" * 70)
    print("📊 Bug数据集统计分析")
    print("=" * 70)
    
    # 基本统计
    print(f"\n总bug数量: {len(bugs)}")
    
    # 按数据库分类
    dbms_counter = Counter(bug.get('dbms', 'Unknown') for bug in bugs)
    print("\n📁 数据库分布:")
    for dbms, count in dbms_counter.most_common():
        percentage = count / len(bugs) * 100
        bar = "█" * int(percentage / 2)
        print(f"  {dbms:15s} {count:5d} ({percentage:5.1f}%) {bar}")
    
    # 按Oracle类型分类
    oracle_counter = Counter(bug.get('oracle', 'Unknown') for bug in bugs)
    print("\n🔍 Oracle类型分布:")
    for oracle, count in oracle_counter.most_common():
        percentage = count / len(bugs) * 100
        print(f"  {oracle:15s} {count:5d} ({percentage:5.1f}%)")
    
    # 按状态分类
    status_counter = Counter(bug.get('status', 'Unknown') for bug in bugs)
    print("\n📌 Bug状态分布:")
    for status, count in status_counter.most_common():
        percentage = count / len(bugs) * 100
        print(f"  {status:20s} {count:5d} ({percentage:5.1f}%)")
    
    # 按Reporter分类（Top 10）
    reporter_counter = Counter(bug.get('reporter', 'Unknown') for bug in bugs)
    print("\n👤 Top 10 Reporter:")
    for reporter, count in reporter_counter.most_common(10):
        percentage = count / len(bugs) * 100
        print(f"  {reporter:25s} {count:5d} ({percentage:5.1f}%)")
    
    # 时间分析
    print("\n📅 时间范围:")
    dates = []
    for bug in bugs:
        date_str = bug.get('date', '')
        try:
            # 解析日期 DD/MM/YYYY
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    day, month, year = parts
                    dates.append(f"{year}-{month.zfill(2)}-{day.zfill(2)}")
        except:
            pass
    
    if dates:
        dates.sort()
        print(f"  最早: {dates[0]}")
        print(f"  最新: {dates[-1]}")
        
        # 按年份统计
        year_counter = Counter(d[:4] for d in dates)
        print("\n📆 按年份分布:")
        for year in sorted(year_counter.keys()):
            count = year_counter[year]
            bar = "▓" * (count // 50)
            print(f"  {year}: {count:4d} {bar}")
    
    # 包含SQL测试的比例
    with_sql = sum(1 for bug in bugs if bug.get('test'))
    print(f"\n🔬 包含SQL测试用例: {with_sql}/{len(bugs)} ({with_sql/len(bugs)*100:.1f}%)")
    
    # 包含评论的比例
    with_comment = sum(1 for bug in bugs if bug.get('comment'))
    print(f"💬 包含评论说明: {with_comment}/{len(bugs)} ({with_comment/len(bugs)*100:.1f}%)")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    analyze_bugs()

