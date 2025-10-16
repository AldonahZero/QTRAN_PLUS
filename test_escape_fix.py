#!/usr/bin/env python3
"""测试修复 \$eq 转义问题"""
import json

# 模拟 LLM 输出的 JSON (包含 \$eq)
llm_output = """{
  "mutations": [
    {
      "mutated_sql": "test1",
      "explanation": "使用 \\$eq 运算符"
    },
    {
      "mutated_sql": "test2",
      "explanation": "使用 \\$in 操作符"
    }
  ]
}"""

print("原始 LLM 输出:")
print(llm_output[:200])

print("\n【方法1】尝试直接解析...")
try:
    data = json.loads(llm_output)
    print("✅ 解析成功!")
except json.JSONDecodeError as e:
    print(f"❌ 解析失败: {e}")

    print("\n【方法2】替换 \\$ 为 \\\\$...")
    fixed = llm_output.replace("\\$", "\\\\$")
    print(f"修复后:\n{fixed[:200]}")
    try:
        data = json.loads(fixed)
        print("✅ 解析成功!")
        print(f"   mutations[0].explanation: {data['mutations'][0]['explanation']}")
    except json.JSONDecodeError as e2:
        print(f"❌ 还是失败: {e2}")
