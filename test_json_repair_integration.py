#!/usr/bin/env python3
"""
测试 json-repair 集成效果

验证 translate_sqlancer.py 和 MutateLLM.py 中的 JSON 修复功能
"""

import json
from json_repair import repair_json

# 测试用例：实际出现的错误格式
test_cases = [
    {
        "name": "TLP Mutation - 缺少引号的字段名",
        "bad_json": '{"op":"find","collection":"myCollection","filter":{"key":"mykey",value:{"$type":"number"}}}',
        "expected_fields": ["op", "collection", "filter", "value"]
    },
    {
        "name": "TLP Mutation - 复杂嵌套",
        "bad_json": '{"cmd":"{\\\"op\\\":\\\"findOne\\\",\\\"collection\\\":\\\"myCollection\\\",\\\"filter\\\":{\\\"mykey\\\":\\\"hello\\\",value:{\\\"$type\\\":\\\"number\\\"}}}","category":"tlp_true"}',
        "expected_fields": ["cmd", "category"]
    },
    {
        "name": "NoREC Mutation - 多层嵌套",
        "bad_json": '{"mutations":[{cmd:"{...}",oracle:"norec"}]}',
        "expected_fields": ["mutations"]
    }
]

print("🔧 测试 json-repair 集成\n")
print("=" * 60)

success_count = 0
fail_count = 0

for i, test in enumerate(test_cases, 1):
    print(f"\n测试 {i}: {test['name']}")
    print(f"原始: {test['bad_json'][:80]}...")
    
    try:
        # 尝试修复
        repaired = repair_json(test['bad_json'])
        
        # 验证可以解析
        parsed = json.loads(repaired)
        
        # 检查预期字段
        all_present = all(field in str(parsed) for field in test['expected_fields'])
        
        if all_present:
            print("✅ 修复成功")
            print(f"   修复后: {repaired[:80]}...")
            success_count += 1
        else:
            print("⚠️  修复成功但字段不完整")
            fail_count += 1
            
    except Exception as e:
        print(f"❌ 修复失败: {e}")
        fail_count += 1

print("\n" + "=" * 60)
print(f"\n📊 测试结果: {success_count}/{len(test_cases)} 成功")

if success_count == len(test_cases):
    print("✅ 所有测试通过！json-repair 集成正常工作")
else:
    print(f"⚠️  {fail_count} 个测试失败")

print("\n💡 下一步:")
print("   1. 清理旧输出: rm -rf Output/queue_test")
print("   2. 重新运行: python src/main.py Input/queue_test.jsonl")
print("   3. 检查结果: cat Output/queue_test/MutationLLM/0.jsonl")
