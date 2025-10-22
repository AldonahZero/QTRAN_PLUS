#!/usr/bin/env python3
"""Update TLP MongoDB examples to match new rules."""

import json

NEW_EXAMPLES = """=== EXAMPLES WITH CORRECT FIELD SELECTION ===

Example 1: Direct Field Query with Type Partitioning
Seed: {"op":"findOne","collection":"myCollection","filter":{"counter":{"$exists":true}}}
Existing Fields: ["counter"]
Partition Strategy: Add type condition to "counter" field
Output:
{"mutations":[{"cmd":"{\\"op\\":\\"findOne\\",\\"collection\\":\\"myCollection\\",\\"filter\\":{\\"counter\\":{\\"$exists\\":true}}}","category":"original","oracle":"tlp_base"},{"cmd":"{\\"op\\":\\"findOne\\",\\"collection\\":\\"myCollection\\",\\"filter\\":{\\"counter\\":{\\"$exists\\":true,\\"$type\\":\\"number\\"}}}","category":"tlp_true","oracle":"tlp_partition"},{"cmd":"{\\"op\\":\\"findOne\\",\\"collection\\":\\"myCollection\\",\\"filter\\":{\\"counter\\":{\\"$exists\\":true,\\"$not\\":{\\"$type\\":\\"number\\"}}}}","category":"tlp_false","oracle":"tlp_partition"},{"cmd":"{\\"op\\":\\"findOne\\",\\"collection\\":\\"myCollection\\",\\"filter\\":{\\"counter\\":{\\"$exists\\":false}}}","category":"tlp_null","oracle":"tlp_partition"}]}

Example 2: KV Pattern (_id-based) with Value Field
Seed: {"op":"find","collection":"kv","filter":{"_id":"mykey"}}
Existing Fields: ["_id"]
Partition Strategy: Assume "value" field exists (KV pattern)
Output:
{"mutations":[{"cmd":"{\\"op\\":\\"find\\",\\"collection\\":\\"kv\\",\\"filter\\":{\\"_id\\":\\"mykey\\"}}","category":"original","oracle":"tlp_base"},{"cmd":"{\\"op\\":\\"find\\",\\"collection\\":\\"kv\\",\\"filter\\":{\\"_id\\":\\"mykey\\",\\"value\\":{\\"$type\\":\\"number\\"}}}","category":"tlp_true","oracle":"tlp_partition"},{"cmd":"{\\"op\\":\\"find\\",\\"collection\\":\\"kv\\",\\"filter\\":{\\"_id\\":\\"mykey\\",\\"value\\":{\\"$not\\":{\\"$type\\":\\"number\\"}},\\"value\\":{\\"$exists\\":true}}}","category":"tlp_false","oracle":"tlp_partition"},{"cmd":"{\\"op\\":\\"find\\",\\"collection\\":\\"kv\\",\\"filter\\":{\\"_id\\":\\"mykey\\",\\"value\\":{\\"$exists\\":false}}}","category":"tlp_null","oracle":"tlp_partition"}]}

Example 3: Zset Pattern with Score Partitioning
Seed: {"op":"find","collection":"zset","filter":{"key":"myset"}}
Existing Fields: ["key"]
Partition Strategy: Assume "score" field exists (Zset pattern)
Output:
{"mutations":[{"cmd":"{\\"op\\":\\"find\\",\\"collection\\":\\"zset\\",\\"filter\\":{\\"key\\":\\"myset\\"}}","category":"original","oracle":"tlp_base"},{"cmd":"{\\"op\\":\\"find\\",\\"collection\\":\\"zset\\",\\"filter\\":{\\"key\\":\\"myset\\",\\"score\\":{\\"$gte\\":100}}}","category":"tlp_true","oracle":"tlp_partition"},{"cmd":"{\\"op\\":\\"find\\",\\"collection\\":\\"zset\\",\\"filter\\":{\\"key\\":\\"myset\\",\\"score\\":{\\"$lt\\":100}}}","category":"tlp_false","oracle":"tlp_partition"},{"cmd":"{\\"op\\":\\"find\\",\\"collection\\":\\"zset\\",\\"filter\\":{\\"key\\":\\"myset\\",\\"score\\":{\\"$exists\\":false}}}","category":"tlp_null","oracle":"tlp_partition"}]}

Example 4: Multi-Field Query
Seed: {"op":"findOne","collection":"myCollection","filter":{"status":"active","count":{"$gte":0}}}
Existing Fields: ["status", "count"]
Partition Strategy: Partition on "count" (numeric, good for range partition)
Output:
{"mutations":[{"cmd":"{\\"op\\":\\"findOne\\",\\"collection\\":\\"myCollection\\",\\"filter\\":{\\"status\\":\\"active\\",\\"count\\":{\\"$gte\\":0}}}","category":"original","oracle":"tlp_base"},{"cmd":"{\\"op\\":\\"findOne\\",\\"collection\\":\\"myCollection\\",\\"filter\\":{\\"status\\":\\"active\\",\\"count\\":{\\"$gte\\":10}}}","category":"tlp_true","oracle":"tlp_partition"},{"cmd":"{\\"op\\":\\"findOne\\",\\"collection\\":\\"myCollection\\",\\"filter\\":{\\"status\\":\\"active\\",\\"count\\":{\\"$gte\\":0,\\"$lt\\":10}}}","category":"tlp_false","oracle":"tlp_partition"},{"cmd":"{\\"op\\":\\"findOne\\",\\"collection\\":\\"myCollection\\",\\"filter\\":{\\"status\\":\\"active\\",\\"count\\":{\\"$exists\\":false}}}","category":"tlp_null","oracle":"tlp_partition"}]}

"""


def main():
    filepath = "MutationData/MutationLLMPrompt/tlp_mongodb.json"

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    content = data["tlp"]
    old_start = content.find("=== EXAMPLES WITH CORRECT FIELD SELECTION ===")
    old_end = content.find("=== TLP ORACLE VERIFICATION LOGIC ===")

    if old_start == -1 or old_end == -1:
        print("❌ Failed to find examples section")
        print(f"   old_start: {old_start}, old_end: {old_end}")
        return False

    # Replace the examples section
    new_content = content[:old_start] + NEW_EXAMPLES + "\n" + content[old_end:]
    data["tlp"] = new_content

    # Write back
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("✅ Successfully updated examples in tlp_mongodb.json")
    print(f"   Old examples: {old_end - old_start} chars")
    print(f"   New examples: {len(NEW_EXAMPLES)} chars")
    print("\n   Updated examples:")
    print("   1. Direct field query (counter exists) → partition on counter")
    print("   2. KV pattern (_id key) → partition on value")
    print("   3. Zset pattern (key) → partition on score")
    print("   4. Multi-field query → partition on numeric field")
    return True


if __name__ == "__main__":
    main()
