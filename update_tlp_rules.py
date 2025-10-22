#!/usr/bin/env python3
"""Update TLP MongoDB rules to prevent field invention."""

import json

NEW_RULES = """=== ⚠️ CRITICAL FIELD SELECTION RULES ===

**RULE 1: EXTRACT EXISTING FIELDS FROM SEED QUERY**
⚠️ **MOST IMPORTANT**: TLP partitions MUST ONLY use fields that ALREADY EXIST in the seed query.

**Field Extraction Process:**
1. Parse the seed query filter to identify ALL field names used
2. Choose a partition field that EXISTS in the query
3. NEVER invent fictional fields like "value", "score", etc. unless they appear in the seed

**Correct Examples:**

✅ Seed Filter: {"counter": {"$exists": true}}
   → Existing fields: ["counter"]
   → Partition on "counter" (the ONLY field present)
   → True:  {"counter": {"$exists": true, "$type": "number"}}
   → False: {"counter": {"$exists": true, "$not": {"$type": "number"}}}
   → Null:  {"counter": {"$exists": false}}

✅ Seed Filter: {"_id": "mykey"}
   → Existing fields: ["_id"]
   → For KV pattern, document typically has {_id, value}
   → Can partition on "value" IF it's reasonable to assume it exists
   → True:  {"_id": "mykey", "value": {"$type": "string"}}
   → False: {"_id": "mykey", "value": {"$not": {"$type": "string"}}, "value": {"$exists": true}}
   → Null:  {"_id": "mykey", "value": {"$exists": false}}

✅ Seed Filter: {"key": "myset", "score": {"$gte": 0}}
   → Existing fields: ["key", "score"]
   → Partition on "score" (already used but can add more conditions)
   → Or partition on "member" if we know it exists from schema

**Wrong Examples (Field Invention):**

❌ Seed Filter: {"counter": {"$exists": true}}
   → Adding "value": {"counter": {"$exists": true}, "value": {"$type": "number"}}
   → WRONG! "value" is NOT in the seed query

❌ Seed Filter: {"mykey": "test"}
   → Adding "score": {"mykey": "test", "score": {"$gte": 100}}
   → WRONG! "score" is fictional

**RULE 2: UNDERSTAND MONGODB DOCUMENT PATTERNS**

When seed uses certain patterns, we can infer additional fields:

Pattern A: Direct Field Query
- Seed: {"fieldName": {"$exists": true}}
- Inferred: Document has "fieldName" field
- ✅ Partition on "fieldName" itself

Pattern B: KV-Style (_id as key)
- Seed: {"_id": "somekey"}
- Inferred: Document likely has {"_id": "somekey", "value": ...}
- ✅ Partition on "value" (reasonable assumption for KV collections)

Pattern C: Zset-Style (key + score/member)
- Seed: {"key": "myset"}
- Inferred: Document has {"key": "myset", "member": "...", "score": N}
- ✅ Partition on "score" or "member"

**RULE 3: CONSERVATIVE PARTITIONING STRATEGY**

When in doubt, partition on the SAME field that's already in the query:

Strategy 1: Add type conditions to existing field
- Seed: {"myfield": {"$exists": true}}
- ✅ Safe: {"myfield": {"$exists": true, "$type": "number"}}

Strategy 2: Add value range to existing numeric field  
- Seed: {"age": {"$gte": 0}}
- ✅ Safe: {"age": {"$gte": 18}} (different range)

Strategy 3: For _id-based KV queries, assume "value" field
- Seed: {"_id": "key1"}
- ✅ Reasonable: {"_id": "key1", "value": {"$type": "number"}}

**NEVER add fields that don't appear in seed AND can't be inferred from collection pattern!**

"""


def main():
    filepath = "MutationData/MutationLLMPrompt/tlp_mongodb.json"

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    content = data["tlp"]
    old_start = content.find("=== ⚠️ CRITICAL FIELD SELECTION RULES ===")
    old_end = content.find("=== MONGODB TLP PATTERNS ===")

    if old_start == -1 or old_end == -1:
        print("❌ Failed to find sections to replace")
        print(f"   old_start: {old_start}, old_end: {old_end}")
        return False

    # Replace the section
    new_content = content[:old_start] + NEW_RULES + "\n" + content[old_end:]
    data["tlp"] = new_content

    # Write back
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("✅ Successfully updated tlp_mongodb.json")
    print(f"   Old section: {old_end - old_start} chars")
    print(f"   New section: {len(NEW_RULES)} chars")
    print("\n   Key changes:")
    print("   - Rule 1: Extract existing fields from seed query")
    print("   - Examples show correct field usage vs invention")
    print("   - Conservative strategy: partition on existing fields")
    return True


if __name__ == "__main__":
    main()
