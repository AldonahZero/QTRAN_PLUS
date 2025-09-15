import os
import json
from src.FeatureKnowledgeBaseConstruction.ClickHouse.HTMLs_Crawler import htmls_crawler
from src.FeatureKnowledgeBaseConstruction.ClickHouse.Info_Crawler import crawler_results
from src.Tools.Crawler.crawler_options import category_classifier
current_file_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file_path)


"""
ClickHouse 爬虫入口模块

本模块负责协调 ClickHouse 文档的抓取流程：
- 抓取各类特征（数据类型、函数、运算符）对应的 HTML 列表并存储为 HTMLs.json。
- 基于抓取的 HTML 列表逐页提取函数/运算符/数据类型的详细信息，保存到 results 目录。
- 对抓取结果进行简单的分类（调用 crawler_options 中的分类器）。

该模块位置：src/FeatureKnowledgeBaseConstruction/ClickHouse
与 abstract.md 中“FeatureKnowledgeBaseConstruction -> ClickHouse”章节对应。
只添加模块级说明，不修改已有实现逻辑。
"""

def clickhouse_crawler():
    dic_path = os.path.join(current_dir,"..", "..", "..", "FeatureKnowledgeBase", "clickhouse")
    feature_types = ["datatype", "function", "operator"]
    sub_dic = ["results", "results_category"]
    htmls_start_list = {
        "function": "https://clickhouse.com/docs/en/sql-reference/functions",
        "operator": "https://clickhouse.com/docs/en/sql-reference/window-functions/leadInFrame",
        "datatype": "https://clickhouse.com/docs/en/sql-reference/data-types"
    }
    htmls_end_list = {
        "function": "https://clickhouse.com/docs/en/sql-reference/window-functions/leadInFrame",
        "operator": "https://clickhouse.com/docs/en/sql-reference/operators/exists",
        "datatype": "https://clickhouse.com/docs/en/sql-reference/data-types/newjson"
    }
    # htmls Crawler
    for feature in feature_types:
        # make dictionaries
        feature_dic = os.path.join(dic_path, feature)
        if not os.path.exists(feature_dic):
            os.makedirs(feature_dic)
        for sub in sub_dic:
            sub_dic_path = os.path.join(feature_dic, sub)
            if not os.path.exists(sub_dic_path):
                os.makedirs(sub_dic_path)
        # crawl the htmls list
        html_path = os.path.join(feature_dic, "HTMLs.json")
        if os.path.exists(html_path):
            print("File " + html_path + " exists！")
            continue
        htmls = htmls_crawler(htmls_start_list[feature], htmls_end_list[feature], html_path)
        with open(html_path, 'w', encoding='utf-8') as f:
            json.dump(htmls, f, indent=4)

    # functions and operators information Crawler and classification
    for feature in feature_types:
        htmls_filename = os.path.join(dic_path, feature, "HTMLs.json")
        results_dic = os.path.join(dic_path, feature, "results")
        results_category_dic = os.path.join(dic_path, feature, "results_category")
        crawler_results(feature, htmls_filename, results_dic)
        category_classifier(results_dic, results_category_dic)