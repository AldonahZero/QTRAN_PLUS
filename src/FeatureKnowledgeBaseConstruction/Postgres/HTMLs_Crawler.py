from src.Tools.Crawler.crawler_options import set_options
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
from urllib.parse import urljoin


"""
Postgres HTML 列表抓取模块

职责：
- 遍历 PostgreSQL 官方文档目录，收集函数/运算符/数据类型的子页面 URL，生成 HTML 列表供 Info_Crawler 使用。
- 处理层级目录与跳过规则，返回结构为 {"No Category": {...}}。

文件位置：src/FeatureKnowledgeBaseConstruction/Postgres/HTMLs_Crawler.py
说明：仅加入模块级注释，不更改实现。
"""

def htmls_crawler(html):
    timeout = 5  # 等待时间
    options = set_options()
    driver = webdriver.Chrome(options=options)  # 创建一个Chrome浏览器的WebDriver对象，用于控制浏览器的操作

    htmls_table = {}  # 用于存储所有的htmls
    # 要跳过的html
    skip_htmls = [
    ]

    driver.get(html)  # 打开指定的URL:使用WebDriver打开指定的URL，加载页面内容
    WebDriverWait(driver, timeout)  # 创建一个WebDriverWait对象，设置最大等待时间为50秒，用于等待页面加载完成
    soup = BeautifulSoup(driver.page_source, "html.parser")
    soup_dts = soup.find("dl", class_="toc").find_all("dt")

    for item in soup_dts:
        name = item.text.strip()
        if name.count(".") > 2:
            # 二级标题，跳过
            continue
        href = urljoin(html, item.find("a").get("href"))
        if href in skip_htmls:
            continue
        htmls_table[name] = href
    return {"No Category": htmls_table}
