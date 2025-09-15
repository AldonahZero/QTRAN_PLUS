import json
import os
from collections import defaultdict

class MetamorphicRelationMiner:
    """
    从提取的 API 模式中挖掘蜕变关系。
    v4 产品版：将专家知识作为独立于数据发现的核心规则进行注入，确保关键关系的建立。
    """
    def __init__(self, patterns_path, output_dir="NoSQLFeatureKnowledgeBase/MongoDB"):
        self.patterns_path = patterns_path
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def load_patterns(self):
        with open(self.patterns_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def mine_relations(self):
        print("开始挖掘蜕变关系 (v4 产品版)...")
        patterns = self.load_patterns()
        
        knowledge_graph = {
            "operators": defaultdict(lambda: {
                "equivalent_forms": [],
                "used_with_methods": set(),
                "properties": [],
                "relations": [] 
            }),
            "methods": defaultdict(lambda: {
                "signatures": set()
            })
        }

        # 步骤 1: 从数据中发现模式和使用场景
        print("步骤 1: 从数据中发现操作符和使用场景...")
        self._mine_from_data(patterns, knowledge_graph)

        # 步骤 2: 注入不依赖于数据发现的、确定性的专家知识
        print("步骤 2: 注入核心专家知识...")
        self._inject_expert_knowledge(knowledge_graph)
        
        # 步骤 3: 后处理和清理
        print("步骤 3: 进行后处理和清理...")
        for op_data in knowledge_graph["operators"].values():
            op_data["used_with_methods"] = sorted(list(op_data["used_with_methods"]))
        
        # 删除没有信息的空操作符条目
        cleaned_operators = {op: data for op, data in knowledge_graph["operators"].items() if data.get("used_with_methods") or data.get("equivalent_forms") or data.get("properties") or data.get("relations")}
        knowledge_graph["operators"] = cleaned_operators

        output_path = os.path.join(self.output_dir, "mongodb_knowledge_graph.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(knowledge_graph, f, indent=4)
            
        print("\n挖掘完成！")
        print(f"最终知识图谱已保存至: {output_path}")

    def _mine_from_data(self, patterns, kg):
        """包含所有依赖于从数据中发现模式的规则。"""
        for pattern in patterns:
            method = pattern.get('method')
            if not method: continue

            operators = pattern.get('operators', [])
            for op in operators:
                kg["operators"][op]["used_with_methods"].add(method)

            if method == 'find' and pattern.get('arguments'):
                query_filter = pattern['arguments'][0]
                if not isinstance(query_filter, dict): continue
                
                has_implicit_eq = any(not isinstance(v, dict) and not k.startswith('$') for k, v in query_filter.items())
                if has_implicit_eq:
                    kg["operators"]["$eq"]["used_with_methods"].add(method)
                    form = "implicit_equality"
                    if form not in kg["operators"]["$eq"]["equivalent_forms"]:
                        kg["operators"]["$eq"]["equivalent_forms"].append(form)

                top_level_keys = [k for k in query_filter.keys() if not k.startswith('$')]
                if len(top_level_keys) > 1:
                    kg["operators"]["$and"]["used_with_methods"].add(method)
                    form = "implicit_conjunction"
                    if form not in kg["operators"]["$and"]["equivalent_forms"]:
                        kg["operators"]["$and"]["equivalent_forms"].append(form)

                self._find_in_vs_eq_relation_recursive(query_filter, kg)

    def _find_in_vs_eq_relation_recursive(self, doc, kg):
        if isinstance(doc, dict):
            for key, value in doc.items():
                if key == "$in" and isinstance(value, list) and len(value) == 1:
                    relation = {"type": "equivalent_to", "operator": "$eq", "condition": "when array has one element"}
                    if relation not in kg["operators"]["$in"]["relations"]:
                        kg["operators"]["$in"]["relations"].append(relation)
                elif isinstance(value, (dict, list)):
                    self._find_in_vs_eq_relation_recursive(value, kg)
        elif isinstance(doc, list):
            for item in doc:
                self._find_in_vs_eq_relation_recursive(item, kg)

    def _inject_expert_knowledge(self, kg):
        """
        注入确定性的专家规则。这些规则不依赖于是否在数据中发现了特定操作符（如 $not）。
        """
        all_ops_found = set(kg["operators"].keys())

        # 规则 5: $nin <=> $not($in)
        if "$nin" in all_ops_found:
            # 这个规则仍然依赖于发现 $nin, 这是正确的
            kg["operators"]["$not"] # 确保 $not 存在于图中
            kg["operators"]["$in"]  # 确保 $in 存在于图中
            relation = {"type": "equivalent_to", "construct": {"operator": "$not", "nested_operator": "$in"}}
            if relation not in kg["operators"]["$nin"]["relations"]:
                kg["operators"]["$nin"]["relations"].append(relation)

        # 规则 6: 逆运算关系 - **逻辑修正**
        op_inverse_map = {
            "$gt": "$lte", "$lt": "$gte",
            "$gte": "$lt", "$lte": "$gt",
            "$ne": "$eq",  "$eq": "$ne"
        }
        # 不再检查 $not 是否存在，而是检查关系的两端是否存在
        for op, inverse_op in op_inverse_map.items():
            if op in all_ops_found and inverse_op in all_ops_found:
                kg["operators"]["$not"] # 关系本身就意味着 $not 的存在
                # 添加双向关系
                relation1 = {"type": "inverse_of", "via_operator": "$not", "target_operator": inverse_op}
                if relation1 not in kg["operators"][op]["relations"]:
                     kg["operators"][op]["relations"].append(relation1)
                relation2 = {"type": "inverse_of", "via_operator": "$not", "target_operator": op}
                if relation2 not in kg["operators"][inverse_op]["relations"]:
                     kg["operators"][inverse_op]["relations"].append(relation2)

        # 规则 7: 逻辑操作符的交换律
        for op in ["$and", "$or"]:
            if op in all_ops_found:
                prop = "commutative"
                if prop not in kg["operators"][op]["properties"]:
                    kg["operators"][op]["properties"].append(prop)
        
        # 规则 8: 德摩根定律 - **逻辑修正**
        # 只要 $and 和 $or 都被发现了，就可以推断这个定律
        if "$and" in all_ops_found and "$or" in all_ops_found:
            kg["operators"]["$not"] # 定律本身意味着 $not 的存在
            relation = {"type": "equivalent_to", "law": "De Morgan's Law", "construct": {"operator": "$not", "nested_operator": "$or"}}
            if relation not in kg["operators"]["$and"]["relations"]:
                kg["operators"]["$and"]["relations"].append(relation)
            relation_rev = {"type": "equivalent_to", "law": "De Morgan's Law", "construct": {"operator": "$not", "nested_operator": "$and"}}
            if relation_rev not in kg["operators"]["$or"]["relations"]:
                kg["operators"]["$or"]["relations"].append(relation_rev)

if __name__ == '__main__':
    patterns_file = "NoSQLFeatureKnowledgeBase/MongoDB/extracted_api_patterns.json"
    if os.path.exists(patterns_file):
        miner = MetamorphicRelationMiner(patterns_path=patterns_file)
        miner.mine_relations()
    else:
        print(f"错误: 未找到 API 模式文件 '{patterns_file}'。请先运行 APIExtractor.py。")

