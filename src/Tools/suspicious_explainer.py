import os
import json


def _read_jsonl(path):
    items = []
    with open(path, 'r', encoding='utf-8') as r:
        for line in r:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                pass
    return items


def explain_suspicious(input_name: str) -> str:
    """
    为 Output/<input_name>/SuspiciousBugs 下的每个 <index>.jsonl 生成 <index>.report.json，
    把对应 MutationLLM/<index>.jsonl 中的 OracleCheck 结论补充进来，并给出简短原因摘要。
    返回报告目录路径。
    """
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'Output', input_name))
    susp_dir = os.path.join(base, 'SuspiciousBugs')
    mut_dir = os.path.join(base, 'MutationLLM')
    if not os.path.isdir(susp_dir):
        raise FileNotFoundError(f'SuspiciousBugs dir not found: {susp_dir}')

    for fname in os.listdir(susp_dir):
        if not fname.endswith('.jsonl'):
            continue
        index = os.path.splitext(fname)[0]
        # 读取 suspicious 简化视图
        susp_path = os.path.join(susp_dir, fname)
        susp_records = _read_jsonl(susp_path)
        last_view = susp_records[-1] if susp_records else {}

        # 读取 mutation 详细记录（含 OracleCheck）
        mut_path = os.path.join(mut_dir, f'{index}.jsonl')
        oracle = None
        if os.path.exists(mut_path):
            mut_records = _read_jsonl(mut_path)
            if mut_records:
                last_full = mut_records[-1]
                oracle = last_full.get('OracleCheck')

        # 构造报告
        report = {
            'index': int(index) if index.isdigit() else index,
            'input': input_name,
            'suspicious_view': {
                'sql': last_view.get('sql'),
                'transfer_sql': (last_view.get('TransferResult') or [None])[-1] if last_view.get('TransferResult') else None,
                'mutate_sql': last_view.get('MutateResult'),
            },
            'oracle_check': oracle,
            'reason': None,
        }
        # 生成简短原因
        if isinstance(oracle, dict):
            end = oracle.get('end')
            err = oracle.get('error')
            if end is False and (err is None or str(err).lower() == 'none'):
                report['reason'] = 'Oracle check failed with no execution error: results mismatch under MOLT.'
            elif end is False and err:
                report['reason'] = f'Oracle check failed due to error: {err}'
            elif end is True:
                report['reason'] = 'Oracle check passed (not suspicious).'
            else:
                report['reason'] = 'Oracle check unavailable or inconclusive.'
        else:
            report['reason'] = 'No OracleCheck found in MutationLLM; open the mutation file to inspect.'

        out_path = os.path.join(susp_dir, f'{index}.report.json')
        with open(out_path, 'w', encoding='utf-8') as w:
            json.dump(report, w, ensure_ascii=False, indent=2)

    return susp_dir


if __name__ == '__main__':
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else 'demo1'
    print(explain_suspicious(name))
