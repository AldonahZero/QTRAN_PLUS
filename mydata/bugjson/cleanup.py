#!/usr/bin/env python3
"""
整理文件 - 只保留最重要的文件
"""

import os
import shutil
from pathlib import Path

# 要保留的文件
KEEP_FILES = {
    # 原始数据
    'bugs.json',
    
    # 核心代码
    'demo.py',
    'bugs.py',
    'multi_source_crawler.py',  # 最强的爬虫
    
    # 工具脚本
    'stats.py',
    'clean_bugs.py',
    'merge_multi_db.py',
    
    # 配置文件
    'crawler_config.py',
    
    # 文档
    'README.md',
    'QUICKSTART.md',
    '使用指南.md',
    '多数据库爬取说明.md',
}

def cleanup():
    """清理文件"""
    
    print("=" * 70)
    print("🧹 整理文件")
    print("=" * 70)
    
    # 1. 重命名bugs_ultimate.json为bugs_new.json
    if os.path.exists('bugs_ultimate.json'):
        print("\n📝 重命名最终数据集...")
        shutil.copy2('bugs_ultimate.json', 'bugs_new.json')
        print("  ✅ bugs_ultimate.json -> bugs_new.json")
        KEEP_FILES.add('bugs_new.json')
    
    # 2. 获取所有文件
    all_files = []
    for ext in ['*.json', '*.py', '*.md']:
        all_files.extend(Path('.').glob(ext))
    
    # 3. 删除不需要的文件
    print("\n🗑️  删除中间文件...")
    deleted_count = 0
    for file_path in all_files:
        filename = file_path.name
        if filename not in KEEP_FILES and not filename.startswith('.'):
            try:
                file_path.unlink()
                print(f"  ❌ 删除: {filename}")
                deleted_count += 1
            except Exception as e:
                print(f"  ⚠️  无法删除 {filename}: {e}")
    
    # 4. 统计保留的文件
    print(f"\n✅ 保留的文件:")
    kept_files = sorted([f for f in KEEP_FILES if os.path.exists(f)])
    
    print("\n📊 数据文件:")
    data_files = [f for f in kept_files if f.endswith('.json')]
    for f in data_files:
        size = os.path.getsize(f) / 1024
        print(f"  ✅ {f:25s} ({size:7.1f} KB)")
    
    print("\n🐍 Python脚本:")
    py_files = [f for f in kept_files if f.endswith('.py')]
    for f in py_files:
        size = os.path.getsize(f) / 1024
        print(f"  ✅ {f:25s} ({size:7.1f} KB)")
    
    print("\n📖 文档文件:")
    doc_files = [f for f in kept_files if f.endswith('.md')]
    for f in doc_files:
        size = os.path.getsize(f) / 1024
        print(f"  ✅ {f:25s} ({size:7.1f} KB)")
    
    print("\n" + "=" * 70)
    print("📊 统计:")
    print("=" * 70)
    print(f"  保留文件: {len(kept_files)} 个")
    print(f"  删除文件: {deleted_count} 个")
    print("=" * 70)
    
    print("\n✅ 整理完成!")
    print("\n📁 保留的核心文件:")
    print("  数据:")
    print("    - bugs.json      : 原始数据 (2019-2020)")
    print("    - bugs_new.json  : 完整数据 (2019-2025)")
    print("  代码:")
    print("    - demo.py                  : 演示脚本")
    print("    - bugs.py                  : 工具脚本")
    print("    - multi_source_crawler.py  : 最强爬虫（多源）")
    print("  工具:")
    print("    - stats.py                 : 统计分析")
    print("    - clean_bugs.py            : 数据清理")
    print("    - merge_multi_db.py        : 数据合并")


if __name__ == "__main__":
    cleanup()

