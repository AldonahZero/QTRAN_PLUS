"""
Mem0 适配器 - 变异阶段（Mutation Phase）
为 QTRAN 变异阶段提供记忆管理功能

功能：
1. 记录成功的变异模式
2. 记录 Oracle 失败（潜在 Bug）
3. 增强变异 Prompt
4. 跨会话学习和优化
"""

import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import json


class MutationMemoryManager:
    """变异阶段的 Mem0 记忆管理器（使用 Qdrant）"""
    
    def __init__(
        self,
        user_id: str = "qtran_mutation",
        qdrant_host: str = None,
        qdrant_port: int = None
    ):
        """
        初始化变异记忆管理器
        
        Args:
            user_id: 用户标识（用于隔离不同数据库对的记忆）
            qdrant_host: Qdrant 服务器地址
            qdrant_port: Qdrant 端口
        """
        try:
            from mem0 import Memory
            
            # Qdrant 配置
            host = qdrant_host or os.getenv("QDRANT_HOST", "localhost")
            port = qdrant_port or int(os.getenv("QDRANT_PORT", "6333"))
            
            config = {
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "host": host,
                        "port": port,
                        "collection_name": "qtran_mutation_memories",
                    }
                },
                "llm": {
                    "provider": "openai",
                    "config": {
                        "model": "gpt-4o-mini",
                        "temperature": 0.1,
                    }
                },
                "embedder": {
                    "provider": "openai",
                    "config": {
                        "model": "text-embedding-3-small"
                    }
                }
            }
            
            self.memory = Memory.from_config(config)
            self.user_id = user_id
            self.session_start_time = None
            self.session_data = {
                "mutations_generated": 0,
                "mutations_successful": 0,
                "bugs_found": 0,
                "oracle_checks": 0,
                "search_times": [],
            }
            
        except ImportError as e:
            raise ImportError(
                f"Mem0 not installed. Please run: pip install mem0ai qdrant-client\n{e}"
            )
    
    def start_session(self, db_type: str, oracle_type: str, sql_type: str = "unknown"):
        """
        开始变异会话
        
        Args:
            db_type: 数据库类型（如 mongodb, postgres）
            oracle_type: Oracle 类型（如 tlp, norec, semantic）
            sql_type: SQL 类型（如 SELECT, UPDATE）
        """
        self.session_start_time = time.time()
        self.session_data["db_type"] = db_type
        self.session_data["oracle_type"] = oracle_type
        self.session_data["sql_type"] = sql_type
        
        # 记录会话开始
        session_info = (
            f"Started mutation session for {db_type} using {oracle_type} oracle. "
            f"SQL type: {sql_type}. Timestamp: {datetime.now().isoformat()}"
        )
        
        try:
            self.memory.add(
                session_info,
                user_id=self.user_id,
                metadata={
                    "type": "session_start",
                    "db_type": db_type,
                    "oracle_type": oracle_type,
                    "sql_type": sql_type,
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            print(f"⚠️ Failed to record session start: {e}")
    
    def record_successful_mutation(
        self,
        original_sql: str,
        mutated_sqls: List[str],
        oracle_type: str,
        db_type: str,
        mutation_strategy: str = None,
        execution_time: float = None
    ):
        """
        记录成功的变异模式
        
        Args:
            original_sql: 原始 SQL
            mutated_sqls: 变异后的 SQL 列表
            oracle_type: Oracle 类型
            db_type: 数据库类型
            mutation_strategy: 变异策略
            execution_time: 执行时间（秒）
        """
        self.session_data["mutations_generated"] += len(mutated_sqls)
        self.session_data["mutations_successful"] += 1
        
        # 提取 SQL 特征
        features = self._extract_sql_features(original_sql)
        
        # 构建记忆内容（转义大括号）
        mutation_count = len(mutated_sqls)
        mutations_preview = mutated_sqls[0] if mutated_sqls else "N/A"
        
        # 转义 MongoDB Shell 语法中的大括号
        original_escaped = original_sql.replace('{', '{{').replace('}', '}}')
        mutations_escaped = mutations_preview.replace('{', '{{').replace('}', '}}')
        
        memory_content = (
            f"Successfully generated {mutation_count} mutations for {db_type} using {oracle_type} oracle. "
            f"Original: {original_escaped}... "
            f"Example mutation: {mutations_escaped}... "
            f"Strategy: {mutation_strategy or 'auto'}, "
            f"Features: {features}, "
            f"Execution time: {execution_time:.2f}s."
        )
        
        try:
            self.memory.add(
                memory_content,
                user_id=self.user_id,
                metadata={
                    "type": "successful_mutation",
                    "db_type": db_type,
                    "oracle_type": oracle_type,
                    "mutation_count": mutation_count,
                    "strategy": mutation_strategy or "auto",
                    "features": features,
                    "execution_time": execution_time,
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            print(f"⚠️ Failed to record successful mutation: {e}")
    
    def record_bug_pattern(
        self,
        original_sql: str,
        mutation_sql: str,
        bug_type: str,
        oracle_type: str,
        db_type: str,
        oracle_details: Dict[str, Any] = None
    ):
        """
        记录发现的 Bug 模式（Oracle 失败）
        
        Args:
            original_sql: 原始 SQL
            mutation_sql: 导致 Bug 的变异 SQL
            bug_type: Bug 类型
            oracle_type: Oracle 类型
            db_type: 数据库类型
            oracle_details: Oracle 检查详情
        """
        self.session_data["bugs_found"] += 1
        
        # 转义大括号
        original_escaped = original_sql.replace('{', '{{').replace('}', '}}')
        mutation_escaped = mutation_sql.replace('{', '{{').replace('}', '}}')
        details_str = json.dumps(oracle_details or {{}}).replace('{', '{{').replace('}', '}}')
        
        memory_content = (
            f"🐛 BUG FOUND in {db_type} with {oracle_type} oracle! "
            f"Type: {bug_type}. "
            f"Original: {original_escaped}... "
            f"Mutation: {mutation_escaped}... "
            f"Details: {details_str}"
        )
        
        try:
            self.memory.add(
                memory_content,
                user_id=self.user_id,
                metadata={
                    "type": "bug_pattern",
                    "bug_type": bug_type,
                    "db_type": db_type,
                    "oracle_type": oracle_type,
                    "details": oracle_details or {},
                    "timestamp": datetime.now().isoformat(),
                    "severity": "high"  # 所有 bug 都标记为高优先级
                }
            )
            print(f"🐛 Bug pattern recorded: {bug_type}")
        except Exception as e:
            print(f"⚠️ Failed to record bug pattern: {e}")
    
    def record_oracle_failure_pattern(
        self,
        original_sql: str,
        mutation_sql: str,
        failure_reason: str,
        oracle_type: str,
        db_type: str,
        expected_result: Any = None,
        actual_result: Any = None
    ):
        """
        记录 Oracle 检查失败的模式（可能的 Bug 或误报）
        
        Args:
            original_sql: 原始 SQL
            mutation_sql: 失败的变异 SQL
            failure_reason: 失败原因
            oracle_type: Oracle 类型
            db_type: 数据库类型
            expected_result: 期望结果
            actual_result: 实际结果
        """
        self.session_data["oracle_checks"] += 1
        
        # 转义大括号
        original_escaped = original_sql.replace('{', '{{').replace('}', '}}')
        mutation_escaped = mutation_sql.replace('{', '{{').replace('}', '}}')
        reason_escaped = str(failure_reason).replace('{', '{{').replace('}', '}}')
        
        memory_content = (
            f"Oracle check failed for {db_type} with {oracle_type}. "
            f"Reason: {reason_escaped}. "
            f"Original: {original_escaped}... "
            f"Mutation: {mutation_escaped}... "
            f"Expected vs Actual: {expected_result} vs {actual_result}"
        )
        
        try:
            self.memory.add(
                memory_content,
                user_id=self.user_id,
                metadata={
                    "type": "oracle_failure",
                    "oracle_type": oracle_type,
                    "db_type": db_type,
                    "failure_reason": failure_reason,
                    "expected": str(expected_result),
                    "actual": str(actual_result),
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            print(f"⚠️ Failed to record oracle failure: {e}")
    
    def get_relevant_patterns(
        self,
        query_sql: str,
        oracle_type: str,
        db_type: str,
        limit: int = 3
    ) -> List[Dict]:
        """
        获取相关的历史变异模式
        
        Args:
            query_sql: 查询 SQL
            oracle_type: Oracle 类型
            db_type: 数据库类型
            limit: 返回数量限制
        
        Returns:
            相关记忆列表
        """
        # 构建语义搜索查询
        search_query = (
            f"Successful mutation patterns for {db_type} database using {oracle_type} oracle, "
            f"similar to: {query_sql[:100]}"
        )
        
        start_time = time.time()
        try:
            memories = self.memory.search(
                search_query,
                user_id=self.user_id,
                limit=limit
            )
            
            search_time = time.time() - start_time
            self.session_data["search_times"].append(search_time)
            
            # 过滤：只返回成功的变异模式
            filtered = [
                m for m in memories
                if m.get("metadata", {}).get("type") == "successful_mutation"
            ]
            
            return filtered[:limit]
        
        except Exception as e:
            print(f"⚠️ Failed to search memories: {e}")
            return []
    
    def get_bug_patterns_to_avoid(
        self,
        query_sql: str,
        oracle_type: str,
        db_type: str,
        limit: int = 2
    ) -> List[Dict]:
        """
        获取应该避免的 Bug 模式
        
        Args:
            query_sql: 查询 SQL
            oracle_type: Oracle 类型
            db_type: 数据库类型
            limit: 返回数量限制
        
        Returns:
            Bug 模式列表
        """
        search_query = (
            f"Bug patterns in {db_type} with {oracle_type} oracle to avoid, "
            f"related to: {query_sql[:100]}"
        )
        
        try:
            memories = self.memory.search(
                search_query,
                user_id=self.user_id,
                limit=limit
            )
            
            # 过滤：只返回 bug 相关的记忆
            bugs = [
                m for m in memories
                if m.get("metadata", {}).get("type") in ["bug_pattern", "oracle_failure"]
            ]
            
            return bugs[:limit]
        
        except Exception as e:
            print(f"⚠️ Failed to search bug patterns: {e}")
            return []
    
    def build_enhanced_prompt(
        self,
        base_prompt: str,
        query_sql: str,
        oracle_type: str,
        db_type: str
    ) -> str:
        """
        使用历史记忆增强变异 Prompt
        
        Args:
            base_prompt: 基础 prompt
            query_sql: 待变异的 SQL
            oracle_type: Oracle 类型
            db_type: 数据库类型
        
        Returns:
            增强后的 prompt
        """
        # 获取相关模式和 bug 模式
        success_patterns = self.get_relevant_patterns(query_sql, oracle_type, db_type, limit=2)
        bug_patterns = self.get_bug_patterns_to_avoid(query_sql, oracle_type, db_type, limit=1)
        
        if not success_patterns and not bug_patterns:
            return base_prompt
        
        # 构建记忆上下文
        context = "\n\n## 📚 Historical Mutation Knowledge (from Mem0):\n"
        
        if success_patterns:
            context += "\n### ✅ Successful Patterns:\n"
            for i, pattern in enumerate(success_patterns, 1):
                memory_text = pattern.get('memory', '')
                metadata = pattern.get('metadata', {})
                
                # 转义记忆文本中的大括号
                memory_escaped = memory_text.replace('{', '{{').replace('}', '}}')
                
                context += f"{i}. {memory_escaped}\n"
                
                strategy = metadata.get('strategy', 'N/A')
                exec_time = metadata.get('execution_time', 'N/A')
                context += f"   (Strategy: {strategy}, Time: {exec_time}s)\n"
        
        if bug_patterns:
            context += "\n### ⚠️ Patterns to Avoid (Known Bugs):\n"
            for i, bug in enumerate(bug_patterns, 1):
                memory_text = bug.get('memory', '')
                memory_escaped = memory_text.replace('{', '{{').replace('}', '}}')
                
                context += f"{i}. {memory_escaped}\n"
        
        context += "\nPlease consider these patterns when generating mutations.\n"
        
        # 将上下文添加到 system_message 之后
        enhanced_prompt = base_prompt + context
        
        return enhanced_prompt
    
    def end_session(self, success: bool = True, summary: str = None):
        """
        结束变异会话
        
        Args:
            success: 是否成功
            summary: 总结信息
        """
        if self.session_start_time:
            session_duration = time.time() - self.session_start_time
            
            session_summary = (
                f"Mutation session ended. "
                f"Duration: {session_duration:.2f}s, "
                f"Generated: {self.session_data['mutations_generated']} mutations, "
                f"Successful: {self.session_data['mutations_successful']}, "
                f"Bugs found: {self.session_data['bugs_found']}, "
                f"Oracle checks: {self.session_data['oracle_checks']}. "
                f"Status: {'✅ Success' if success else '❌ Failed'}. "
                f"{summary or ''}"
            )
            
            try:
                self.memory.add(
                    session_summary,
                    user_id=self.user_id,
                    metadata={
                        "type": "session_end",
                        "success": success,
                        "duration": session_duration,
                        "stats": self.session_data.copy(),
                        "timestamp": datetime.now().isoformat()
                    }
                )
            except Exception as e:
                print(f"⚠️ Failed to record session end: {e}")
    
    def get_metrics_report(self) -> str:
        """获取性能指标报告"""
        search_times = self.session_data.get("search_times", [])
        avg_search = sum(search_times) / len(search_times) if search_times else 0
        
        total_mutations = self.session_data.get("mutations_generated", 0)
        successful = self.session_data.get("mutations_successful", 0)
        bugs = self.session_data.get("bugs_found", 0)
        
        report = f"""
=== Mem0 Mutation Performance Metrics ===
⏱️  Average search time: {avg_search:.3f}s
🔍 Total searches: {len(search_times)}
🧬 Mutations generated: {total_mutations}
✅ Successful patterns: {successful}
🐛 Bugs found: {bugs}
============================================
"""
        return report
    
    def _extract_sql_features(self, sql: str) -> Dict[str, Any]:
        """提取 SQL 特征"""
        import re
        
        sql_upper = sql.upper()
        
        features = {
            "has_join": "JOIN" in sql_upper,
            "has_where": "WHERE" in sql_upper,
            "has_aggregate": any(op in sql_upper for op in ["COUNT", "SUM", "AVG", "MAX", "MIN"]),
            "has_group_by": "GROUP BY" in sql_upper,
            "has_order_by": "ORDER BY" in sql_upper,
            "has_subquery": "SELECT" in sql_upper and "(" in sql,
        }
        
        # MongoDB 特定特征
        if any(op in sql for op in ["db.", "findOne", "find", "insertOne", "updateOne"]):
            features["is_mongodb_shell"] = True
            features["has_filter"] = "filter" in sql.lower() or "{" in sql
            features["has_projection"] = "projection" in sql.lower()
            features["has_sort"] = ".sort(" in sql
        else:
            features["is_mongodb_shell"] = False
        
        return features


class FallbackMutationMemoryManager:
    """降级模式的记忆管理器（当 Mem0 不可用时使用文件存储）"""
    
    def __init__(self, user_id: str = "qtran_mutation"):
        self.user_id = user_id
        self.session_start_time = None
        self.session_data = {
            "mutations_generated": 0,
            "mutations_successful": 0,
            "bugs_found": 0,
        }
        
        # 创建本地存储目录
        self.storage_dir = os.path.join(os.getcwd(), ".mem0_fallback", "mutation")
        os.makedirs(self.storage_dir, exist_ok=True)
        
        print("⚠️ Using fallback memory manager (file-based)")
    
    def start_session(self, db_type: str, oracle_type: str, sql_type: str = "unknown"):
        self.session_start_time = time.time()
        self.session_data["db_type"] = db_type
        self.session_data["oracle_type"] = oracle_type
    
    def record_successful_mutation(self, *args, **kwargs):
        self.session_data["mutations_successful"] += 1
    
    def record_bug_pattern(self, *args, **kwargs):
        self.session_data["bugs_found"] += 1
        # 记录到文件
        bug_file = os.path.join(self.storage_dir, "bugs.jsonl")
        try:
            with open(bug_file, "a") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "args": str(args),
                    "kwargs": {k: str(v) for k, v in kwargs.items()}
                }, f)
                f.write("\n")
        except Exception:
            pass
    
    def record_oracle_failure_pattern(self, *args, **kwargs):
        pass
    
    def get_relevant_patterns(self, *args, **kwargs) -> List[Dict]:
        return []
    
    def get_bug_patterns_to_avoid(self, *args, **kwargs) -> List[Dict]:
        return []
    
    def build_enhanced_prompt(self, base_prompt: str, *args, **kwargs) -> str:
        return base_prompt
    
    def end_session(self, success: bool = True, summary: str = None):
        pass
    
    def get_metrics_report(self) -> str:
        return f"""
=== Fallback Mode (No Mem0) ===
✅ Mutations successful: {self.session_data.get('mutations_successful', 0)}
🐛 Bugs found: {self.session_data.get('bugs_found', 0)}
===============================
"""

