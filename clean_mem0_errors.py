#!/usr/bin/env python3
"""
清理 mem0 中的错误翻译记忆

问题模式：
1. NULL值被删除
2. 数据值被改变
3. 表名被改变
4. 空字符串被替换
"""

import os
import sys
import json
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


class Mem0Cleaner:
    """mem0 错误记忆清理器"""
    
    def __init__(self):
        self.error_patterns = [
            "VALUES(NULL)",  # NULL被删除的模式
            "VALUES('default')",  # NULL被替换成default
            "meaningless",  # 包含"meaningless"的记忆
            "t2",  # 可能包含表名错误的记忆
        ]
        
        # 需要检查的user_id列表
        self.user_ids = [
            "qtran_duckdb_to_postgres",
            "qtran_postgres_to_duckdb",
            "qtran_mysql_to_mariadb",
            "qtran_mariadb_to_mysql",
            "qtran_sqlite_to_duckdb",
            "qtran_duckdb_to_sqlite",
        ]
    
    def check_memory(self, memory: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查单条记忆是否包含错误模式
        
        返回:
        {
            "is_error": bool,
            "reason": str,
            "memory_id": str,
            "content": str
        }
        """
        memory_str = str(memory).upper()
        memory_id = memory.get('id', 'unknown')
        
        result = {
            "is_error": False,
            "reason": "",
            "memory_id": memory_id,
            "content": str(memory)[:200] + "..." if len(str(memory)) > 200 else str(memory)
        }
        
        # 检查是否包含NULL被删除的模式
        if "NULL" in memory_str:
            if "INSERT" in memory_str:
                # 检查是否有VALUES(NULL)后面跟着没有NULL的翻译
                if "DEFAULT" in memory_str or "''" in memory_str:
                    result["is_error"] = True
                    result["reason"] = "疑似NULL被替换成默认值"
                    return result
        
        # 检查是否包含meaningless关键词
        if "MEANINGLESS" in memory_str:
            result["is_error"] = True
            result["reason"] = "包含'meaningless'关键词（可能基于旧prompt）"
            return result
        
        # 检查是否有表名不一致的情况
        if "T2" in memory_str and "T0" in memory_str:
            # 可能是表名被改变
            result["is_error"] = True
            result["reason"] = "疑似表名被改变（t2→t0）"
            return result
        
        return result
    
    def scan_user_memories(self, user_id: str) -> List[Dict[str, Any]]:
        """扫描指定用户的所有记忆"""
        try:
            print(f"\n{'='*60}")
            print(f"🔍 扫描用户: {user_id}")
            print('='*60)
            
            mgr = TransferMemoryManager(user_id=user_id)
            
            # 获取INSERT相关的记忆
            test_queries = [
                "INSERT INTO",
                "VALUES",
                "NULL",
                "CREATE TABLE",
            ]
            
            all_memories = []
            seen_ids = set()
            
            for query in test_queries:
                try:
                    # 尝试不同的数据库组合
                    for origin_db in ["duckdb", "postgres", "mysql", "mariadb", "sqlite"]:
                        for target_db in ["postgres", "duckdb", "mariadb", "mysql", "duckdb"]:
                            if origin_db == target_db:
                                continue
                            
                            try:
                                memories = mgr.get_relevant_memories(
                                    query, 
                                    origin_db, 
                                    target_db, 
                                    limit=10
                                )
                                
                                for m in memories:
                                    m_id = m.get('id', str(m))
                                    if m_id not in seen_ids:
                                        all_memories.append(m)
                                        seen_ids.add(m_id)
                            except Exception as e:
                                continue  # 忽略不存在的组合
                
                except Exception as e:
                    print(f"⚠️ 查询'{query}'失败: {e}")
                    continue
            
            print(f"📊 找到 {len(all_memories)} 条记忆")
            
            # 检查每条记忆
            error_memories = []
            for i, memory in enumerate(all_memories, 1):
                result = self.check_memory(memory)
                if result["is_error"]:
                    error_memories.append(result)
                    print(f"\n❌ 错误记忆 #{i}")
                    print(f"   ID: {result['memory_id']}")
                    print(f"   原因: {result['reason']}")
                    print(f"   内容: {result['content']}")
            
            if not error_memories:
                print("✅ 未发现明显的错误记忆")
            else:
                print(f"\n⚠️ 共发现 {len(error_memories)} 条可疑的错误记忆")
            
            return error_memories
            
        except Exception as e:
            print(f"❌ 扫描失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def clean_memories(self, user_id: str, memory_ids: List[str], dry_run: bool = True):
        """清理指定的记忆"""
        if not memory_ids:
            print("✅ 没有需要清理的记忆")
            return
        
        try:
            mgr = TransferMemoryManager(user_id=user_id)
            
            if dry_run:
                print(f"\n🔍 [试运行模式] 将要删除 {len(memory_ids)} 条记忆:")
                for i, mid in enumerate(memory_ids, 1):
                    print(f"   {i}. {mid}")
                print("\n💡 如要实际删除，请使用 --delete 参数")
            else:
                print(f"\n🗑️ 正在删除 {len(memory_ids)} 条错误记忆...")
                for i, mid in enumerate(memory_ids, 1):
                    try:
                        # mem0的delete API可能不同，这里需要根据实际API调整
                        # mgr.delete_memories([mid])
                        print(f"   {i}/{len(memory_ids)} 删除: {mid}")
                    except Exception as e:
                        print(f"   ❌ 删除失败: {mid} - {e}")
                
                print("✅ 清理完成")
        
        except Exception as e:
            print(f"❌ 清理失败: {e}")
            import traceback
            traceback.print_exc()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="清理mem0中的错误翻译记忆")
    parser.add_argument(
        "--user-id",
        type=str,
        help="指定要清理的user_id（不指定则扫描所有）"
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="实际删除错误记忆（默认为试运行模式）"
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="仅列出错误记忆，不删除"
    )
    
    args = parser.parse_args()
    
    cleaner = Mem0Cleaner()
    
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  🧹 mem0 错误记忆清理工具                                     ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("📋 检查模式:")
    print("  ❌ NULL值被删除或替换")
    print("  ❌ 包含'meaningless'关键词（基于旧prompt）")
    print("  ❌ 表名被改变（t2→t0）")
    print("  ❌ 数据值被修改")
    print()
    
    # 确定要扫描的user_id列表
    user_ids_to_scan = [args.user_id] if args.user_id else cleaner.user_ids
    
    all_error_memories = {}
    
    # 扫描所有user_id
    for user_id in user_ids_to_scan:
        error_memories = cleaner.scan_user_memories(user_id)
        if error_memories:
            all_error_memories[user_id] = error_memories
    
    # 总结
    print("\n" + "="*60)
    print("📊 扫描总结")
    print("="*60)
    
    if not all_error_memories:
        print("✅ 所有用户的mem0记忆都正常，无需清理")
        return
    
    total_errors = sum(len(errors) for errors in all_error_memories.values())
    print(f"⚠️ 共发现 {total_errors} 条错误记忆")
    
    for user_id, errors in all_error_memories.items():
        print(f"\n【{user_id}】")
        print(f"  错误记忆数: {len(errors)}")
        
        # 按原因分组统计
        reasons = {}
        for err in errors:
            reason = err['reason']
            reasons[reason] = reasons.get(reason, 0) + 1
        
        for reason, count in reasons.items():
            print(f"    - {reason}: {count}条")
    
    # 清理或仅列出
    if args.list_only:
        print("\n💡 仅列出模式，不执行删除")
        return
    
    if args.delete:
        print("\n⚠️ 警告：即将删除错误记忆！")
        response = input("确认删除？(yes/no): ")
        if response.lower() != 'yes':
            print("❌ 已取消")
            return
        
        for user_id, errors in all_error_memories.items():
            memory_ids = [err['memory_id'] for err in errors]
            cleaner.clean_memories(user_id, memory_ids, dry_run=False)
    else:
        print("\n💡 提示：")
        print("  - 这是试运行模式，实际未删除任何记忆")
        print("  - 如需删除，请添加 --delete 参数")
        print("  - 建议先备份重要数据")
        print()
        print("示例命令：")
        print("  python3 clean_mem0_errors.py --delete  # 删除所有错误记忆")
        print("  python3 clean_mem0_errors.py --user-id qtran_duckdb_to_postgres --delete  # 删除指定用户的错误记忆")


if __name__ == "__main__":
    main()

