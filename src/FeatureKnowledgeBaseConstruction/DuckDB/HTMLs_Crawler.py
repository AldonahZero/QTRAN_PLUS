"""
DuckDB HTML 爬虫：抓取 DuckDB 文档页面 HTML，供 Info_Crawler 提取结构化信息。
"""

from src.Tools.Crawler.crawler_options import set_options
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
from urllib.parse import urljoin
def htmls_crawler(html):
    timeout = 5  # 等待时间
    options = set_options()
    driver = webdriver.Chrome(options=options)  # 创建一个Chrome浏览器的WebDriver对象，用于控制浏览器的操作
    htmls_table = {}  # 用于存储所有的htmls
    # 要跳过的html
    skip_htmls = [
        "https://duckdb.org/docs/sql/functions/dateformat",
    """
    DuckDB HTML 列表抓取模块

    职责：
    - 遍历 DuckDB 文档的目录（index/toc）并收集每个页面的 URL 列表，生成供 Info_Crawler 使用的 HTMLs 字典。
    - 处理常见跳过项、构建标准化的 URL 映射，输出格式为 {"No Category": {name: url, ...}}。

    模块位置：src/FeatureKnowledgeBaseConstruction/DuckDB/HTMLs_Crawler.py
    说明：仅添加/替换模块注释，不影响现有抓取与解析逻辑。
    """
        "https://duckdb.org/docs/sql/functions/nested"
    ]
    driver.get(html)  # 打开指定的URL:使用WebDriver打开指定的URL，加载页面内容
    WebDriverWait(driver, timeout)  # 创建一个WebDriverWait对象，设置最大等待时间为50秒，用于等待页面加载完成
    soup = BeautifulSoup(driver.page_source, "html.parser")
    soup_lis = soup.find("div", class_="index").find_all("li")

    for soup_li in soup_lis:
        name = soup_li.text.strip()
        href = urljoin(html, soup_li.find("a").get("href"))
        if href in skip_htmls:
            continue
        htmls_table[name] = href
    return {"No Category": htmls_table}
