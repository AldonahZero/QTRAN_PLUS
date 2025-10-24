#!/usr/bin/env python3
"""
知识库导入工具：将 NoSQLFeatureKnowledgeBase 和 FeatureKnowledgeBase 导入到 Mem0

使用方法:
    # 导入所有知识库
    python tools/knowledge_base_importer.py --all
    
    # 只导入 MongoDB 知识
    python tools/knowledge_base_importer.py --nosql mongodb
    
    # 只导入 MySQL 知识
    python tools/knowledge_base_importer.py --sql mysql
    
    # 导入特定类型的知识
    python tools/knowledge_base_importer.py --sql mysql --type datatype,function
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
import time

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from src.TransferLLM.mem0_adapter import TransferMemoryManager, FallbackMemoryManager
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    print("⚠️ Mem0 not available, will use fallback manager")


class KnowledgeBaseImporter:
    """知识库导入器"""
    
    def __init__(self, user_id: str = "qtran_knowledge_base"):
        """初始化导入器"""
        try:
            if MEM0_AVAILABLE:
                self.manager = TransferMemoryManager(user_id=user_id)
            else:
                self.manager = FallbackMemoryManager(user_id=user_id)
            print(f"✅ Memory manager initialized for user: {user_id}")
        except Exception as e:
            print(f"❌ Failed to initialize memory manager: {e}")
            raise
        
        self.base_path = Path(__file__).parent.parent
        self.stats = {
            "total_imported": 0,
            "by_database": {},
            "by_type": {},
            "errors": []
        }
    
    def import_mongodb_knowledge(self):
        """导入 MongoDB 知识库"""
        print("\n📚 Importing MongoDB knowledge...")
        db_name = "mongodb"
        
        # 1. 导入知识图谱
        kg_path = self.base_path / "NoSQLFeatureKnowledgeBase/MongoDB/mongodb_knowledge_graph.json"
        if kg_path.exists():
            with open(kg_path, 'r', encoding='utf-8') as f:
                kg_data = json.load(f)
            
            # 导入操作符
            for op_name, op_info in kg_data.get("operators", {}).items():
                memory_text = self._format_mongodb_operator(op_name, op_info)
                metadata = {
                    "database": db_name,
                    "type": "operator",
                    "feature_name": op_name,
                    "source": "knowledge_graph"
                }
                self._add_memory(memory_text, db_name, metadata)
            
            print(f"  ✅ Imported {len(kg_data.get('operators', {}))} MongoDB operators")
        
        # 2. 导入 API 模式
        api_path = self.base_path / "NoSQLFeatureKnowledgeBase/MongoDB/extracted_api_patterns.json"
        if api_path.exists():
            with open(api_path, 'r', encoding='utf-8') as f:
                api_data = json.load(f)
            
            # 由于文件很大，只导入前 500 个示例
            imported_count = 0
            max_samples = 500
            
            for i, pattern in enumerate(api_data[:max_samples]):
                if i % 50 == 0:
                    print(f"  Processing API patterns: {i}/{min(max_samples, len(api_data))}")
                
                memory_text = self._format_mongodb_api_pattern(pattern)
                metadata = {
                    "database": db_name,
                    "type": "api_pattern",
                    "collection": pattern.get("collection", "unknown"),
                    "method": pattern.get("method", "unknown"),
                    "source": "api_patterns"
                }
                self._add_memory(memory_text, db_name, metadata)
                imported_count += 1
            
            print(f"  ✅ Imported {imported_count} MongoDB API patterns")
        
        # 3. 导入代码片段
        snippet_path = self.base_path / "NoSQLFeatureKnowledgeBase/MongoDB/mongodb_code_snippets.json"
        if snippet_path.exists():
            with open(snippet_path, 'r', encoding='utf-8') as f:
                snippet_data = json.load(f)
            
            # 同样限制数量
            imported_count = 0
            max_snippets = 300
            
            for i, snippet in enumerate(snippet_data[:max_snippets]):
                if i % 50 == 0:
                    print(f"  Processing code snippets: {i}/{min(max_snippets, len(snippet_data))}")
                
                memory_text = self._format_mongodb_code_snippet(snippet)
                metadata = {
                    "database": db_name,
                    "type": "code_snippet",
                    "source": "code_snippets"
                }
                if isinstance(snippet, dict):
                    metadata.update({
                        "category": snippet.get("category", "unknown"),
                        "operation": snippet.get("operation", "unknown")
                    })
                self._add_memory(memory_text, db_name, metadata)
                imported_count += 1
            
            print(f"  ✅ Imported {imported_count} MongoDB code snippets")
    
    def import_redis_knowledge(self):
        """导入 Redis 知识库"""
        print("\n📚 Importing Redis knowledge...")
        db_name = "redis"
        
        # 导入 Redis 命令知识
        cmd_kb_path = self.base_path / "NoSQLFeatureKnowledgeBase/Redis/outputs/redis_commands_knowledge.json"
        if cmd_kb_path.exists():
            with open(cmd_kb_path, 'r', encoding='utf-8') as f:
                cmd_data = json.load(f)
            
            for cmd_name, cmd_info in cmd_data.get("commands", {}).items():
                memory_text = self._format_redis_command(cmd_name, cmd_info)
                metadata = {
                    "database": db_name,
                    "type": "command",
                    "feature_name": cmd_name,
                    "source": "commands_knowledge"
                }
                self._add_memory(memory_text, db_name, metadata)
            
            print(f"  ✅ Imported {len(cmd_data.get('commands', {}))} Redis commands")
        
        # 导入 SQL 到 Redis 映射
        mapping_path = self.base_path / "NoSQLFeatureKnowledgeBase/Redis/sql_to_redis_mapping.json"
        if mapping_path.exists():
            with open(mapping_path, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
            
            for mapping in mapping_data if isinstance(mapping_data, list) else [mapping_data]:
                memory_text = self._format_sql_to_redis_mapping(mapping)
                metadata = {
                    "database": db_name,
                    "type": "sql_mapping",
                    "source": "sql_to_redis_mapping"
                }
                self._add_memory(memory_text, db_name, metadata)
            
            print(f"  ✅ Imported SQL to Redis mappings")
    
    def import_sql_database_knowledge(self, db_name: str, knowledge_types: Optional[List[str]] = None):
        """
        导入 SQL 数据库知识
        
        Args:
            db_name: 数据库名称 (mysql, postgres, sqlite 等)
            knowledge_types: 知识类型列表 ['datatype', 'function', 'operator']，None 表示全部
        """
        print(f"\n📚 Importing {db_name.upper()} knowledge...")
        
        db_path = self.base_path / f"FeatureKnowledgeBase/{db_name}"
        if not db_path.exists():
            print(f"  ⚠️ Database path not found: {db_path}")
            return
        
        if knowledge_types is None:
            knowledge_types = ['datatype', 'function', 'operator']
        
        for ktype in knowledge_types:
            type_path = db_path / ktype / "results"
            if not type_path.exists():
                print(f"  ⚠️ Knowledge type path not found: {type_path}")
                continue
            
            # 获取所有 JSON 文件
            json_files = sorted(type_path.glob("*.json"))
            imported_count = 0
            
            print(f"  Processing {ktype}s: found {len(json_files)} files")
            
            for i, json_file in enumerate(json_files):
                if i % 20 == 0 and i > 0:
                    print(f"    Progress: {i}/{len(json_files)}")
                
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        feature_data = json.load(f)
                    
                    memory_text = self._format_sql_feature(db_name, ktype, feature_data)
                    if not memory_text:
                        continue
                    
                    metadata = {
                        "database": db_name,
                        "type": ktype,
                        "source": "feature_knowledge_base"
                    }
                    
                    # 添加特征名称
                    if ktype == 'function':
                        metadata["feature_name"] = feature_data.get("Name", "unknown")
                    elif ktype == 'datatype':
                        metadata["feature_name"] = feature_data.get("Feature", ["unknown"])[0] if feature_data.get("Feature") else "unknown"
                    elif ktype == 'operator':
                        metadata["feature_name"] = feature_data.get("Name", "unknown")
                    
                    # 添加分类
                    if "Category" in feature_data:
                        categories = feature_data["Category"]
                        if isinstance(categories, list) and categories:
                            metadata["category"] = categories[0]
                    
                    self._add_memory(memory_text, db_name, metadata)
                    imported_count += 1
                    
                except Exception as e:
                    self.stats["errors"].append({
                        "file": str(json_file),
                        "error": str(e)
                    })
            
            print(f"  ✅ Imported {imported_count} {db_name} {ktype}s")
    
    def _format_mongodb_operator(self, op_name: str, op_info: Dict) -> str:
        """格式化 MongoDB 操作符信息"""
        parts = [f"MongoDB Operator: {op_name}"]
        
        if op_info.get("equivalent_forms"):
            parts.append(f"Equivalent forms: {', '.join(op_info['equivalent_forms'])}")
        
        if op_info.get("used_with_methods"):
            parts.append(f"Used with methods: {', '.join(op_info['used_with_methods'])}")
        
        if op_info.get("properties"):
            parts.append(f"Properties: {', '.join(op_info['properties'])}")
        
        if op_info.get("relations"):
            for rel in op_info["relations"]:
                if rel.get("type") == "equivalent_to":
                    parts.append(f"Equivalent to: {rel.get('construct', {}).get('operator', 'unknown')} via {rel.get('law', 'unknown')}")
                elif rel.get("type") == "inverse_of":
                    parts.append(f"Inverse of: {rel.get('target_operator', 'unknown')} via {rel.get('via_operator', '$not')}")
        
        return "\n".join(parts)
    
    def _format_mongodb_api_pattern(self, pattern: Dict) -> str:
        """格式化 MongoDB API 模式"""
        collection = pattern.get("collection", "collection")
        method = pattern.get("method", "method")
        
        parts = [f"MongoDB API Pattern: db.{collection}.{method}()"]
        
        # 添加示例参数（简化版本，避免太长）
        if pattern.get("arguments"):
            args_str = json.dumps(pattern["arguments"], ensure_ascii=False)
            if len(args_str) > 200:
                args_str = args_str[:200] + "..."
            parts.append(f"Example arguments: {args_str}")
        
        if pattern.get("operators"):
            parts.append(f"Uses operators: {', '.join(pattern['operators'])}")
        
        if pattern.get("metadata", {}).get("description"):
            desc = pattern["metadata"]["description"]
            if len(desc) > 150:
                desc = desc[:150] + "..."
            parts.append(f"Description: {desc}")
        
        return "\n".join(parts)
    
    def _format_mongodb_code_snippet(self, snippet: Any) -> str:
        """格式化 MongoDB 代码片段"""
        if isinstance(snippet, dict):
            parts = ["MongoDB Code Snippet"]
            
            if snippet.get("category"):
                parts.append(f"Category: {snippet['category']}")
            
            if snippet.get("operation"):
                parts.append(f"Operation: {snippet['operation']}")
            
            if snippet.get("code"):
                code = snippet["code"]
                if len(code) > 300:
                    code = code[:300] + "..."
                parts.append(f"Code:\n{code}")
            
            if snippet.get("description"):
                parts.append(f"Description: {snippet['description']}")
            
            return "\n".join(parts)
        else:
            # 如果是字符串或其他格式
            snippet_str = str(snippet)
            if len(snippet_str) > 300:
                snippet_str = snippet_str[:300] + "..."
            return f"MongoDB Code Snippet:\n{snippet_str}"
    
    def _format_redis_command(self, cmd_name: str, cmd_info: Dict) -> str:
        """格式化 Redis 命令信息"""
        parts = [f"Redis Command: {cmd_name}"]
        
        if cmd_info.get("examples"):
            examples = cmd_info["examples"][:3]  # 最多 3 个示例
            for ex in examples:
                if ex.get("raw"):
                    parts.append(f"Example: {ex['raw']}")
        
        if cmd_info.get("cards"):
            for card in cmd_info["cards"][:2]:  # 最多 2 张卡片
                if isinstance(card, dict) and card.get("description"):
                    desc = card["description"]
                    if len(desc) > 150:
                        desc = desc[:150] + "..."
                    parts.append(f"Description: {desc}")
        
        return "\n".join(parts)
    
    def _format_sql_to_redis_mapping(self, mapping: Any) -> str:
        """格式化 SQL 到 Redis 的映射"""
        if isinstance(mapping, dict):
            parts = ["SQL to Redis Mapping"]
            
            if mapping.get("sql_operation"):
                parts.append(f"SQL Operation: {mapping['sql_operation']}")
            
            if mapping.get("redis_command"):
                parts.append(f"Redis Command: {mapping['redis_command']}")
            
            if mapping.get("example_sql"):
                parts.append(f"SQL Example: {mapping['example_sql']}")
            
            if mapping.get("example_redis"):
                parts.append(f"Redis Example: {mapping['example_redis']}")
            
            if mapping.get("notes"):
                parts.append(f"Notes: {mapping['notes']}")
            
            return "\n".join(parts)
        else:
            return f"SQL to Redis Mapping:\n{str(mapping)[:300]}"
    
    def _format_sql_feature(self, db_name: str, feature_type: str, feature_data: Dict) -> str:
        """格式化 SQL 特性信息"""
        parts = []
        
        # 标题
        if feature_type == 'function':
            feature_name = feature_data.get("Name", "Unknown")
            parts.append(f"{db_name.upper()} Function: {feature_name}")
        elif feature_type == 'datatype':
            feature_name = feature_data.get("Feature", ["Unknown"])[0] if feature_data.get("Feature") else "Unknown"
            parts.append(f"{db_name.upper()} Data Type: {feature_name}")
        elif feature_type == 'operator':
            feature_name = feature_data.get("Name", "Unknown")
            parts.append(f"{db_name.upper()} Operator: {feature_name}")
        
        # 描述
        if feature_data.get("Description"):
            descriptions = feature_data["Description"]
            if isinstance(descriptions, list):
                desc_text = " ".join(descriptions)
            else:
                desc_text = str(descriptions)
            
            # 清理和截断描述
            desc_text = desc_text.replace('\n', ' ').strip()
            if len(desc_text) > 300:
                desc_text = desc_text[:300] + "..."
            
            if desc_text:
                parts.append(f"Description: {desc_text}")
        
        # 分类
        if feature_data.get("Category"):
            categories = feature_data["Category"]
            if isinstance(categories, list):
                parts.append(f"Category: {' > '.join(categories)}")
        
        # 示例 SQL
        if feature_data.get("EffectiveSQLs"):
            sqls = feature_data["EffectiveSQLs"][:3]  # 最多 3 个示例
            if sqls:
                parts.append(f"Example SQL: {'; '.join(sqls)}")
        elif feature_data.get("Examples"):
            examples = feature_data["Examples"]
            if isinstance(examples, list) and examples:
                example_text = str(examples[0])
                if len(example_text) > 200:
                    example_text = example_text[:200] + "..."
                parts.append(f"Example: {example_text}")
        
        # 参考链接
        if feature_data.get("Reference HTML"):
            parts.append(f"Reference: {feature_data['Reference HTML']}")
        elif feature_data.get("HTML"):
            html = feature_data["HTML"]
            if isinstance(html, list) and html:
                parts.append(f"Reference: {html[0]}")
        
        return "\n".join(parts) if parts else ""
    
    def _add_memory(self, memory_text: str, db_name: str, metadata: Dict):
        """添加记忆到 mem0"""
        try:
            if not memory_text or not memory_text.strip():
                return
            
            # 为不同数据库使用不同的 user_id
            user_id = f"qtran_kb_{db_name}"
            
            self.manager.memory.add(
                memory_text,
                user_id=user_id,
                metadata=metadata
            )
            
            # 更新统计
            self.stats["total_imported"] += 1
            self.stats["by_database"][db_name] = self.stats["by_database"].get(db_name, 0) + 1
            
            ktype = metadata.get("type", "unknown")
            self.stats["by_type"][ktype] = self.stats["by_type"].get(ktype, 0) + 1
            
        except Exception as e:
            self.stats["errors"].append({
                "database": db_name,
                "metadata": metadata,
                "error": str(e)
            })
    
    def print_stats(self):
        """打印导入统计"""
        print("\n" + "=" * 60)
        print("📊 Knowledge Base Import Statistics")
        print("=" * 60)
        print(f"Total memories imported: {self.stats['total_imported']}")
        print(f"\nBy Database:")
        for db, count in sorted(self.stats['by_database'].items()):
            print(f"  {db}: {count}")
        print(f"\nBy Type:")
        for ktype, count in sorted(self.stats['by_type'].items()):
            print(f"  {ktype}: {count}")
        
        if self.stats["errors"]:
            print(f"\n⚠️ Errors encountered: {len(self.stats['errors'])}")
            print("First 5 errors:")
            for error in self.stats["errors"][:5]:
                print(f"  - {error}")
        
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Import knowledge bases to Mem0")
    parser.add_argument("--all", action="store_true", help="Import all knowledge bases")
    parser.add_argument("--nosql", choices=["mongodb", "redis"], help="Import specific NoSQL database")
    parser.add_argument("--sql", 
                       choices=["mysql", "postgres", "sqlite", "clickhouse", "duckdb", "mariadb", "monetdb", "tidb"],
                       help="Import specific SQL database")
    parser.add_argument("--type", help="Knowledge types to import (comma-separated: datatype,function,operator)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without actually importing")
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No data will be imported")
        return
    
    importer = KnowledgeBaseImporter()
    
    start_time = time.time()
    
    try:
        if args.all:
            # 导入所有知识库
            print("🚀 Starting full knowledge base import...")
            
            # NoSQL 数据库
            importer.import_mongodb_knowledge()
            importer.import_redis_knowledge()
            
            # SQL 数据库
            sql_databases = ["mysql", "postgres", "sqlite", "clickhouse", "duckdb", "mariadb", "monetdb", "tidb"]
            for db in sql_databases:
                importer.import_sql_database_knowledge(db)
        
        elif args.nosql:
            if args.nosql == "mongodb":
                importer.import_mongodb_knowledge()
            elif args.nosql == "redis":
                importer.import_redis_knowledge()
        
        elif args.sql:
            knowledge_types = None
            if args.type:
                knowledge_types = [t.strip() for t in args.type.split(",")]
            
            importer.import_sql_database_knowledge(args.sql, knowledge_types)
        
        else:
            parser.print_help()
            return
        
        elapsed_time = time.time() - start_time
        
        # 打印统计
        importer.print_stats()
        print(f"\n⏱️  Total time: {elapsed_time:.2f}s")
        print(f"💾 Average time per memory: {elapsed_time/max(importer.stats['total_imported'], 1):.3f}s")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Import interrupted by user")
        importer.print_stats()
    except Exception as e:
        print(f"\n❌ Import failed with error: {e}")
        import traceback
        traceback.print_exc()
        importer.print_stats()


if __name__ == "__main__":
    main()

