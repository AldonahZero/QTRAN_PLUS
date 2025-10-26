#!/usr/bin/env python3
"""
SurrealDB 连接测试脚本
验证 SurrealDB 是否正常工作以及基本的 CRUD 操作
"""

import asyncio
from surrealdb import Surreal

async def test_surrealdb():
    print("🚀 开始测试 SurrealDB 连接...")
    
    try:
        # 创建连接
        print("\n1️⃣ 连接到 SurrealDB (http://127.0.0.1:8000/rpc)...")
        db = Surreal("http://127.0.0.1:8000/rpc")
        await db.connect()
        print("✅ 连接成功！")
        
        # 登录
        print("\n2️⃣ 使用 root 用户登录...")
        await db.signin({"user": "root", "pass": "root"})
        print("✅ 登录成功！")
        
        # 选择命名空间和数据库
        print("\n3️⃣ 选择命名空间和数据库 (test/test)...")
        await db.use("test", "test")
        print("✅ 选择成功！")
        
        # 创建表定义
        print("\n4️⃣ 创建表定义 (users)...")
        await db.query("DEFINE TABLE users SCHEMAFULL;")
        await db.query("DEFINE FIELD name ON TABLE users TYPE string;")
        await db.query("DEFINE FIELD age ON TABLE users TYPE int;")
        await db.query("DEFINE FIELD email ON TABLE users TYPE option<string>;")
        print("✅ 表定义创建成功！")
        
        # 插入测试数据
        print("\n5️⃣ 插入测试数据...")
        result = await db.query("""
            INSERT INTO users (name, age, email) VALUES 
            ('Alice', 25, 'alice@example.com'),
            ('Bob', 30, 'bob@example.com'),
            ('Charlie', 35, NULL);
        """)
        print(f"✅ 插入成功！结果: {result}")
        
        # 查询所有数据
        print("\n6️⃣ 查询所有数据 (SELECT * FROM users)...")
        result = await db.query("SELECT * FROM users;")
        print(f"✅ 查询成功！")
        for user in result[0]['result']:
            print(f"   - {user}")
        
        # 条件查询
        print("\n7️⃣ 条件查询 (WHERE age > 25)...")
        result = await db.query("SELECT * FROM users WHERE age > 25;")
        print(f"✅ 条件查询成功！")
        for user in result[0]['result']:
            print(f"   - {user}")
        
        # 聚合查询
        print("\n8️⃣ 聚合查询 (COUNT, AVG)...")
        result = await db.query("SELECT COUNT(*) AS total, math::mean(age) AS avg_age FROM users;")
        print(f"✅ 聚合查询成功！")
        print(f"   结果: {result[0]['result']}")
        
        # 测试 NULL 处理
        print("\n9️⃣ 测试 NULL 处理...")
        result = await db.query("SELECT * FROM users WHERE email IS NULL;")
        print(f"✅ NULL 查询成功！")
        for user in result[0]['result']:
            print(f"   - {user}")
        
        # 更新数据
        print("\n🔟 更新数据...")
        result = await db.query("UPDATE users SET age = 26 WHERE name = 'Alice';")
        print(f"✅ 更新成功！结果: {result}")
        
        # 验证更新
        print("\n1️⃣1️⃣ 验证更新结果...")
        result = await db.query("SELECT * FROM users WHERE name = 'Alice';")
        print(f"✅ 验证成功！Alice 的新年龄: {result[0]['result'][0]['age']}")
        
        # 删除数据
        print("\n1️⃣2️⃣ 删除数据...")
        result = await db.query("DELETE FROM users WHERE name = 'Charlie';")
        print(f"✅ 删除成功！")
        
        # 最终统计
        print("\n1️⃣3️⃣ 最终统计...")
        result = await db.query("SELECT COUNT(*) AS remaining FROM users;")
        print(f"✅ 剩余用户数: {result[0]['result'][0]['remaining']}")
        
        print("\n" + "="*60)
        print("🎉 所有测试通过！SurrealDB 工作正常！")
        print("="*60)
        
        print("\n📊 SurrealQL vs SQL 语法对比:")
        print("-" * 60)
        print("SQL (SQLite):        CREATE TABLE users (name TEXT, age INT);")
        print("SurrealQL:           DEFINE TABLE users SCHEMAFULL;")
        print("                     DEFINE FIELD name ON TABLE users TYPE string;")
        print("-" * 60)
        print("SQL:                 SELECT * FROM users WHERE age > 25;")
        print("SurrealQL:           SELECT * FROM users WHERE age > 25;  (相同!)")
        print("-" * 60)
        print("SQL:                 SELECT COUNT(*), AVG(age) FROM users;")
        print("SurrealQL:           SELECT COUNT(*), math::mean(age) FROM users;")
        print("-" * 60)
        
        print("\n✅ 翻译难度评估: ⭐⭐⭐ 中等")
        print("   - SELECT/WHERE/ORDER BY: 几乎完全相同")
        print("   - INSERT/UPDATE/DELETE: 基本相同")
        print("   - 表定义: 需要转换为 DEFINE 语法")
        print("   - 聚合函数: 部分函数名不同 (AVG → math::mean)")
        
        print("\n🎯 下一步:")
        print("   1. 创建 SQLite → SurrealQL 的翻译 prompt")
        print("   2. 构建 SurrealDB 特性知识库")
        print("   3. 运行 demo1.jsonl 进行测试")
        print("   4. 寻找真正的 SurrealDB Bug！")
        
        # 关闭连接
        await db.close()
        print("\n🔌 连接已关闭")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_surrealdb())

