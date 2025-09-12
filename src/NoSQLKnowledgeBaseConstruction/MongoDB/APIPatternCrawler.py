import requests
from bs4 import BeautifulSoup
import json
import time
import os
from urllib.parse import urljoin

class APIPatternCrawler:
    """
    一个网络爬虫，用于从指定的数据源（如官方文档、技术博客、Stack Overflow）
    抓取与 NoSQL 数据库（特别是 MongoDB）相关的代码片段。
    """

    def __init__(self, start_urls, output_dir="NoSQLFeatureKnowledgeBase/MongoDB", max_depth=2):
        """
        初始化爬虫。

        Args:
            start_urls (list): 爬虫开始的 URL 列表。
            output_dir (str): 保存抓取数据的目录。
            max_depth (int): 爬虫的最大递归深度。
        """
        self.start_urls = start_urls
        self.output_dir = output_dir
        self.max_depth = max_depth
        self.visited_urls = set()
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def crawl(self):
        """
        启动爬虫，并保存结果。
        """
        print("启动 API 模式爬虫...")
        all_snippets = []
        for url in self.start_urls:
            all_snippets.extend(self._crawl_recursive(url, depth=0))

        output_path = os.path.join(self.output_dir, "mongodb_code_snippets.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_snippets, f, indent=4, ensure_ascii=False)
        
        print(f"爬取完成！总共找到 {len(all_snippets)} 个代码片段。")
        print(f"数据已保存至: {output_path}")

    def _crawl_recursive(self, url, depth):
        """
        递归地爬取页面。
        """
        if depth > self.max_depth or url in self.visited_urls:
            return []
        
        print(f"正在爬取 (深度 {depth}): {url}")
        self.visited_urls.add(url)

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            # time.sleep(1) # 遵守礼貌的爬虫协议
        except requests.RequestException as e:
            print(f"无法访问 URL {url}: {e}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        snippets = self._extract_code_snippets(soup, url)

        # 寻找并跟随页面上的其他链接
        if depth < self.max_depth:
            for link in soup.find_all('a', href=True):
                next_url = urljoin(url, link['href'])
                # 简单过滤，避免爬取不相关的页面
                if any(keyword in next_url for keyword in ['docs.mongodb.com', 'manual', 'reference']):
                    snippets.extend(self._crawl_recursive(next_url, depth + 1))
        
        return snippets

    def _extract_code_snippets(self, soup, source_url):
        """
        从 BeautifulSoup 对象中提取代码片段。
        """
        found_snippets = []
        # 这里的选择器需要根据目标网站的 HTML 结构进行调整
        # 通常代码会包含在 <pre>, <code>, 或特定 class 的 <div> 中
        code_selectors = ['pre > code', 'div.highlight', 'code.language-js', 'code.language-javascript']
        for selector in code_selectors:
            for code_block in soup.select(selector):
                text_content = code_block.get_text().strip()
                if text_content and 'db.' in text_content: # 简单过滤，确保是数据库代码
                    # 尝试获取代码块前的描述性文本
                    description = ""
                    prev_sibling = code_block.find_previous_sibling()
                    if prev_sibling and prev_sibling.name in ['p', 'h1', 'h2', 'h3']:
                        description = prev_sibling.get_text().strip()
                        
                    found_snippets.append({
                        "source_url": source_url,
                        "description": description,
                        "code": text_content
                    })
        return found_snippets

if __name__ == '__main__':
    # 示例：爬取 MongoDB 官方文档中关于查询的部分
    mongo_docs_urls = [
        "https://www.mongodb.com/docs/manual/tutorial/query-documents/",
        "https://www.mongodb.com/docs/manual/reference/operator/query/"
    ]
    crawler = APIPatternCrawler(start_urls=mongo_docs_urls, max_depth=1)
    crawler.crawl()
