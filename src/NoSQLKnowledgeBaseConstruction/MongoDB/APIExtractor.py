import json
import re
import os
from bson import json_util # 使用 bson 库来处理更复杂的 BSON/JSON 结构

class APIExtractor:
    """
    从原始代码片段中提取结构化的 API 模式。
    它能识别出方法调用、操作符和查询结构。
    """
    def __init__(self, snippets_path, output_dir="NoSQLFeatureKnowledgeBase/MongoDB"):
        """
        初始化提取器。

        Args:
            snippets_path (str): 包含代码片段的 JSON 文件路径。
            output_dir (str): 保存提取出的 API 模式的目录。
        """
        self.snippets_path = snippets_path
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
        # 定义用于匹配 MongoDB 操作的正则表达式
        # 例如: db.collection.find({...})
        self.mongo_pattern = re.compile(
            r"db\.([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\((.*?)\)", 
            re.DOTALL
        )

    def load_snippets(self):
        """从文件加载代码片段。"""
        with open(self.snippets_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def extract_patterns(self):
        """
        执行提取过程并保存结果。
        """
        print("开始提取 API 模式...")
        snippets = self.load_snippets()
        extracted_apis = []

        for snippet in snippets:
            code = snippet['code']
            matches = self.mongo_pattern.finditer(code)
            for match in matches:
                collection = match.group(1)
                method = match.group(2)
                args_str = match.group(3).strip()

                try:
                    # 我们需要处理非标准JSON，例如JavaScript对象字面量
                    # 一个策略是替换单引号为双引号，并移除尾随逗号
                    # BSON 库的 json_util 更强大，但仍可能失败
                    args_str_cleaned = self._cleanup_js_object_str(args_str)
                    args = json_util.loads(f'[{args_str_cleaned}]') # 包裹在数组中处理多个参数
                    
                    api_call = {
                        "collection": collection,
                        "method": method,
                        "arguments": args,
                        "operators": self._find_operators(args),
                        "metadata": {
                            "source_url": snippet["source_url"],
                            "description": snippet["description"]
                        }
                    }
                    extracted_apis.append(api_call)
                except Exception as e:
                    # print(f"解析参数失败: {args_str} -> {e}")
                    pass
        
        output_path = os.path.join(self.output_dir, "extracted_api_patterns.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(extracted_apis, f, indent=4, default=str) # 使用 default=str 处理无法序列化的对象
            
        print(f"提取完成！总共找到 {len(extracted_apis)} 个 API 调用模式。")
        print(f"数据已保存至: {output_path}")
        return extracted_apis

    def _cleanup_js_object_str(self, s):
        """一个简单的清理函数，将JS对象字符串转换为更接近JSON的格式。"""
        s = re.sub(r"([{\s,])([a-zA-Z0-9_]+)\s*:", r'\1"\2":', s) # 给键加上双引号
        s = s.replace("'", '"') # 替换单引号
        s = re.sub(r",\s*([}\]])", r"\1", s) # 移除尾随逗号
        return s

    def _find_operators(self, obj):
        """
        递归地在解析后的参数对象中查找 MongoDB 操作符 (以 '$' 开头)。
        """
        operators = set()
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(key, str) and key.startswith('$'):
                    operators.add(key)
                operators.update(self._find_operators(value))
        elif isinstance(obj, list):
            for item in obj:
                operators.update(self._find_operators(item))
        return list(operators)

if __name__ == '__main__':
    # 假设爬虫数据已存在
    snippets_file = "NoSQLFeatureKnowledgeBase/MongoDB/mongodb_code_snippets.json"
    if os.path.exists(snippets_file):
        extractor = APIExtractor(snippets_path=snippets_file)
        extractor.extract_patterns()
    else:
        print(f"错误: 未找到爬虫数据文件 '{snippets_file}'。请先运行 APIPatternCrawler.py。")
