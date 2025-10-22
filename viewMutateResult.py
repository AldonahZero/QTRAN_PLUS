import json

with open("Output/agent_demo/MutationLLM/0.jsonl", "r") as f:
    for line in f:
        data = json.loads(line.strip())
        if "MutateResult" in data:
            print("=" * 80)
            print(f'Original SQL: {data["sqls"]}')
            print(f'Transferred: {data["TransferResult"][0]["TransferSQL"]}')
            print(f'MutateResult: {data["MutateResult"][:200]}...')
            if "OracleCheck" in data:
                print(f'Oracle Check: {data["OracleCheck"]}')
            print()


with open("Output/agent_demo/MutationLLM/0.jsonl", "r") as f:
    for line in f:
        data = json.loads(line.strip())
        if "MutateResult" in data:
            print("=" * 80)
            print(f'Original Redis: {data["sqls"]}')
            print(f'Transferred MongoDB: {data["TransferResult"][0]["TransferSQL"]}')
            print()

            mutate_result = json.loads(data["MutateResult"])
            print(f'Total Mutations: {len(mutate_result["mutations"])}')
            for i, mut in enumerate(mutate_result["mutations"]):
                print(
                    f'  [{i}] Category: {mut["category"]:15s} Oracle: {mut["oracle"]:15s}'
                )
                cmd = json.loads(mut["cmd"])
                print(f'      Operation: {cmd["op"]}')
                print(f'      Filter: {json.dumps(cmd["filter"], ensure_ascii=False)}')
            print()
            if "OracleCheck" in data:
                print(f'Oracle Result: {data["OracleCheck"]}')
            print()
