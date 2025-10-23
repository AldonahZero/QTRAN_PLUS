"""
Mem0 记忆管理适配器：用于翻译阶段的跨会话知识累积

功能概述：
- 记录成功的翻译案例和错误修正模式
- 检索相关历史知识增强 prompt
- 支持记忆衰减和跨数据库共享

使用示例：
    manager = TransferMemoryManager(user_id="qtran_redis_to_mongodb")
    manager.start_session(origin_db="redis", target_db="mongodb", molt="semantic")
    
    # 增强 prompt
    enhanced_prompt = manager.build_enhanced_prompt(base_prompt, sql, "redis", "mongodb")
    
    # 记录成功案例
    manager.record_successful_translation(origin_sql, target_sql, "redis", "mongodb", iterations=2)
"""

import os
import json
from typing import Dict, List, Optional, Any
import time
from datetime import datetime

# 可选引入 Mem0（仅当启用时才需要）
try:
    from mem0 import Memory
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    Memory = None


class TransferMemoryManager:
    """翻译阶段的 Mem0 记忆管理器"""
    
    def __init__(self, user_id: str = "qtran_transfer", enable_metrics: bool = True):
        """
        初始化记忆管理器
        
        Args:
            user_id: 用户标识，用于隔离不同实验的记忆
            enable_metrics: 是否启用性能指标收集
        """
        if not MEM0_AVAILABLE:
            raise ImportError(
                "Mem0 is not installed. Please install it with: pip install mem0ai"
            )
        
        # 配置 Mem0
        config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "host": os.environ.get("QDRANT_HOST", "localhost"),
                    "port": int(os.environ.get("QDRANT_PORT", 6333)),
                    "collection_name": "qtran_transfer_memory"
                }
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": os.environ.get("OPENAI_MEMORY_MODEL", "gpt-4o-mini"),
                    "temperature": 0.2,
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small"
                }
            }
        }
        
        try:
            self.memory = Memory.from_config(config)
        except Exception as e:
            print(f"⚠️ Failed to initialize Mem0 with Qdrant, falling back to in-memory mode: {e}")
            # 回退到内存模式（开发/测试用）
            config["vector_store"] = {
                "provider": "chroma",
                "config": {
                    "collection_name": "qtran_transfer_memory",
                    "path": ".mem0_db"
                }
            }
            self.memory = Memory.from_config(config)
        
        self.user_id = user_id
        self.session_id = None
        self.enable_metrics = enable_metrics
        
        if enable_metrics:
            self.metrics = {
                "search_times": [],
                "add_times": [],
                "hits": []
            }
    
    def start_session(self, origin_db: str, target_db: str, molt: str) -> str:
        """
        开启新的翻译会话
        
        Args:
            origin_db: 源数据库
            target_db: 目标数据库
            molt: 测试策略(norec/tlp/semantic等)
        
        Returns:
            session_id: 会话标识
        """
        import uuid
        self.session_id = f"{origin_db}_to_{target_db}_{molt}_{uuid.uuid4().hex[:8]}"
        
        # 记录会话开始
        message = (
            f"Started translation session from {origin_db} to {target_db} "
            f"using {molt} strategy"
        )
        
        try:
            self.memory.add(
                message,
                user_id=self.user_id,
                metadata={
                    "type": "session_start",
                    "origin_db": origin_db,
                    "target_db": target_db,
                    "molt": molt,
                    "session_id": self.session_id,
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            print(f"⚠️ Failed to add session start memory: {e}")
        
        return self.session_id
    
    def record_successful_translation(
        self,
        origin_sql: str,
        target_sql: str,
        origin_db: str,
        target_db: str,
        iterations: int,
        features: List[str] = None
    ):
        """
        记录成功的翻译案例
        
        Args:
            origin_sql: 源 SQL
            target_sql: 目标 SQL
            origin_db: 源数据库
            target_db: 目标数据库
            iterations: 迭代次数
            features: 涉及的特征列表
        """
        start_time = time.time()
        
        # 截断过长的 SQL 以避免存储过大
        origin_snippet = origin_sql[:200] if len(origin_sql) > 200 else origin_sql
        target_snippet = target_sql[:200] if len(target_sql) > 200 else target_sql
        
        message = (
            f"Successfully translated SQL from {origin_db} to {target_db} "
            f"in {iterations} iterations. "
            f"Original: {origin_snippet}{'...' if len(origin_sql) > 200 else ''} "
            f"Translated: {target_snippet}{'...' if len(target_sql) > 200 else ''}"
        )
        
        if features:
            message += f" Features: {', '.join(features[:5])}"  # 最多记录5个特征
        
        try:
            self.memory.add(
                message,
                user_id=self.user_id,
                metadata={
                    "type": "successful_translation",
                    "origin_db": origin_db,
                    "target_db": target_db,
                    "iterations": iterations,
                    "features": features or [],
                    "session_id": self.session_id,
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            print(f"⚠️ Failed to record successful translation: {e}")
        
        if self.enable_metrics:
            self.metrics["add_times"].append(time.time() - start_time)
    
    def record_error_fix(
        self,
        error_message: str,
        fix_sql: str,
        origin_db: str,
        target_db: str,
        failed_sql: str = None
    ):
        """
        记录错误及其修正方案
        
        Args:
            error_message: 错误信息
            fix_sql: 修正后的 SQL
            origin_db: 源数据库
            target_db: 目标数据库
            failed_sql: 失败的 SQL
        """
        start_time = time.time()
        
        # 截断错误信息和 SQL
        error_snippet = error_message[:300] if len(error_message) > 300 else error_message
        fix_snippet = fix_sql[:200] if len(fix_sql) > 200 else fix_sql
        
        message = (
            f"Fixed error in {target_db}: {error_snippet}{'...' if len(error_message) > 300 else ''}. "
            f"Solution: {fix_snippet}{'...' if len(fix_sql) > 200 else ''}"
        )
        
        try:
            self.memory.add(
                message,
                user_id=self.user_id,
                metadata={
                    "type": "error_fix",
                    "origin_db": origin_db,
                    "target_db": target_db,
                    "error_message": error_message[:500],  # 限制长度
                    "fix_sql": fix_sql[:500],
                    "session_id": self.session_id,
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            print(f"⚠️ Failed to record error fix: {e}")
        
        if self.enable_metrics:
            self.metrics["add_times"].append(time.time() - start_time)
    
    def get_relevant_memories(
        self,
        query_sql: str,
        origin_db: str,
        target_db: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        检索相关的历史记忆
        
        Args:
            query_sql: 查询 SQL
            origin_db: 源数据库
            target_db: 目标数据库
            limit: 返回记忆数量
        
        Returns:
            相关记忆列表
        """
        start_time = time.time()
        
        # 构建查询字符串
        query_snippet = query_sql[:300] if len(query_sql) > 300 else query_sql
        query = (
            f"Translation from {origin_db} to {target_db}. "
            f"SQL: {query_snippet}"
        )
        
        try:
            memories = self.memory.search(
                query=query,
                user_id=self.user_id,
                limit=limit
            )
            
            if self.enable_metrics:
                self.metrics["search_times"].append(time.time() - start_time)
                self.metrics["hits"].append(1 if memories else 0)
            
            return memories
        except Exception as e:
            print(f"⚠️ Failed to search memories: {e}")
            return []
    
    def build_enhanced_prompt(
        self,
        base_prompt: str,
        query_sql: str,
        origin_db: str,
        target_db: str
    ) -> str:
        """
        使用历史记忆增强 prompt
        
        Args:
            base_prompt: 基础 prompt
            query_sql: 待翻译的 SQL
            origin_db: 源数据库
            target_db: 目标数据库
        
        Returns:
            增强后的 prompt
        """
        memories = self.get_relevant_memories(query_sql, origin_db, target_db, limit=3)
        
        if not memories:
            return base_prompt
        
        # 构建记忆上下文
        memory_context = "\n\n## 📚 Relevant Historical Knowledge (from Mem0):\n"
        memory_context += "(These are successful patterns from previous translations)\n\n"
        
        for i, mem in enumerate(memories, 1):
            memory_text = mem.get('memory', '')
            metadata = mem.get('metadata', {})
            mem_type = metadata.get('type', 'unknown')
            
            # ⚠️ 关键修复：转义记忆文本中的大括号，避免被 Python format() 误解析
            # MongoDB Shell 语法如 { _id: "key" } 会被当作占位符
            memory_text_escaped = memory_text.replace('{', '{{').replace('}', '}}')
            
            memory_context += f"### Memory {i} [{mem_type}]:\n"
            memory_context += f"{memory_text_escaped}\n"
            
            # 添加元数据提示
            if mem_type == 'successful_translation':
                iterations = metadata.get('iterations', 'N/A')
                memory_context += f"(Completed in {iterations} iterations)\n"
            elif mem_type == 'error_fix':
                memory_context += f"(Common error fix pattern)\n"
            
            memory_context += "\n"
        
        # 在特征知识部分后插入记忆上下文
        # 查找插入位置（在 feature_knowledge 之后，examples 之前）
        if "{feature_knowledge}" in base_prompt:
            enhanced_prompt = base_prompt.replace(
                "{feature_knowledge}",
                "{feature_knowledge}" + memory_context
            )
        else:
            # 如果没有 feature_knowledge 占位符，在 examples 前插入
            if "{examples}" in base_prompt:
                enhanced_prompt = base_prompt.replace(
                    "{examples}",
                    memory_context + "{examples}"
                )
            else:
                # 作为最后手段，添加到末尾
                enhanced_prompt = memory_context + base_prompt
        
        return enhanced_prompt
    
    def end_session(self, success: bool, final_result: str = None):
        """
        结束翻译会话
        
        Args:
            success: 是否成功
            final_result: 最终结果
        """
        status = "successfully" if success else "unsuccessfully"
        
        result_snippet = ""
        if final_result:
            result_snippet = final_result[:150] if len(final_result) > 150 else final_result
            result_snippet = f". Final result: {result_snippet}{'...' if len(final_result) > 150 else ''}"
        
        message = f"Ended translation session {self.session_id} {status}{result_snippet}"
        
        try:
            self.memory.add(
                message,
                user_id=self.user_id,
                metadata={
                    "type": "session_end",
                    "session_id": self.session_id,
                    "success": success,
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            print(f"⚠️ Failed to add session end memory: {e}")
        
        self.session_id = None
    
    def get_metrics_report(self) -> str:
        """
        生成性能指标报告
        
        Returns:
            格式化的指标报告
        """
        if not self.enable_metrics:
            return "Metrics collection is disabled"
        
        report = "\n=== Mem0 Performance Metrics ===\n"
        
        if self.metrics["search_times"]:
            avg_search = sum(self.metrics["search_times"]) / len(self.metrics["search_times"])
            report += f"⏱️  Average search time: {avg_search:.3f}s\n"
            report += f"🔍 Total searches: {len(self.metrics['search_times'])}\n"
        
        if self.metrics["add_times"]:
            avg_add = sum(self.metrics["add_times"]) / len(self.metrics["add_times"])
            report += f"⏱️  Average add time: {avg_add:.3f}s\n"
            report += f"💾 Total additions: {len(self.metrics['add_times'])}\n"
        
        if self.metrics["hits"]:
            hit_rate = sum(self.metrics["hits"]) / len(self.metrics["hits"])
            report += f"🎯 Memory hit rate: {hit_rate:.1%}\n"
        
        report += "================================\n"
        return report


class FallbackMemoryManager:
    """
    当 Mem0 不可用时的降级实现（基于文件的简单记忆）
    仅用于开发/测试，不推荐生产使用
    """
    
    def __init__(self, user_id: str = "qtran_transfer", storage_dir: str = ".mem0_fallback"):
        self.user_id = user_id
        self.storage_dir = storage_dir
        self.session_id = None
        os.makedirs(storage_dir, exist_ok=True)
        print("⚠️ Using fallback memory manager (file-based)")
    
    def start_session(self, origin_db: str, target_db: str, molt: str) -> str:
        import uuid
        self.session_id = f"{origin_db}_to_{target_db}_{molt}_{uuid.uuid4().hex[:8]}"
        return self.session_id
    
    def record_successful_translation(self, origin_sql, target_sql, origin_db, target_db, iterations, features=None):
        # 简单的文件追加
        filepath = os.path.join(self.storage_dir, f"{self.user_id}_success.jsonl")
        with open(filepath, 'a', encoding='utf-8') as f:
            json.dump({
                "origin_sql": origin_sql[:200],
                "target_sql": target_sql[:200],
                "origin_db": origin_db,
                "target_db": target_db,
                "iterations": iterations,
                "features": features,
                "timestamp": datetime.now().isoformat()
            }, f)
            f.write('\n')
    
    def record_error_fix(self, error_message, fix_sql, origin_db, target_db, failed_sql=None):
        filepath = os.path.join(self.storage_dir, f"{self.user_id}_errors.jsonl")
        with open(filepath, 'a', encoding='utf-8') as f:
            json.dump({
                "error": error_message[:300],
                "fix_sql": fix_sql[:200],
                "origin_db": origin_db,
                "target_db": target_db,
                "timestamp": datetime.now().isoformat()
            }, f)
            f.write('\n')
    
    def get_relevant_memories(self, query_sql, origin_db, target_db, limit=5):
        # 返回空列表（降级模式不支持语义搜索）
        return []
    
    def build_enhanced_prompt(self, base_prompt, query_sql, origin_db, target_db):
        # 降级模式不增强 prompt
        return base_prompt
    
    def end_session(self, success, final_result=None):
        self.session_id = None
    
    def get_metrics_report(self):
        return "Fallback mode: metrics not available"

