import json
import argparse
from pathlib import Path

"""
依据 MongoDB / Redis 查询或命令特征判定应该使用的微调类别 (molt)
类别含义（沿用原项目推测语义）：
  orec   : 聚合/结果重写/集合计算密集
  tlp    : NULL / 特殊值 / 三值或缺失语义（Redis 里用 -inf/+inf 等边界、位/HyperLogLog 近似计数可放入此类）
  pinolo : 连接/多集合交叉 / 组合操作（Redis 多 key 合并、交、权重聚合）
  dqe    : 基础数据查询 / 简单操作

优先级（命中多个时取先出现）：聚合(orec) > NULL/边界(tlp) > 多集合交叉(pinolo) > dqe
可通过 --dialect 强制，也可通过自动检测 (auto) 根据内容简单推断。
"""

# MongoDB 关键字集
AGGREGATION_KEYWORDS = [
    '$group', '$sum', '$avg', '$count', '$facet', '$bucket', '$bucketAuto', '$merge', '$setWindowFields'
]
JOIN_LIKE_KEYWORDS = ['$lookup', '$graphLookup', '$unionWith']
NULL_SEMANTIC_KEYWORDS = ['$ifNull', '$exists', '$type', '$cond', '$coalesce']

# Redis 关键字集分类
REDIS_AGG_KEYS = {
    # 排序 / 统计 / 基数 / 位操作等
    'sort', 'zrange', 'zrevrange', 'zcount', 'zcard', 'scard', 'pfcount', 'bitcount', 'strlen',
    'zrank', 'zrevrank', 'zrangebylex', 'zlexcount', 'hrandfield'
}
REDIS_NULL_EDGE_TOKENS = {
    '-inf', '+inf', 'incrbyfloat', 'getbit', 'setbit', 'bitpos', 'bitop', 'pfadd', 'pfmerge'
}
REDIS_MULTISET_TOKENS = {
    'zinterstore', 'zunionstore', 'sinterstore', 'sunionstore', 'sdiffstore', 'zmpop', 'smove'
}

# 允许将历史标签 norec 视作 dqe 映射显示
HISTORICAL_MAPPING = {
    'norec': 'dqe'
}

def determine_molt_mongodb(text: str) -> str:
    lower = text.lower()
    has_aggregate = any(k in lower for k in (kw.lower() for kw in AGGREGATION_KEYWORDS)) or 'pipeline' in lower
    null_literal = (': null' in lower) or (' null,' in lower) or (' null}' in lower) or (' null]' in lower)
    has_null = null_literal or any(k in lower for k in (kw.lower() for kw in NULL_SEMANTIC_KEYWORDS))
    has_join_subquery = any(k in lower for k in (kw.lower() for kw in JOIN_LIKE_KEYWORDS))
    if has_aggregate:
        return 'orec'
    if has_null:
        return 'tlp'
    if has_join_subquery:
        return 'pinolo'
    return 'dqe'


def tokenize_redis(cmd: str):
    return [t.strip().lower() for t in cmd.replace('\n', ' ').split() if t.strip()]


def determine_molt_redis(command: str) -> str:
    tokens = tokenize_redis(command)
    if not tokens:
        return 'dqe'
    token_set = set(tokens)

    # 1 聚合/统计/排序
    if any(t in REDIS_AGG_KEYS for t in token_set):
        return 'orec'
    # 2 边界 / NULL / 特殊值（-inf +inf）或近似结构
    if any(t in REDIS_NULL_EDGE_TOKENS for t in token_set):
        return 'tlp'
    # 3 多集合交叉/合并
    if any(t in REDIS_MULTISET_TOKENS for t in token_set):
        return 'pinolo'
    return 'dqe'


def auto_detect_dialect(sample_text: str) -> str:
    lt = sample_text.lower()
    if any(x in lt for x in ['$match', '$group', '$lookup', 'pipeline']):
        return 'mongodb'
    # 典型 redis 动词
    if any(x in lt.split()[:1] for x in ['set', 'get', 'zadd', 'zincrby', 'zrange', 'sort', 'sadd', 'pfadd']):
        return 'redis'
    return 'redis'  # 默认回退 redis


def determine_molt(text: str, dialect: str) -> str:
    if dialect == 'mongodb':
        return determine_molt_mongodb(text)
    else:  # redis
        return determine_molt_redis(text)


def main():
    parser = argparse.ArgumentParser(description='Analyze queries/commands and decide molt category (MongoDB & Redis).')
    parser.add_argument('-i', '--input', type=str, required=True, help='输入 JSONL 文件路径。每行至少包含命令/查询字段。')
    parser.add_argument('-qf', '--query-field', type=str, default='query', help='字段名（MongoDB 查询或 Redis 命令），默认 query。')
    parser.add_argument('-of', '--original-molt-field', type=str, default='molt', help='原始标注 molt 字段名。')
    parser.add_argument('--dialect', type=str, choices=['mongodb', 'redis', 'auto'], default='auto', help='指定方言：mongodb / redis / auto 自动推断。')
    parser.add_argument('--show-mapping', action='store_true', help='显示历史标签映射后的结果。')
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        raise FileNotFoundError(f'输入文件不存在: {path}')

    # 预读一行用于自动方言识别
    first_line = None
    with path.open('r', encoding='utf-8') as f:
        for raw in f:
            if raw.strip():
                first_line = raw
                break
    if first_line is None:
        print('空文件。')
        return
    try:
        first_obj = json.loads(first_line)
        sample_text = str(first_obj.get(args.query_field, ''))
    except Exception:
        sample_text = first_line

    dialect = args.dialect
    if dialect == 'auto':
        dialect = auto_detect_dialect(sample_text)

    print(f'# 使用方言: {dialect}')

    # 第二次遍历：正式处理
    with path.open('r', encoding='utf-8') as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                print(f'[WARN] 第 {line_no} 行解析失败: {e}')
                continue
            if args.query_field not in data:
                print(f'[WARN] 第 {line_no} 行缺少字段 {args.query_field}')
                continue
            text = str(data[args.query_field])
            decided = determine_molt(text, dialect)
            original = data.get(args.original_molt_field, 'N/A')
            mapped = HISTORICAL_MAPPING.get(original, original)
            out_original = mapped if args.show_mapping else original
            index_display = data.get('index', line_no)
            print(f"index: {index_display}, decided: {decided}, original: {out_original}, raw: {text[:120]}{'...' if len(text)>120 else ''}")

if __name__ == '__main__':
    main()