#!/usr/bin/env python3
"""
Quick test for Agent mutation path (QTRAN_MUTATION_ENGINE=agent)
"""
import os
import json

os.environ.setdefault("HTTP_PROXY", "http://127.0.0.1:7890")
os.environ.setdefault("HTTPS_PROXY", "http://127.0.0.1:7890")

# Ensure agent engine
os.environ["QTRAN_MUTATION_ENGINE"] = "agent"

from openai import OpenAI
from src.MutationLlmModelValidator.MutateLLM import run_muatate_llm_single_sql


def main():
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    # Dummy model id for fallback (won't be used if agent succeeds)
    model_id = os.environ.get("SEMANTIC_MUTATION_LLM_ID", "gpt-4o-mini")

    tool = "sqlancer"
    mutate_name = "semantic"  # or norec/tlp
    oracle = "semantic"
    db_type = "mysql"
    sql = "SELECT * FROM users WHERE age > 18 AND city = 'Beijing';"

    out, cost = run_muatate_llm_single_sql(
        tool=tool,
        client=client,
        model_id=model_id,
        mutate_name=mutate_name,
        oracle=oracle,
        db_type=db_type,
        sql=sql,
    )
    print("=== Engine Cost ===")
    print(cost)
    print("=== Raw Output (truncated) ===")
    print(str(out)[:800])
    try:
        data = json.loads(out)
        print("=== Parsed JSON Keys ===", list(data.keys()))
    except Exception as e:
        print("JSON parse failed:", e)


if __name__ == "__main__":
    main()
