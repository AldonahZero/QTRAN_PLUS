import json
import os
from collections import defaultdict

class MetamorphicRelationMiner:
    """
    从提取的 API 模式中挖掘蜕变关系。
    例如，发现两种不同的查询语法实际上是等价的。
    """
    def __init__(self, patterns_path, output_dir="NoSQLFeatureKnowledgeBase/MongoDB"):
        """
        初始化关系挖掘器。

        Args:
            patterns_path (str): 包含提取出的 API 模式的 JSON 文件路径。
            output_dir (str): 保存最终知识库的目录。
        """
        self.patterns_path = patterns_path
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def load_patterns(self):
        """加载 API 模式。"""
        with open(self.patterns_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def mine_relations(self):
        """
        执行关系挖掘并构建知识库。
        """
        print("开始挖掘蜕变关系...")
        patterns = self.load_patterns()
        
        knowledge_graph = {
            "operators": defaultdict(lambda: {"equivalent_to": [], "used_with_methods": set()})
        }

        # 应用一系列挖掘规则
        self._mine_implicit_equality(patterns, knowledge_graph)
        self._mine_operator_method_associations(patterns, knowledge_graph)
        
        # 将集合转换为列表以便JSON序列化
        for op_data in knowledge_graph["operators"].values():
            op_data["used_with_methods"] = list(op_data["used_with_methods"])

        output_path = os.path.join(self.output_dir, "mongodb_knowledge_graph.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(knowledge_graph, f, indent=4)
            
        print("挖掘完成！")
        print(f"知识图谱已保存至: {output_path}")

    def _mine_implicit_equality(self, patterns, kg):
        """
        规则 1: 挖掘隐式与显式相等查询之间的关系。
        db.coll.find({ "field": "value" }) 等价于 db.coll.find({ "field": { "$eq": "value" } })
        """
        for pattern in patterns:
            if pattern['method'] == 'find' and pattern['arguments']:
                query_filter = pattern['arguments'][0]
                if not isinstance(query_filter, dict): continue
                
                for field, value in query_filter.items():
                    # 如果值不是一个字典 (即不包含操作符), 那么它就是一个隐式相等查询
                    if not isinstance(value, dict):
                        # 我们发现了一个隐式相等查询
                        # 在知识图谱中记录 $eq 操作符
                        eq_op_data = kg["operators"]["$eq"]
                        if "implicit_form" not in eq_op_data["equivalent_to"]:
                            eq_op_data["equivalent_to"].append("implicit_form")
    
    def _mine_operator_method_associations(self, patterns, kg):
        """
        规则 2: 记录哪些操作符与哪些方法一起使用。
        """
        for pattern in patterns:
            method = pattern['method']
            operators = pattern.get('operators', [])
            for op in operators:
                kg["operators"][op]["used_with_methods"].add(method)


if __name__ == '__main__':
    patterns_file = "NoSQLFeatureKnowledgeBase/MongoDB/extracted_api_patterns.json"
    if os.path.exists(patterns_file):
        miner = MetamorphicRelationMiner(patterns_path=patterns_file)
        miner.mine_relations()
    else:
        print(f"错误: 未找到 API 模式文件 '{patterns_file}'。请先运行 APIExtractor.py。")
