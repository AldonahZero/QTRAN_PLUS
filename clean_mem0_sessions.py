#!/usr/bin/env python3
"""
清理 mem0 中的翻译会话记忆，保留知识库

策略：
- 删除所有 qtran_{db1}_to_{db2} 格式的记忆（翻译会话）
- 保留所有 qtran_kb_{db} 格式的记忆（知识库）

优势：
- 删除可能包含错误的翻译案例
- 保留静态知识库（从文档导入，质量可靠）
- 重建翻译记忆比重建知识库容易得多
"""

import os
import sys
import argparse
from typing import List, Dict, Any

# 设置环境变量
os.environ["QTRAN_USE_MEM0"] = "true"

# 添加项目路径
sys.path.insert(0, '/root/QTRAN')

try:
    from src.TransferLLM.mem0_adapter import TransferMemoryManager
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保在QTRAN项目根目录下运行此脚本")
    sys.exit(1)


class SessionCleaner:
    """翻译会话记忆清理器（保留知识库）"""
    
    def __init__(self):
        # 翻译会话的user_id模式：qtran_{db1}_to_{db2}
        # 知识库的user_id模式：qtran_kb_{db}
        
        # 已知的翻译会话user_id（可以扩展）
        self.session_user_ids = [
            "qtran_redis_to_mongodb",
            "qtran_sqlite_to_mongodb",
            "qtran_mysql_to_postgres",
            "qtran_postgres_to_mysql",
            "qtran_sqlite_to_duckdb",
            "qtran_duckdb_to_sqlite",
            "qtran_duckdb_to_postgres",
            "qtran_postgres_to_duckdb",
            "qtran_mysql_to_mariadb",
            "qtran_mariadb_to_mysql",
            "qtran_clickhouse_to_postgres",
            "qtran_postgres_to_clickhouse",
            "qtran_monetdb_to_postgres",
            "qtran_tidb_to_mysql",
        ]
        
        # 知识库user_id（这些要保留！）
        self.kb_user_ids = [
            "qtran_kb_mongodb",
            "qtran_kb_redis",
            "qtran_kb_mysql",
            "qtran_kb_postgres",
            "qtran_kb_sqlite",
            "qtran_kb_duckdb",
            "qtran_kb_clickhouse",
            "qtran_kb_mariadb",
            "qtran_kb_monetdb",
            "qtran_kb_tidb",
        ]
    
    def is_session_user_id(self, user_id: str) -> bool:
        """判断是否是翻译会话user_id"""
        # 模式：qtran_{db1}_to_{db2}
        if "_to_" in user_id and user_id.startswith("qtran_"):
            return True
        return False
    
    def is_kb_user_id(self, user_id: str) -> bool:
        """判断是否是知识库user_id"""
        # 模式：qtran_kb_{db}
        if user_id.startswith("qtran_kb_"):
            return True
        return False
    
    def list_all_memories(self, user_id: str) -> List[Dict[str, Any]]:
        """列出指定user_id的所有记忆"""
        try:
            mgr = TransferMemoryManager(user_id=user_id)
            
            # 尝试获取记忆（使用一个通用查询）
            memories = mgr.memory.get_all(user_id=user_id)
            
            return memories if memories else []
        except Exception as e:
            print(f"⚠️ 获取记忆失败 ({user_id}): {e}")
            return []
    
    def delete_user_memories(self, user_id: str, dry_run: bool = True) -> int:
        """删除指定user_id的所有记忆"""
        try:
            print(f"\n{'='*60}")
            print(f"📁 处理: {user_id}")
            print('='*60)
            
            # 获取所有记忆
            memories = self.list_all_memories(user_id)
            
            if not memories:
                print("✅ 没有找到记忆")
                return 0
            
            memory_count = len(memories)
            print(f"📊 找到 {memory_count} 条记忆")
            
            if dry_run:
                print(f"🔍 [试运行] 将删除这些记忆（实际未删除）")
                # 显示前3条记忆的内容
                for i, mem in enumerate(memories[:3], 1):
                    mem_text = str(mem.get('memory', mem.get('data', '')))[:100]
                    print(f"   {i}. {mem_text}...")
                if memory_count > 3:
                    print(f"   ... 还有 {memory_count - 3} 条")
            else:
                print(f"🗑️ 正在删除...")
                mgr = TransferMemoryManager(user_id=user_id)
                
                # 删除所有记忆
                for i, mem in enumerate(memories, 1):
                    mem_id = mem.get('id')
                    if mem_id:
                        try:
                            mgr.memory.delete(mem_id)
                            if i % 10 == 0:
                                print(f"   已删除 {i}/{memory_count}")
                        except Exception as e:
                            print(f"   ⚠️ 删除失败: {mem_id} - {e}")
                
                print(f"✅ 已删除 {memory_count} 条记忆")
            
            return memory_count
            
        except Exception as e:
            print(f"❌ 删除失败: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def clean_all_sessions(self, dry_run: bool = True) -> Dict[str, int]:
        """清理所有翻译会话记忆"""
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║  🧹 翻译会话记忆清理工具（保留知识库）                        ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        print()
        print("📋 策略:")
        print("  ✅ 保留知识库: qtran_kb_{database}")
        print("  ❌ 删除会话记忆: qtran_{db1}_to_{db2}")
        print()
        
        results = {}
        total_deleted = 0
        
        # 1. 先检查知识库（确认不会被删除）
        print("\n" + "="*60)
        print("✅ 检查知识库（这些将被保留）")
        print("="*60)
        
        for kb_id in self.kb_user_ids:
            memories = self.list_all_memories(kb_id)
            if memories:
                print(f"  ✅ {kb_id}: {len(memories)} 条记忆")
        
        # 2. 清理翻译会话记忆
        print("\n" + "="*60)
        print("❌ 清理翻译会话记忆")
        print("="*60)
        
        for session_id in self.session_user_ids:
            count = self.delete_user_memories(session_id, dry_run=dry_run)
            if count > 0:
                results[session_id] = count
                total_deleted += count
        
        # 3. 总结
        print("\n" + "="*60)
        print("📊 清理总结")
        print("="*60)
        
        if not results:
            print("✅ 所有翻译会话记忆都是空的，无需清理")
        else:
            print(f"{'会话类型':<35} {'记忆数量':>10}")
            print("-" * 60)
            for session_id, count in results.items():
                print(f"{session_id:<35} {count:>10}")
            print("-" * 60)
            print(f"{'总计':<35} {total_deleted:>10}")
        
        if dry_run:
            print("\n💡 这是试运行模式，实际未删除任何记忆")
            print("   如需实际删除，请使用 --delete 参数")
        else:
            print("\n✅ 清理完成！")
            print("   知识库已保留，翻译会话记忆已删除")
            print("   新的翻译会话将自动创建新的记忆")
        
        return results


def main():
    parser = argparse.ArgumentParser(
        description="清理mem0中的翻译会话记忆（保留知识库）"
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="实际删除记忆（默认为试运行模式）"
    )
    parser.add_argument(
        "--user-id",
        type=str,
        help="只清理指定的user_id"
    )
    
    args = parser.parse_args()
    
    cleaner = SessionCleaner()
    
    if args.user_id:
        # 只清理指定的user_id
        if cleaner.is_kb_user_id(args.user_id):
            print(f"⚠️ 警告：{args.user_id} 是知识库，不会被删除")
            sys.exit(0)
        
        if not cleaner.is_session_user_id(args.user_id):
            print(f"⚠️ 警告：{args.user_id} 不是翻译会话格式")
            response = input("确认删除？(yes/no): ")
            if response.lower() != 'yes':
                print("❌ 已取消")
                sys.exit(0)
        
        cleaner.delete_user_memories(args.user_id, dry_run=not args.delete)
    else:
        # 清理所有翻译会话记忆
        if args.delete:
            print("⚠️ 警告：即将删除所有翻译会话记忆！")
            print("   知识库将被保留")
            print()
            response = input("确认删除？(yes/no): ")
            if response.lower() != 'yes':
                print("❌ 已取消")
                sys.exit(0)
        
        cleaner.clean_all_sessions(dry_run=not args.delete)


if __name__ == "__main__":
    main()

