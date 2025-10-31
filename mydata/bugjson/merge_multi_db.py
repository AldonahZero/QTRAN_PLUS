#!/usr/bin/env python3
"""
合并多数据库bugs到一个文件

自动查找所有 bugs_*_new.json 和 bugs_multi_source.json 文件，
合并到 bugs_new.json 中。
"""

import json
import shutil
import glob
from pathlib import Path
from collections import Counter
from datetime import datetime


def find_new_bug_files():
    """查找所有新爬取的bug文件"""
    patterns = [
        "bugs_*_new.json",
        "bugs_multi_source.json"
    ]
    
    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))
    
    return sorted(set(files))


def merge_bugs(
    main_file="bugs_new.json",
    new_files=None,
    backup=True
):
    """
    合并新爬取的bug文件到主文件
    
    Args:
        main_file: 主文件（bugs_new.json）
        new_files: 新文件列表（如果为None，自动查找）
        backup: 是否备份
    """
    
    print("=" * 70)
    print("🔄 合并新爬取的Bug数据")
    print("=" * 70)
    
    # 自动查找新文件
    if new_files is None:
        new_files = find_new_bug_files()
    
    if not new_files:
        print("❌ 未找到新的bug文件")
        print("💡 提示: 查找以下文件:")
        print("   - bugs_*_new.json")
        print("   - bugs_multi_source.json")
        return
    
    print(f"\n📂 找到 {len(new_files)} 个新文件:")
    for f in new_files:
        size = Path(f).stat().st_size / 1024
        print(f"   ✓ {f} ({size:.1f}KB)")
    
    # 检查主文件
    main_path = Path(main_file)
    
    if not main_path.exists():
        print(f"\n⚠️  主文件不存在: {main_file}")
        print(f"💡 将创建新文件")
        main_bugs = []
    else:
        # 备份
        if backup:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = main_path.with_suffix(f'.json.backup_{timestamp}')
            shutil.copy2(main_path, backup_file)
            print(f"\n💾 备份主文件到: {backup_file}")
        
        # 加载主文件
        print(f"\n📖 读取主文件...")
        with open(main_path, 'r', encoding='utf-8') as f:
            main_bugs = json.load(f)
        print(f"   ✅ {main_file}: {len(main_bugs)} 个bugs")
    
    
    # 统计原始数据
    if main_bugs:
        main_dbms = Counter(bug.get('database', bug.get('dbms', 'Unknown')) for bug in main_bugs)
        print(f"\n📊 主文件数据库分布:")
        for dbms, count in main_dbms.most_common(10):
            print(f"    {dbms:15s} {count:4d} 个")
    
    # 加载并合并所有新文件
    print(f"\n🔄 加载新文件...")
    all_new_bugs = []
    
    for new_file in new_files:
        try:
            with open(new_file, 'r', encoding='utf-8') as f:
                new_bugs = json.load(f)
            print(f"   ✅ {new_file}: {len(new_bugs)} 个bugs")
            all_new_bugs.extend(new_bugs)
        except Exception as e:
            print(f"   ❌ {new_file}: 读取失败 - {e}")
    
    print(f"\n📦 新数据总计: {len(all_new_bugs)} 个bugs")
    
    if not all_new_bugs:
        print("❌ 没有新数据需要合并")
        return
    
    # 统计新数据
    new_dbms = Counter(bug.get('database', bug.get('dbms', 'Unknown')) for bug in all_new_bugs)
    print(f"\n📊 新数据数据库分布:")
    for dbms, count in new_dbms.most_common():
        print(f"    {dbms:15s} {count:4d} 个")
    
    # 去重合并（使用多种去重策略）
    print(f"\n🔄 合并中...")
    
    # 构建已存在的标识集合
    existing_ids = set()
    existing_urls = set()
    existing_combos = set()  # (database, date, test前50字符)
    
    for bug in main_bugs:
        # ID去重
        bug_id = bug.get('id')
        if bug_id:
            existing_ids.add(bug_id)
        
        # URL去重
        url = bug.get('url') or bug.get('links', {}).get('bugreport', '')
        if url:
            existing_urls.add(url)
        
        # 组合去重
        db = bug.get('database', bug.get('dbms', ''))
        date = bug.get('date', '')
        test_val = bug.get('test', '')
        # test可能是字符串或列表
        if isinstance(test_val, list):
            test = ' '.join(test_val)[:50] if test_val else ''
        else:
            test = str(test_val)[:50] if test_val else ''
        if db and date and test:
            existing_combos.add((db, date, test))
    
    print(f"   已有ID数: {len(existing_ids)}")
    print(f"   已有URL数: {len(existing_urls)}")
    
    added = 0
    skipped = 0
    added_by_db = Counter()
    
    for bug in all_new_bugs:
        # 检查是否重复
        bug_id = bug.get('id')
        url = bug.get('url') or bug.get('links', {}).get('bugreport', '')
        db = bug.get('database', bug.get('dbms', ''))
        date = bug.get('date', '')
        test_val = bug.get('test', '')
        # test可能是字符串或列表
        if isinstance(test_val, list):
            test = ' '.join(test_val)[:50] if test_val else ''
        else:
            test = str(test_val)[:50] if test_val else ''
        combo = (db, date, test)
        
        is_duplicate = False
        if bug_id and bug_id in existing_ids:
            is_duplicate = True
        elif url and url in existing_urls:
            is_duplicate = True
        elif combo in existing_combos:
            is_duplicate = True
        
        if not is_duplicate:
            main_bugs.append(bug)
            if bug_id:
                existing_ids.add(bug_id)
            if url:
                existing_urls.add(url)
            if combo[0] and combo[1] and combo[2]:
                existing_combos.add(combo)
            added += 1
            added_by_db[db] += 1
        else:
            skipped += 1
    
    print(f"   ✅ 新增: {added} 个")
    print(f"   ⚠️  跳过: {skipped} 个（重复）")
    
    if added > 0:
        print(f"\n📈 新增数据库分布:")
        for dbms, count in added_by_db.most_common():
            print(f"    {dbms:15s} +{count:4d} 个")
    
    # 按日期排序
    print(f"\n🔀 排序...")
    try:
        main_bugs.sort(key=lambda x: x.get('date', ''), reverse=False)
        print(f"   ✅ 已按日期排序")
    except Exception as e:
        print(f"   ⚠️  排序失败: {e}")
    
    # 保存
    print(f"\n💾 保存到: {main_file}")
    with open(main_path, 'w', encoding='utf-8') as f:
        json.dump(main_bugs, f, indent=4, ensure_ascii=False)
    
    # 最终统计
    final_dbms = Counter(bug.get('database', bug.get('dbms', 'Unknown')) for bug in main_bugs)
    
    print("\n" + "=" * 70)
    print("📊 合并后的数据库分布")
    print("=" * 70)
    for dbms, count in final_dbms.most_common():
        percentage = count / len(main_bugs) * 100 if main_bugs else 0
        bar = "█" * min(int(percentage / 2), 25)
        print(f"  {dbms:15s} {count:4d} ({percentage:5.1f}%) {bar}")
    print("=" * 70)
    print(f"  总计:        {len(main_bugs):4d} 个bugs")
    print("=" * 70)
    
    # 检查用户想要的数据库
    wanted_dbs = ['SQLite', 'DuckDB', 'MySQL', 'PostgreSQL', 'MonetDB', 'MariaDB']
    print("\n🎯 用户需要的数据库:")
    print("=" * 70)
    all_present = True
    total_wanted = 0
    for db in wanted_dbs:
        count = final_dbms.get(db, 0)
        total_wanted += count
        if count > 0:
            print(f"  ✅ {db:15s} {count:4d} 个")
        else:
            print(f"  ❌ {db:15s} {count:4d} 个（缺少）")
            all_present = False
    print("=" * 70)
    print(f"  需要的总计:  {total_wanted:4d} 个bugs")
    print("=" * 70)
    
    if all_present:
        print("\n🎉 太好了！所有需要的数据库都有数据！")
    else:
        print("\n💡 提示: 部分数据库缺少数据，可以继续爬取")
    
    print(f"\n✅ 合并完成！")
    print(f"💾 结果文件: {main_file}")
    print(f"📊 总bug数: {len(main_bugs)}")
    print(f"📈 本次新增: {added} 个")


if __name__ == "__main__":
    import sys
    
    # 默认合并到 bugs_new.json
    main_file = "bugs_new.json"
    
    # 可以通过命令行参数指定主文件
    if len(sys.argv) > 1:
        main_file = sys.argv[1]
    
    merge_bugs(main_file=main_file)

