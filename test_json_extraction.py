#!/usr/bin/env python3
"""测试 JSON 提取逻辑"""
import json

test_output = """根据提供的 SQL 语句和要求，以下是生成的 3-5 个语义变异的 JSON 输出：

```json
{
  "mutations": [
    {
      "mutated_sql": "test1",
      "explanation": "解释1"
    },
    {
      "mutated_sql": "test2",
      "explanation": "解释2"
    }
  ]
}
```

这些变异保持了原始查询的语义。"""

print("原始输出:")
print(test_output[:200])
print("\n" + "=" * 80)

txt = test_output.strip()

# 方案1: 尝试提取 ```json 代码块
print("\n【方案1】检测 ```json 代码块...")
if "```json" in txt:
    print("✅ 找到 ```json 标记")
    start = txt.find("```json") + 7
    end = txt.find("```", start)
    print(f"   起始位置: {start}, 结束位置: {end}")
    if end > start:
        txt = txt[start:end].strip()
        print(f"   提取成功,长度: {len(txt)}")
else:
    print("❌ 未找到 ```json 标记")

print("\n【提取结果】")
print(txt[:300])

print("\n【解析 JSON】")
try:
    data = json.loads(txt)
    print("✅ 解析成功!")
    print(f"   键: {list(data.keys())}")
    if "mutations" in data:
        print(f"   变异数量: {len(data['mutations'])}")
except json.JSONDecodeError as e:
    print(f"❌ 解析失败: {e}")
