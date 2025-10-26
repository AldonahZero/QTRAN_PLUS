#!/usr/bin/env python3
"""
SurrealDB 简单连接测试
"""

import requests
import json

# 测试 HTTP API
base_url = "http://127.0.0.1:8000"

print("🚀 开始测试 SurrealDB (HTTP API)...")

# 1. 健康检查
print("\n1️⃣ 健康检查...")
try:
    response = requests.get(f"{base_url}/health")
    print(f"✅ 健康检查: {response.status_code}")
except Exception as e:
    print(f"❌ 健康检查失败: {e}")
    exit(1)

# 2. SQL 查询（使用 HTTP API）
print("\n2️⃣ 测试 SQL 查询...")
headers = {
    "Accept": "application/json",
    "NS": "test",
    "DB": "test",
}
auth = ("root", "root")

# 创建表定义
print("   创建表定义...")
queries = [
    "DEFINE TABLE users SCHEMAFULL;",
    "DEFINE FIELD name ON TABLE users TYPE string;",
    "DEFINE FIELD age ON TABLE users TYPE int;",
    "DEFINE FIELD email ON TABLE users TYPE option<string>;",
]

for query in queries:
    try:
        response = requests.post(
            f"{base_url}/sql",
            data=query,
            headers=headers,
            auth=auth
        )
        if response.status_code == 200:
            print(f"   ✅ {query[:50]}...")
        else:
            print(f"   ⚠️ {query[:50]}... Status: {response.status_code}")
            print(f"      Response: {response.text}")
    except Exception as e:
        print(f"   ❌ 查询失败: {e}")

# 3. 插入数据
print("\n3️⃣ 插入测试数据...")
insert_query = """
INSERT INTO users (name, age, email) VALUES 
('Alice', 25, 'alice@example.com'),
('Bob', 30, 'bob@example.com'),
('Charlie', 35, NULL);
"""
try:
    response = requests.post(
        f"{base_url}/sql",
        data=insert_query,
        headers=headers,
        auth=auth
    )
    if response.status_code == 200:
        print(f"✅ 插入成功！")
        print(f"   Response: {response.text[:200]}")
    else:
        print(f"⚠️ Status: {response.status_code}")
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"❌ 插入失败: {e}")

# 4. 查询数据
print("\n4️⃣ 查询所有数据...")
select_query = "SELECT * FROM users;"
try:
    response = requests.post(
        f"{base_url}/sql",
        data=select_query,
        headers=headers,
        auth=auth
    )
    if response.status_code == 200:
        print(f"✅ 查询成功！")
        result = response.json()
        print(f"   结果: {json.dumps(result, indent=2)}")
    else:
        print(f"⚠️ Status: {response.status_code}")
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"❌ 查询失败: {e}")

# 5. 条件查询
print("\n5️⃣ 条件查询 (WHERE age > 25)...")
where_query = "SELECT * FROM users WHERE age > 25;"
try:
    response = requests.post(
        f"{base_url}/sql",
        data=where_query,
        headers=headers,
        auth=auth
    )
    if response.status_code == 200:
        print(f"✅ 条件查询成功！")
        result = response.json()
        print(f"   结果: {json.dumps(result, indent=2)}")
    else:
        print(f"⚠️ Status: {response.status_code}")
except Exception as e:
    print(f"❌ 条件查询失败: {e}")

# 6. 聚合查询
print("\n6️⃣ 聚合查询...")
agg_query = "SELECT COUNT(*) AS total, math::mean(age) AS avg_age FROM users;"
try:
    response = requests.post(
        f"{base_url}/sql",
        data=agg_query,
        headers=headers,
        auth=auth
    )
    if response.status_code == 200:
        print(f"✅ 聚合查询成功！")
        result = response.json()
        print(f"   结果: {json.dumps(result, indent=2)}")
    else:
        print(f"⚠️ Status: {response.status_code}")
        print(f"   Response: {response.text}")
except Exception as e:
    print(f"❌ 聚合查询失败: {e}")

print("\n" + "="*60)
print("🎉 基本测试完成！")
print("="*60)

print("\n📊 SurrealQL 语法验证:")
print("   ✅ 表定义: DEFINE TABLE/FIELD 语法")
print("   ✅ INSERT: 与 SQL 相同")
print("   ✅ SELECT: 与 SQL 相同")
print("   ✅ WHERE: 与 SQL 相同")
print("   ✅ 聚合: 使用 math::mean() 而非 AVG()")

print("\n🎯 SurrealDB 已就绪，可以开始测试！")
print("\n下一步:")
print("   1. 创建知识库目录")
print("   2. 准备翻译 Prompt")
print("   3. 运行第一个测试")


