"""
使用Mem0增强的变异模块
结合历史记忆和模式学习，提升变异质量和效率
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from mem0 import Memory
import re

class Mem0EnhancedMutateLLM:
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化Mem0增强的变异模块
        
        Args:
            config: 配置参数，包括mem0配置、数据库连接等
        """
        self.config = config or {}
        self.memory = Memory(config=self.config.get('mem0_config', {}))
        self.mutation_history = []
        self.oracle_failure_patterns = []
        
    def classify_sql_type(self, sql: str) -> str:
        """分类SQL类型"""
        sql_upper = sql.upper()
        if 'SELECT' in sql_upper:
            if 'JOIN' in sql_upper:
                return 'SELECT_JOIN'
            elif 'WHERE' in sql_upper:
                return 'SELECT_WHERE'
            else:
                return 'SELECT_SIMPLE'
        elif 'INSERT' in sql_upper:
            return 'INSERT'
        elif 'UPDATE' in sql_upper:
            return 'UPDATE'
        elif 'DELETE' in sql_upper:
            return 'DELETE'
        else:
            return 'OTHER'
    
    def extract_sql_features(self, sql: str) -> Dict[str, Any]:
        """提取SQL特征"""
        features = {
            'has_joins': bool(re.search(r'\bJOIN\b', sql, re.IGNORECASE)),
            'has_subqueries': bool(re.search(r'\([^)]*SELECT[^)]*\)', sql, re.IGNORECASE)),
            'has_aggregates': bool(re.search(r'\b(COUNT|SUM|AVG|MAX|MIN)\b', sql, re.IGNORECASE)),
            'has_group_by': bool(re.search(r'\bGROUP BY\b', sql, re.IGNORECASE)),
            'has_order_by': bool(re.search(r'\bORDER BY\b', sql, re.IGNORECASE)),
            'has_having': bool(re.search(r'\bHAVING\b', sql, re.IGNORECASE)),
            'complexity_score': len(sql.split()) / 10  # 简单的复杂度评分
        }
        return features
    
    def store_mutation_pattern(self, original_sql: str, mutated_sql: str, 
                             oracle_type: str, success_rate: float, 
                             db_type: str, execution_time: float = None):
        """存储成功的变异模式到记忆"""
        sql_type = self.classify_sql_type(original_sql)
        features = self.extract_sql_features(original_sql)
        
        pattern_info = {
            "sql_type": sql_type,
            "sql_features": features,
            "mutation_strategy": self._extract_mutation_strategy(original_sql, mutated_sql),
            "oracle_type": oracle_type,
            "db_type": db_type,
            "success_rate": success_rate,
            "execution_time": execution_time,
            "timestamp": datetime.now().isoformat()
        }
        
        # 存储到mem0
        memory_content = f"""
        成功变异模式:
        - SQL类型: {sql_type}
        - 数据库: {db_type}
        - 预言机: {oracle_type}
        - 成功率: {success_rate}
        - 变异策略: {pattern_info['mutation_strategy']}
        - 执行时间: {execution_time}ms
        """
        
        self.memory.add([
            {"role": "system", "content": memory_content}
        ])
        
        self.mutation_history.append(pattern_info)
    
    def store_oracle_failure(self, sql: str, mutation: str, failure_reason: str, 
                           oracle_type: str, db_type: str):
        """存储预言机检查失败的模式"""
        failure_info = {
            "sql_pattern": self._extract_sql_pattern(sql),
            "mutation_type": self._classify_mutation_type(sql, mutation),
            "failure_reason": failure_reason,
            "oracle_type": oracle_type,
            "db_type": db_type,
            "timestamp": datetime.now().isoformat()
        }
        
        memory_content = f"""
        预言机失败模式:
        - SQL模式: {failure_info['sql_pattern']}
        - 变异类型: {failure_info['mutation_type']}
        - 失败原因: {failure_reason}
        - 预言机: {oracle_type}
        - 数据库: {db_type}
        """
        
        self.memory.add([
            {"role": "system", "content": memory_content}
        ])
        
        self.oracle_failure_patterns.append(failure_info)
    
    def get_relevant_mutation_patterns(self, sql: str, oracle_type: str, 
                                     db_type: str, limit: int = 5) -> List[Dict]:
        """检索相关的历史变异模式"""
        sql_type = self.classify_sql_type(sql)
        features = self.extract_sql_features(sql)
        
        # 构建搜索查询
        search_queries = [
            f"SQL类型: {sql_type} 预言机: {oracle_type}",
            f"数据库: {db_type} 成功率高的变异",
            f"SQL特征: {json.dumps(features)}"
        ]
        
        relevant_patterns = []
        for query in search_queries:
            results = self.memory.search(query, limit=limit)
            relevant_patterns.extend(results)
        
        # 去重并按相关性排序
        unique_patterns = []
        seen = set()
        for pattern in relevant_patterns:
            pattern_id = pattern.get('id', '')
            if pattern_id not in seen:
                unique_patterns.append(pattern)
                seen.add(pattern_id)
        
        return unique_patterns[:limit]
    
    def get_failure_patterns_to_avoid(self, sql: str, oracle_type: str, 
                                    db_type: str) -> List[Dict]:
        """获取应该避免的失败模式"""
        sql_type = self.classify_sql_type(sql)
        
        search_query = f"失败模式 SQL类型: {sql_type} 预言机: {oracle_type} 数据库: {db_type}"
        failure_patterns = self.memory.search(search_query, limit=3)
        
        return failure_patterns
    
    def build_enhanced_prompt(self, original_sql: str, oracle_type: str, 
                            db_type: str, system_message: str) -> str:
        """构建增强的提示词，包含历史记忆"""
        # 获取相关模式
        relevant_patterns = self.get_relevant_mutation_patterns(original_sql, oracle_type, db_type)
        failure_patterns = self.get_failure_patterns_to_avoid(original_sql, oracle_type, db_type)
        
        # 构建上下文信息
        context_info = self._build_context_info(relevant_patterns, failure_patterns)
        
        # 增强系统消息
        enhanced_system_message = f"""
        {system_message}
        
        === 历史变异经验 ===
        {context_info}
        
        === 注意事项 ===
        基于历史数据，请特别注意：
        1. 避免重复已知的失败模式
        2. 优先使用成功率高的变异策略
        3. 考虑数据库特定的优化建议
        """
        
        return enhanced_system_message
    
    def _extract_mutation_strategy(self, original: str, mutated: str) -> str:
        """提取变异策略"""
        # 简单的策略识别
        if 'JOIN' in original.upper() and 'EXISTS' in mutated.upper():
            return 'JOIN_TO_EXISTS'
        elif 'IN' in original.upper() and 'EXISTS' in mutated.upper():
            return 'IN_TO_EXISTS'
        elif 'BETWEEN' in original.upper() and 'AND' in mutated.upper():
            return 'BETWEEN_TO_AND'
        elif len(mutated) > len(original) * 1.5:
            return 'REDUNDANT_CONDITIONS'
        else:
            return 'LOGICAL_EQUIVALENCE'
    
    def _extract_sql_pattern(self, sql: str) -> str:
        """提取SQL模式"""
        # 简化版模式提取
        if 'JOIN' in sql.upper():
            return 'JOIN_QUERY'
        elif 'WHERE' in sql.upper():
            return 'WHERE_QUERY'
        elif 'GROUP BY' in sql.upper():
            return 'AGGREGATE_QUERY'
        else:
            return 'SIMPLE_QUERY'
    
    def _classify_mutation_type(self, original: str, mutated: str) -> str:
        """分类变异类型"""
        return self._extract_mutation_strategy(original, mutated)
    
    def _build_context_info(self, relevant_patterns: List[Dict], 
                           failure_patterns: List[Dict]) -> str:
        """构建上下文信息"""
        context_parts = []
        
        if relevant_patterns:
            context_parts.append("成功的变异模式:")
            for pattern in relevant_patterns[:3]:
                content = pattern.get('content', '')
                if '成功率' in content:
                    context_parts.append(f"- {content}")
        
        if failure_patterns:
            context_parts.append("\n应避免的模式:")
            for pattern in failure_patterns[:2]:
                content = pattern.get('content', '')
                if '失败原因' in content:
                    context_parts.append(f"- {content}")
        
        return "\n".join(context_parts)
    
    def analyze_mutation_performance(self) -> Dict[str, Any]:
        """分析变异性能"""
        if not self.mutation_history:
            return {"message": "暂无历史数据"}
        
        # 统计成功率
        success_rates = [h['success_rate'] for h in self.mutation_history if 'success_rate' in h]
        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0
        
        # 统计最有效的策略
        strategies = {}
        for history in self.mutation_history:
            strategy = history.get('mutation_strategy', 'unknown')
            if strategy not in strategies:
                strategies[strategy] = []
            strategies[strategy].append(history.get('success_rate', 0))
        
        strategy_performance = {
            strategy: sum(rates) / len(rates) 
            for strategy, rates in strategies.items()
        }
        
        return {
            "total_mutations": len(self.mutation_history),
            "average_success_rate": avg_success_rate,
            "strategy_performance": strategy_performance,
            "failure_patterns_count": len(self.oracle_failure_patterns)
        }
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        try:
            # 获取所有记忆
            all_memories = self.memory.get_all()
            return {
                "total_memories": len(all_memories),
                "mutation_patterns": len(self.mutation_history),
                "failure_patterns": len(self.oracle_failure_patterns)
            }
        except Exception as e:
            return {"error": str(e)}


# 使用示例
def example_usage():
    """使用示例"""
    # 初始化增强变异模块
    config = {
        'mem0_config': {
            'vector_store': {
                'provider': 'chroma',
                'config': {
                    'path': './mem0_storage'
                }
            }
        }
    }
    
    enhanced_mutator = Mem0EnhancedMutateLLM(config)
    
    # 模拟变异过程
    original_sql = "SELECT * FROM users WHERE age > 18"
    mutated_sql = "SELECT * FROM users WHERE age >= 19"
    oracle_type = "norec"
    db_type = "postgres"
    
    # 存储成功的变异模式
    enhanced_mutator.store_mutation_pattern(
        original_sql, mutated_sql, oracle_type, 0.95, db_type, 150.5
    )
    
    # 获取增强的提示词
    system_message = "你是一个SQL变异专家..."
    enhanced_prompt = enhanced_mutator.build_enhanced_prompt(
        original_sql, oracle_type, db_type, system_message
    )
    
    print("增强的提示词:")
    print(enhanced_prompt)
    
    # 分析性能
    performance = enhanced_mutator.analyze_mutation_performance()
    print("\n性能分析:")
    print(json.dumps(performance, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    example_usage()

