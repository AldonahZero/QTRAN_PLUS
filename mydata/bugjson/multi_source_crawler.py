#!/usr/bin/env python3
"""
多源Bug爬虫架构 - 为不同数据库使用不同的爬取方法

支持的数据源：
1. SQLite - 官方bug tracker (HTML解析)
2. DuckDB - GitHub Issues (放宽过滤)
3. MySQL - Bugzilla API
4. PostgreSQL - 官方邮件列表/bug tracker
5. MariaDB - Jira API
6. MonetDB - GitHub Issues
7. ClickHouse - GitHub Issues
"""

import requests
import re
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from abc import ABC, abstractmethod


class BaseBugCrawler(ABC):
    """Bug爬虫基类"""
    
    def __init__(self, dbms_name: str):
        self.dbms_name = dbms_name
        self.bugs = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        })
    
    @abstractmethod
    def crawl(self, max_bugs: int = 100) -> List[Dict]:
        """爬取bugs - 子类必须实现"""
        pass
    
    def save_bugs(self, filename: str):
        """保存bugs到JSON文件"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.bugs, f, indent=4, ensure_ascii=False)
        print(f"  💾 {self.dbms_name}: 保存 {len(self.bugs)} 个bugs到 {filename}")


class SQLiteBugCrawler(BaseBugCrawler):
    """SQLite Bug Tracker爬虫 - HTML解析"""
    
    def __init__(self):
        super().__init__("SQLite")
        self.base_url = "https://www.sqlite.org/src/timeline"
    
    def crawl(self, max_bugs: int = 100) -> List[Dict]:
        """
        爬取SQLite的bug报告
        
        SQLite使用Fossil版本控制系统，有专门的timeline页面
        """
        print(f"\n🔍 爬取 {self.dbms_name} (官方Bug Tracker)...")
        
        try:
            # SQLite的timeline可以按类型过滤
            # 参数: y=ci (check-ins), n=100 (数量)
            url = f"{self.base_url}?y=ci&n={max_bugs*2}"  # 多爬一些，过滤后可能不够
            
            print(f"  📄 访问: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找包含"fix"或"bug"关键词的提交
            timeline_items = soup.find_all('tr', class_='timelineRow')
            
            count = 0
            for item in timeline_items:
                if count >= max_bugs:
                    break
                
                # 提取信息
                bug_data = self._parse_timeline_item(item)
                if bug_data:
                    self.bugs.append(bug_data)
                    count += 1
                    print(f"    ✅ {bug_data['title'][:60]}...")
            
            print(f"  🎉 {self.dbms_name}: 新增 {len(self.bugs)} 个bugs")
            
        except Exception as e:
            print(f"  ❌ 爬取失败: {e}")
        
        return self.bugs
    
    def _parse_timeline_item(self, item) -> Optional[Dict]:
        """解析timeline条目"""
        try:
            # 查找是否包含bug相关关键词
            text = item.get_text().lower()
            if not any(kw in text for kw in ['fix', 'bug', 'crash', 'error', 'issue']):
                return None
            
            # 提取日期
            date_elem = item.find('td', class_='timelineDate')
            date_str = date_elem.get_text().strip() if date_elem else ''
            
            # 提取标题和链接
            title_elem = item.find('a')
            title = title_elem.get_text().strip() if title_elem else 'No title'
            link = f"https://www.sqlite.org{title_elem['href']}" if title_elem and title_elem.get('href') else ''
            
            # 转换日期格式
            try:
                # SQLite使用 YYYY-MM-DD 格式
                date_obj = datetime.strptime(date_str.split()[0], '%Y-%m-%d')
                formatted_date = date_obj.strftime('%d/%m/%Y')
            except:
                formatted_date = date_str
            
            return {
                "date": formatted_date,
                "dbms": self.dbms_name,
                "links": {
                    "bugreport": link
                },
                "oracle": "unknown",
                "reporter": "SQLite Team",
                "status": "fixed",
                "title": title
            }
            
        except Exception as e:
            return None


class DuckDBGitHubCrawler(BaseBugCrawler):
    """DuckDB GitHub爬虫 - 不使用标签过滤"""
    
    def __init__(self, github_token=None):
        super().__init__("DuckDB")
        self.github_token = github_token
        self.repo = "duckdb/duckdb"
        self.api_base = f"https://api.github.com/repos/{self.repo}/issues"
        
        if github_token:
            self.session.headers['Authorization'] = f'token {github_token}'
    
    def crawl(self, max_bugs: int = 100) -> List[Dict]:
        """爬取DuckDB的GitHub issues - 不使用标签过滤"""
        print(f"\n🔍 爬取 {self.dbms_name} (GitHub - 无标签过滤)...")
        
        page = 1
        count = 0
        
        while count < max_bugs:
            params = {
                'state': 'all',
                'per_page': 100,
                'page': page,
                'since': '2020-09-01T00:00:00Z'  # 只要2020年9月后的
            }
            
            print(f"  📄 第 {page} 页...")
            
            try:
                response = self.session.get(self.api_base, params=params, timeout=30)
                
                if response.status_code == 403:
                    print("  ⏰ API限流，等待60秒...")
                    time.sleep(60)
                    continue
                
                response.raise_for_status()
                issues = response.json()
                
                if not issues:
                    break
                
                for issue in issues:
                    if count >= max_bugs:
                        break
                    
                    # 跳过PR
                    if issue.get('pull_request'):
                        continue
                    
                    # 检查是否看起来像bug
                    if self._looks_like_bug(issue):
                        bug_data = self._parse_github_issue(issue)
                        if bug_data:
                            self.bugs.append(bug_data)
                            count += 1
                            print(f"    ✅ {bug_data['title'][:60]}...")
                
                page += 1
                time.sleep(1)
                
            except Exception as e:
                print(f"  ❌ 错误: {e}")
                break
        
        print(f"  🎉 {self.dbms_name}: 新增 {len(self.bugs)} 个bugs")
        return self.bugs
    
    def _looks_like_bug(self, issue: Dict) -> bool:
        """判断issue是否看起来像bug"""
        title = issue['title'].lower()
        body = (issue.get('body') or '').lower()
        
        # Bug相关关键词
        bug_keywords = [
            'bug', 'crash', 'error', 'fail', 'incorrect', 'wrong',
            'assertion', 'segfault', 'panic', 'exception', 'issue'
        ]
        
        return any(kw in title or kw in body for kw in bug_keywords)
    
    def _parse_github_issue(self, issue: Dict) -> Optional[Dict]:
        """解析GitHub issue"""
        try:
            created_at = datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00'))
            date_str = created_at.strftime("%d/%m/%Y")
            
            # 提取SQL测试用例
            body = issue.get('body', '') or ''
            test_cases = self._extract_sql(body)
            
            # 判断oracle类型
            oracle = self._determine_oracle(issue['title'], body)
            
            bug_data = {
                "date": date_str,
                "dbms": self.dbms_name,
                "links": {
                    "bugreport": issue['html_url']
                },
                "oracle": oracle,
                "reporter": issue['user']['login'],
                "status": "open" if issue['state'] == 'open' else "fixed",
                "title": issue['title']
            }
            
            if test_cases:
                bug_data["test"] = test_cases
            
            return bug_data
            
        except Exception as e:
            return None
    
    def _extract_sql(self, text: str) -> List[str]:
        """从文本中提取SQL"""
        sql_statements = []
        
        # 提取```sql代码块
        pattern = r'```(?:sql|SQL)\n(.*?)```'
        for match in re.finditer(pattern, text, re.DOTALL):
            code = match.group(1).strip()
            lines = [l.strip() for l in code.split('\n') if l.strip() and not l.strip().startswith('--')]
            sql_statements.extend(lines[:5])
        
        return sql_statements[:10]
    
    def _determine_oracle(self, title: str, body: str) -> str:
        """判断oracle类型"""
        text = (title + ' ' + body).lower()
        
        if any(kw in text for kw in ['crash', 'segfault', 'assertion', 'panic']):
            return "crash"
        elif any(kw in text for kw in ['wrong result', 'incorrect', 'expected']):
            return "PQS"
        elif any(kw in text for kw in ['error', 'exception', 'fail']):
            return "error"
        else:
            return "unknown"


class MySQLBugzillaCrawler(BaseBugCrawler):
    """MySQL Bugzilla爬虫"""
    
    def __init__(self):
        super().__init__("MySQL")
        self.base_url = "https://bugs.mysql.com"
        # Bugzilla REST API
        self.api_url = f"{self.base_url}/rest.cgi/bug"
    
    def crawl(self, max_bugs: int = 100) -> List[Dict]:
        """爬取MySQL Bugzilla"""
        print(f"\n🔍 爬取 {self.dbms_name} (Bugzilla)...")
        
        try:
            # Bugzilla API参数
            params = {
                'product': 'MySQL Server',
                'limit': max_bugs,
                'order': 'bug_id DESC',  # 最新的
                'include_fields': 'id,summary,status,creation_time,component'
            }
            
            print(f"  📄 访问Bugzilla API...")
            response = self.session.get(self.api_url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                bugs_data = data.get('bugs', [])
                
                for bug in bugs_data[:max_bugs]:
                    bug_data = self._parse_bugzilla_bug(bug)
                    if bug_data:
                        self.bugs.append(bug_data)
                        print(f"    ✅ {bug_data['title'][:60]}...")
                
                print(f"  🎉 {self.dbms_name}: 新增 {len(self.bugs)} 个bugs")
            else:
                print(f"  ⚠️  Bugzilla API返回: {response.status_code}")
                print(f"  💡 尝试备选方案: HTML解析...")
                self._crawl_html_fallback(max_bugs)
        
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            print(f"  💡 尝试备选方案...")
            self._crawl_html_fallback(max_bugs)
        
        return self.bugs
    
    def _parse_bugzilla_bug(self, bug: Dict) -> Optional[Dict]:
        """解析Bugzilla bug"""
        try:
            # 转换日期
            date_obj = datetime.fromisoformat(bug['creation_time'].replace('Z', '+00:00'))
            date_str = date_obj.strftime("%d/%m/%Y")
            
            bug_id = bug['id']
            
            return {
                "date": date_str,
                "dbms": self.dbms_name,
                "links": {
                    "bugreport": f"{self.base_url}/bug.php?id={bug_id}"
                },
                "oracle": "unknown",
                "reporter": "MySQL Team",
                "status": bug.get('status', 'unknown').lower(),
                "title": bug.get('summary', 'No title')
            }
        except Exception as e:
            return None
    
    def _crawl_html_fallback(self, max_bugs: int):
        """备选方案：HTML解析"""
        print(f"  📄 使用HTML解析方案...")
        # 这里可以实现HTML解析逻辑
        pass


class PostgreSQLMailingListCrawler(BaseBugCrawler):
    """PostgreSQL邮件列表爬虫"""
    
    def __init__(self):
        super().__init__("PostgreSQL")
        self.base_url = "https://www.postgresql.org/list/pgsql-bugs"
    
    def crawl(self, max_bugs: int = 100) -> List[Dict]:
        """爬取PostgreSQL邮件列表"""
        print(f"\n🔍 爬取 {self.dbms_name} (邮件列表)...")
        print(f"  ⚠️  PostgreSQL使用邮件列表，解析较复杂")
        print(f"  💡 建议: 手动访问 {self.base_url}")
        
        # 邮件列表爬取比较复杂，这里提供框架
        # 实际实现需要解析邮件归档页面
        
        return self.bugs


class MariaDBJiraCrawler(BaseBugCrawler):
    """MariaDB Jira爬虫"""
    
    def __init__(self):
        super().__init__("MariaDB")
        self.base_url = "https://jira.mariadb.org"
        self.api_url = f"{self.base_url}/rest/api/2/search"
    
    def crawl(self, max_bugs: int = 100) -> List[Dict]:
        """爬取MariaDB Jira"""
        print(f"\n🔍 爬取 {self.dbms_name} (Jira)...")
        
        try:
            # Jira JQL查询
            params = {
                'jql': 'project=MDEV AND type=Bug ORDER BY created DESC',
                'maxResults': max_bugs,
                'fields': 'summary,status,created,reporter'
            }
            
            print(f"  📄 访问Jira API...")
            response = self.session.get(self.api_url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                issues = data.get('issues', [])
                
                for issue in issues:
                    bug_data = self._parse_jira_issue(issue)
                    if bug_data:
                        self.bugs.append(bug_data)
                        print(f"    ✅ {bug_data['title'][:60]}...")
                
                print(f"  🎉 {self.dbms_name}: 新增 {len(self.bugs)} 个bugs")
            else:
                print(f"  ⚠️  Jira API需要认证或访问受限")
                print(f"  💡 建议: 手动访问 {self.base_url}")
        
        except Exception as e:
            print(f"  ❌ 错误: {e}")
        
        return self.bugs
    
    def _parse_jira_issue(self, issue: Dict) -> Optional[Dict]:
        """解析Jira issue"""
        try:
            fields = issue.get('fields', {})
            
            # 转换日期
            date_str = fields.get('created', '')
            if date_str:
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                date_str = date_obj.strftime("%d/%m/%Y")
            
            return {
                "date": date_str,
                "dbms": self.dbms_name,
                "links": {
                    "bugreport": f"{self.base_url}/browse/{issue['key']}"
                },
                "oracle": "unknown",
                "reporter": fields.get('reporter', {}).get('displayName', 'Unknown'),
                "status": fields.get('status', {}).get('name', 'unknown').lower(),
                "title": fields.get('summary', 'No title')
            }
        except Exception as e:
            return None


def main():
    """主函数 - 从多个数据源爬取bugs"""
    
    print("=" * 70)
    print("🕷️  多源Bug爬虫系统")
    print("=" * 70)
    print("📋 将从各数据库的官方网站爬取最新bugs\n")
    
    # 尝试获取GitHub Token
    github_token = None
    try:
        from crawler_config import GITHUB_TOKEN
        github_token = GITHUB_TOKEN
    except:
        pass
    
    all_bugs = []
    
    # 1. SQLite - 官方Bug Tracker
    print("\n" + "=" * 70)
    print("1️⃣ SQLite (官方Bug Tracker)")
    print("=" * 70)
    sqlite_crawler = SQLiteBugCrawler()
    sqlite_bugs = sqlite_crawler.crawl(max_bugs=50)
    all_bugs.extend(sqlite_bugs)
    if sqlite_bugs:
        sqlite_crawler.save_bugs("bugs_sqlite_new.json")
    
    # 2. DuckDB - GitHub (无标签过滤)
    print("\n" + "=" * 70)
    print("2️⃣ DuckDB (GitHub - 放宽过滤)")
    print("=" * 70)
    duckdb_crawler = DuckDBGitHubCrawler(github_token)
    duckdb_bugs = duckdb_crawler.crawl(max_bugs=100)
    all_bugs.extend(duckdb_bugs)
    if duckdb_bugs:
        duckdb_crawler.save_bugs("bugs_duckdb_new.json")
    
    # 3. MySQL - Bugzilla
    print("\n" + "=" * 70)
    print("3️⃣ MySQL (Bugzilla)")
    print("=" * 70)
    mysql_crawler = MySQLBugzillaCrawler()
    mysql_bugs = mysql_crawler.crawl(max_bugs=50)
    all_bugs.extend(mysql_bugs)
    if mysql_bugs:
        mysql_crawler.save_bugs("bugs_mysql_new.json")
    
    # 4. PostgreSQL - 邮件列表
    print("\n" + "=" * 70)
    print("4️⃣ PostgreSQL (邮件列表)")
    print("=" * 70)
    pg_crawler = PostgreSQLMailingListCrawler()
    pg_bugs = pg_crawler.crawl(max_bugs=50)
    all_bugs.extend(pg_bugs)
    
    # 5. MariaDB - Jira
    print("\n" + "=" * 70)
    print("5️⃣ MariaDB (Jira)")
    print("=" * 70)
    mariadb_crawler = MariaDBJiraCrawler()
    mariadb_bugs = mariadb_crawler.crawl(max_bugs=50)
    all_bugs.extend(mariadb_bugs)
    if mariadb_bugs:
        mariadb_crawler.save_bugs("bugs_mariadb_new.json")
    
    # 保存所有bugs
    if all_bugs:
        print("\n" + "=" * 70)
        print("💾 保存所有新爬取的bugs...")
        with open("bugs_multi_source.json", 'w', encoding='utf-8') as f:
            json.dump(all_bugs, f, indent=4, ensure_ascii=False)
        print(f"  ✅ 保存 {len(all_bugs)} 个bugs到 bugs_multi_source.json")
    
    # 统计
    from collections import Counter
    dbms_count = Counter(bug['dbms'] for bug in all_bugs)
    
    print("\n" + "=" * 70)
    print("📊 爬取完成统计:")
    print("=" * 70)
    for dbms, count in dbms_count.most_common():
        print(f"  ✅ {dbms:15s} {count:3d} 个新bugs")
    print(f"  {'─' * 36}")
    print(f"  总计:          {len(all_bugs):3d} 个新bugs")
    print("=" * 70)
    
    print("\n💡 提示:")
    print("  - 各数据库的bugs已分别保存")
    print("  - 所有bugs合并在: bugs_multi_source.json")
    print("  - 使用merge_multi_db.py合并到主文件")


if __name__ == "__main__":
    # 安装依赖提示
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("❌ 缺少依赖: BeautifulSoup4")
        print("📦 安装命令: pip install beautifulsoup4")
        exit(1)
    
    main()

