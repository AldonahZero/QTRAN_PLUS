#!/usr/bin/env python3
"""Test the updated TLP mutation generation with corrected rules."""

import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from MutationLlmModelValidator.MutateLLM import _agent_generate_mutations


def test_mutation():
    """Test mutation generation with the new rules."""

    # Load system message
    with open("MutationData/MutationLLMPrompt/tlp_mongodb.json", "r") as f:
        config = json.load(f)
        system_message = config["tlp"]

    # Test case: counter field exists query
    test_sql = '{"op":"findOne","collection":"myCollection","filter":{"counter":{"$exists":true}},"projection":{"counter":1}}'

    print("=" * 80)
    print("Testing TLP Mutation Generation")
    print("=" * 80)
    print(f"\nInput SQL:\n{test_sql}")
    print(f"\nSystem Message Length: {len(system_message)} chars")
    print(
        f"\nKey instruction: 'EXTRACT EXISTING FIELDS' present: {'EXTRACT EXISTING FIELDS' in system_message}"
    )
    print("\n" + "=" * 80)
    print("Generating mutations...")
    print("=" * 80)

    try:
        result = _agent_generate_mutations(
            sql=test_sql, oracle="tlp", db_type="mongodb", system_message=system_message
        )

        if result:
            print("\n✅ Successfully generated mutations!")
            print(f"\nTotal mutations: {len(result.get('mutations', []))}")
            print("\nMutations details:")
            for i, mut in enumerate(result.get("mutations", [])):
                print(
                    f"\n[{i}] Category: {mut['category']:15s} Oracle: {mut['oracle']}"
                )
                cmd = json.loads(mut["cmd"])
                print(f"    Operation: {cmd['op']}")
                print(f"    Filter: {json.dumps(cmd['filter'], indent=2)}")

                # Check if using correct field
                filter_obj = cmd["filter"]
                if "counter" in str(filter_obj):
                    print("    ✅ Uses 'counter' field (correct)")
                if "value" in str(filter_obj) and "counter" in str(filter_obj):
                    print("    ⚠️  Uses both 'counter' AND 'value' fields")
                if "value" in str(filter_obj) and "counter" not in str(filter_obj):
                    print("    ❌ Uses 'value' field but NOT 'counter' (wrong)")
        else:
            print("\n❌ Failed to generate mutations (returned None)")

    except Exception as e:
        print(f"\n❌ Error during generation: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_mutation()
