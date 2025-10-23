"""
Mem0 记忆检查工具：用于调试和管理 Mem0 记忆数据

功能：
- 查看最近的记忆
- 搜索特定内容的记忆
- 导出/导入记忆数据
- 清理旧记忆

使用示例：
    # 查看最近 10 条记忆
    python tools/mem0_inspector.py inspect --limit 10
    
    # 搜索记忆
    python tools/mem0_inspector.py search "SET key value"
    
    # 导出记忆
    python tools/mem0_inspector.py export memories_backup.json
    
    # 导入记忆
    python tools/mem0_inspector.py import memories_backup.json
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def inspect_memories(user_id: str = "qtran_transfer", limit: int = 10):
    """检查最近的记忆"""
    try:
        from src.TransferLLM.mem0_adapter import TransferMemoryManager
        
        manager = TransferMemoryManager(user_id=user_id)
        
        # 获取所有记忆
        memories = manager.memory.get_all(user_id=user_id)
        
        print(f"\n📚 Total memories: {len(memories)}")
        print("\n🔝 Recent memories:")
        print("="*80)
        
        for i, mem in enumerate(memories[:limit], 1):
            mem_text = mem.get('memory', '')
            metadata = mem.get('metadata', {})
            mem_type = metadata.get('type', 'unknown')
            timestamp = metadata.get('timestamp', 'N/A')
            
            print(f"\n{i}. [{mem_type}] {timestamp}")
            print(f"   {mem_text[:200]}...")
            
            # 显示关键元数据
            if mem_type == 'successful_translation':
                iterations = metadata.get('iterations', 'N/A')
                print(f"   Iterations: {iterations}")
            elif mem_type == 'error_fix':
                print(f"   Error fix pattern")
        
        print("\n" + "="*80)
        
    except Exception as e:
        print(f"❌ Failed to inspect memories: {e}")
        import traceback
        traceback.print_exc()


def search_memories(query: str, user_id: str = "qtran_transfer", limit: int = 5):
    """搜索记忆"""
    try:
        from src.TransferLLM.mem0_adapter import TransferMemoryManager
        
        manager = TransferMemoryManager(user_id=user_id)
        
        print(f"\n🔍 Searching for: {query}")
        print("="*80)
        
        results = manager.memory.search(query=query, user_id=user_id, limit=limit)
        
        if not results:
            print("No memories found matching your query.")
            return
        
        print(f"Found {len(results)} relevant memories:\n")
        
        for i, mem in enumerate(results, 1):
            mem_text = mem.get('memory', '')
            score = mem.get('score', 0)
            metadata = mem.get('metadata', {})
            mem_type = metadata.get('type', 'unknown')
            
            print(f"{i}. [Score: {score:.3f}] [{mem_type}]")
            print(f"   {mem_text[:200]}...")
            print()
        
        print("="*80)
        
    except Exception as e:
        print(f"❌ Failed to search memories: {e}")
        import traceback
        traceback.print_exc()


def export_memories(output_path: str, user_id: str = "qtran_transfer"):
    """导出所有记忆到 JSON 文件"""
    try:
        from src.TransferLLM.mem0_adapter import TransferMemoryManager
        
        manager = TransferMemoryManager(user_id=user_id)
        all_memories = manager.memory.get_all(user_id=user_id)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_memories, f, ensure_ascii=False, indent=2)
        
        print(f"📤 Exported {len(all_memories)} memories to {output_path}")
        
    except Exception as e:
        print(f"❌ Failed to export memories: {e}")
        import traceback
        traceback.print_exc()


def import_memories(input_path: str, user_id: str = "qtran_transfer"):
    """从 JSON 文件导入记忆"""
    try:
        from src.TransferLLM.mem0_adapter import TransferMemoryManager
        
        with open(input_path, 'r', encoding='utf-8') as f:
            memories = json.load(f)
        
        manager = TransferMemoryManager(user_id=user_id)
        
        for mem in memories:
            manager.memory.add(
                mem['memory'],
                user_id=user_id,
                metadata=mem.get('metadata', {})
            )
        
        print(f"📥 Imported {len(memories)} memories from {input_path}")
        
    except Exception as e:
        print(f"❌ Failed to import memories: {e}")
        import traceback
        traceback.print_exc()


def cleanup_old_memories(days_threshold: int = 90, user_id: str = "qtran_transfer"):
    """删除超过指定天数的低分记忆"""
    try:
        from src.TransferLLM.mem0_adapter import TransferMemoryManager
        
        manager = TransferMemoryManager(user_id=user_id)
        cutoff = datetime.now() - timedelta(days=days_threshold)
        
        all_memories = manager.memory.get_all(user_id=user_id)
        to_delete = []
        
        for mem in all_memories:
            timestamp_str = mem.get('metadata', {}).get('timestamp', '')
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    score = mem.get('score', 1.0)
                    
                    # 删除旧且低分的记忆
                    if timestamp < cutoff and score < 0.4:
                        to_delete.append(mem['id'])
                except Exception:
                    pass
        
        for mem_id in to_delete:
            manager.memory.delete(memory_id=mem_id)
        
        print(f"🗑️  Cleaned up {len(to_delete)} old memories (older than {days_threshold} days)")
        
    except Exception as e:
        print(f"❌ Failed to cleanup memories: {e}")
        import traceback
        traceback.print_exc()


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="Mem0 记忆管理工具")
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # inspect 命令
    inspect_parser = subparsers.add_parser('inspect', help='查看最近的记忆')
    inspect_parser.add_argument('--user-id', default='qtran_transfer', help='用户 ID')
    inspect_parser.add_argument('--limit', type=int, default=10, help='显示数量')
    
    # search 命令
    search_parser = subparsers.add_parser('search', help='搜索记忆')
    search_parser.add_argument('query', help='搜索内容')
    search_parser.add_argument('--user-id', default='qtran_transfer', help='用户 ID')
    search_parser.add_argument('--limit', type=int, default=5, help='返回数量')
    
    # export 命令
    export_parser = subparsers.add_parser('export', help='导出记忆')
    export_parser.add_argument('output', help='输出文件路径')
    export_parser.add_argument('--user-id', default='qtran_transfer', help='用户 ID')
    
    # import 命令
    import_parser = subparsers.add_parser('import', help='导入记忆')
    import_parser.add_argument('input', help='输入文件路径')
    import_parser.add_argument('--user-id', default='qtran_transfer', help='用户 ID')
    
    # cleanup 命令
    cleanup_parser = subparsers.add_parser('cleanup', help='清理旧记忆')
    cleanup_parser.add_argument('--days', type=int, default=90, help='保留天数')
    cleanup_parser.add_argument('--user-id', default='qtran_transfer', help='用户 ID')
    
    args = parser.parse_args()
    
    if args.command == 'inspect':
        inspect_memories(user_id=args.user_id, limit=args.limit)
    elif args.command == 'search':
        search_memories(query=args.query, user_id=args.user_id, limit=args.limit)
    elif args.command == 'export':
        export_memories(output_path=args.output, user_id=args.user_id)
    elif args.command == 'import':
        import_memories(input_path=args.input, user_id=args.user_id)
    elif args.command == 'cleanup':
        cleanup_old_memories(days_threshold=args.days, user_id=args.user_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

