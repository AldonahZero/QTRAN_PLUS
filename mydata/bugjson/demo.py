#!/usr/bin/env python3
"""
爬虫演示脚本 - 爬取少量数据进行测试
"""

from advanced_crawler import GitHubIssueCrawler
import json


def demo_crawl():
    """演示爬虫功能"""
    
    print("=" * 70)
    print("🎬 数据库Bug爬虫演示")
    print("=" * 70)
    print("\n这个演示将爬取少量bug数据，用于测试爬虫功能\n")
    
    # 创建爬虫实例（不使用token，仅演示）
    print("1️⃣  创建爬虫实例...")
    crawler = GitHubIssueCrawler(output_file="bugs_demo.json")
    
    # 保存原始bug数量
    original_count = len(crawler.existing_bugs)
    print(f"   原始bug数量: {original_count}")
    
    # 定义要爬取的数据库
    databases = [
        ("duckdb/duckdb", "DuckDB", ["bug"]),
        ("ClickHouse/ClickHouse", "ClickHouse", ["bug"]),
        ("postgres/postgres", "PostgreSQL", []),
        ("mysql/mysql-server", "MySQL", ["Bug"]),
        ("MonetDB/MonetDB", "MonetDB", ["bug"]),
        ("MariaDB/server", "MariaDB", ["bug"]),
    ]
    
    counts = {}
    
    # 爬取每个数据库
    for i, (repo, dbms_name, labels) in enumerate(databases, 2):
        print(f"\n{i}️⃣  爬取{dbms_name}最新的bug...")
        count = crawler.crawl_repo(
            repo=repo,
            dbms_name=dbms_name,
            max_issues=10,  # 每个数据库10个用于演示
            labels=labels
        )
        counts[dbms_name] = count
    
    duckdb_count = counts.get("DuckDB", 0)
    clickhouse_count = counts.get("ClickHouse", 0)
    
    # 计算总新增
    total_new = sum(counts.values())
    
    # 保存结果
    if total_new > 0:
        print(f"\n{len(databases)+1}️⃣  保存结果...")
        crawler.save_bugs(backup=False)
        
        # 显示新增的bug
        print("\n5️⃣  新增的bug示例:")
        print("   " + "─" * 66)
        new_bugs = crawler.existing_bugs[original_count:original_count + 3]
        for i, bug in enumerate(new_bugs, 1):
            print(f"\n   Bug #{i}:")
            print(f"   📌 标题: {bug['title'][:55]}...")
            print(f"   🗓️  日期: {bug['date']}")
            print(f"   💾 数据库: {bug['dbms']}")
            print(f"   🔍 Oracle: {bug['oracle']}")
            print(f"   👤 Reporter: {bug['reporter']}")
            print(f"   📊 状态: {bug['status']}")
            if bug.get('test'):
                print(f"   🧪 SQL测试: {len(bug['test'])}条")
                if bug['test']:
                    print(f"      - {bug['test'][0][:50]}...")
    
    # 统计
    print("\n" + "=" * 70)
    print("📊 演示统计:")
    print("=" * 70)
    for dbms_name, count in counts.items():
        status = "✅" if count > 0 else "⚠️ "
        print(f"  {status} {dbms_name:15s} {count:3d} 个")
    print(f"  {'─' * 36}")
    print(f"  总新增:         {total_new:3d} 个")
    print(f"  当前总数:       {len(crawler.existing_bugs):3d} 个")
    print("=" * 70)
    
    print("\n✅ 演示完成!")
    print("\n💡 提示:")
    print("   - 演示结果保存在: bugs_demo.json")
    print("   - 完整爬取使用: python advanced_crawler.py")
    print("   - 查看统计: python stats.py")
    print("   - 详细文档: cat README.md")
    

if __name__ == "__main__":
    demo_crawl()

