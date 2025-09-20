#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基于 Redis enriched examples 生成 Redis 变异微调数据集。
输出: MutationData/FineTuningTrainingData/redis_mutation.jsonl
每条 sample => OpenAI messages schema:
{
  "messages": [
    {"role": "system", "content": "...全局指令..."},
    {"role": "user", "content": "Original: <raw>\nMeta: command=<cmd> group=<group> args=<args json>\nTask: Generate up to N mutations preserving key/data-structure semantics."},
    {"role": "assistant", "content": "{\"mutations\":[{...}]}"}
  ]
}

设计原则:
- 避免语义丢失: 针对聚合/基数/顺序/成员等提供 probe & inverse & idempotent 等多类型 mutation。
- 分类 category + oracle 字段用于训练模型保留可判定语义。
- 产生有限个(<=4)高价值 mutation, 去除重复。
"""

# GIT-CHANGE: 2025-09-20 - review annotations added
# - 目的: 为审阅提供上下文说明 (非功能性注释)。
# - 变更点: 在 KB 注入 / group 映射处增加注释，标注为 GIT-READY（请使用下面建议的 commit message 提交）。
# - 注意: 本次修改不改变脚本逻辑，仅增加注释与变更说明，便于代码审阅与变更记录。
# Suggested commit message: "chore(redis): annotate build_redis_mutation_dataset.py for review (KB_context mapping notes)"

import os
import json
from collections import OrderedDict

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
ENRICHED_DIR = os.path.join(BASE_DIR, 'NoSQLFeatureKnowledgeBase', 'Redis', 'outputs', 'parsed_examples_enriched')
OUT_FILE = os.path.join(BASE_DIR, 'MutationData', 'FineTuningTrainingData', 'semantic.jsonl')

# 命令到结构类别映射 (可扩展)
COMMAND_GROUPS = {
    # STRING
    'GET': 'string', 'SET': 'string', 'INCR': 'string', 'DECR': 'string', 'INCRBY': 'string', 'DECRBY': 'string',
    'GETSET': 'string', 'SETEX': 'string', 'PSETEX': 'string', 'SETRANGE': 'string', 'GETRANGE': 'string', 'APPEND': 'string', 'STRLEN': 'string', 'SUBSTR': 'string',
    # HASH
    'HGET': 'hash', 'HSET': 'hash', 'HDEL': 'hash', 'HKEYS': 'hash', 'HVALS': 'hash', 'HLEN': 'hash', 'HEXISTS': 'hash', 'HINCRBY': 'hash', 'HINCRBYFLOAT': 'hash', 'HRANDFIELD': 'hash', 'HSCAN': 'hash', 'HSTRLEN': 'hash',
    # LIST
    'LPUSH': 'list', 'RPUSH': 'list', 'LPOP': 'list', 'RPOP': 'list', 'LRANGE': 'list', 'LLEN': 'list', 'LSET': 'list', 'LREM': 'list', 'LINDEX': 'list', 'LINSERT': 'list', 'LTRIM': 'list', 'LPOS': 'list', 'LMOVE': 'list',
    # SET
    'SADD': 'set', 'SREM': 'set', 'SMEMBERS': 'set', 'SCARD': 'set', 'SISMEMBER': 'set', 'SPOP': 'set', 'SRANDMEMBER': 'set', 'SINTER': 'set', 'SDIFF': 'set', 'SUNION': 'set', 'SSCAN': 'set',
    # ZSET
    'ZADD': 'zset', 'ZREM': 'zset', 'ZRANGE': 'zset', 'ZREVRANGE': 'zset', 'ZCARD': 'zset', 'ZCOUNT': 'zset', 'ZRANK': 'zset', 'ZINCRBY': 'zset', 'ZLEXCOUNT': 'zset', 'ZDIFF': 'zset', 'ZUNION': 'zset', 'ZINTER': 'zset', 'ZRANDMEMBER': 'zset',
    # TTL / meta
    'EXPIRE': 'ttl', 'TTL': 'ttl', 'PEXPIREAT': 'ttl', 'EXPIREAT': 'ttl', 'PERSIST': 'ttl'
}

# Load semantic KB (Define/Use) to inject small structured context into user prompt
KB_PATH = os.path.join(BASE_DIR, 'NoSQLFeatureKnowledgeBase', 'Redis', 'outputs', 'redis_semantic_kb.json')
try:
    with open(KB_PATH, 'r', encoding='utf-8') as _kbf:
        _kb = json.load(_kbf)
        _by_command = _kb.get('by_command', {})
except Exception:
    _by_command = {}

def get_kb_context(command_upper: str):
    """Return a compact KB context for a given command (define/use/args roles).
    Keeps the structure small: {define:[], use:[], args:{argname:[actions]}}
    """
    if not command_upper:
        return {}
    cmd_l = command_upper.lower()
    entry = _by_command.get(cmd_l) or {}
    actions = entry.get('actions', {}) if isinstance(entry, dict) else {}
    args = entry.get('args', {}) if isinstance(entry, dict) else {}
    kb_ctx = {}
    if actions:
        # collect DefineSymbol and UseSymbol when present
        if 'DefineSymbol' in actions:
            kb_ctx['define'] = actions.get('DefineSymbol')
        if 'UseSymbol' in actions:
            kb_ctx['use'] = actions.get('UseSymbol')
    # collect per-arg roles (if available)
    arg_roles = {}
    for argname, aentry in (args.items() if isinstance(args, dict) else []):
        # aentry may contain DefineSymbol/UseSymbol
        roles = {}
        if isinstance(aentry, dict):
            if 'DefineSymbol' in aentry:
                roles['define'] = aentry.get('DefineSymbol')
            if 'UseSymbol' in aentry:
                roles['use'] = aentry.get('UseSymbol')
        if roles:
            arg_roles[argname] = roles
    if arg_roles:
        kb_ctx['arg_roles'] = arg_roles
    return kb_ctx

# 针对不同 group 设计 mutation 模板函数

def build_mutations(group: str, cmd: str, args):
    muts = []
    key = args[0] if args else 'k'
    if group == 'hash':
        # 期望 args: key, field, value?
        field = args[1] if len(args) > 1 else 'f'
        value = args[2] if len(args) > 2 else 'v'
        muts.extend([
            (f"HGET {key} {field}", 'probe', 'same_field'),
            (f"HEXISTS {key} {field}", 'probe', 'membership_true'),
            (f"HSET {key} {field} {value}", 'idempotent_repeat', 'same_field'),
            (f"HDEL {key} {field}", 'inverse', 'post_condition_empty'),
        ])
    elif group == 'string':
        muts.extend([
            (f"GET {key}", 'probe', 'value_read'),
            (f"STRLEN {key}", 'probe', 'length_consistent'),
            (f"GETRANGE {key} 0 -1", 'probe', 'value_full_range'),
            (f"SET {key} NEWVAL", 'value_transform', 'mutable_change'),
        ])
    elif group == 'list':
        muts.extend([
            (f"LLEN {key}", 'probe', 'length_probe'),
            (f"LRANGE {key} 0 -1", 'probe', 'range_full'),
            (f"LPUSH {key} X_MUT", 'idempotent_extend', 'length_plus_one'),
            (f"LPOP {key}", 'inverse', 'length_minus_one'),
        ])
    elif group == 'set':
        muts.extend([
            (f"SCARD {key}", 'probe', 'cardinality_probe'),
            (f"SADD {key} member_mut", 'idempotent_extend', 'cardinality_plus_one_or_same'),
            (f"SISMEMBER {key} member_mut", 'probe', 'membership_false_or_true'),
            (f"SREM {key} member_mut", 'inverse', 'cardinality_minus_one_or_zero'),
        ])
    elif group == 'zset':
        # richer zset probes: prioritize count/score/rank probes to improve score/member consistency
        muts.extend([
            (f"ZCARD {key}", 'probe', 'cardinality_probe'),
            (f"ZCOUNT {key} -inf +inf", 'probe', 'cardinality_range_count'),
            (f"ZSCORE {key} member_mut", 'probe', 'score_probe'),
            (f"ZRANK {key} member_mut", 'probe', 'rank_probe'),
            (f"ZADD {key} 1 member_mut", 'idempotent_extend', 'cardinality_plus_one_or_same'),
            (f"ZRANGE {key} 0 -1 WITHSCORES", 'probe', 'ordering_consistent'),
            (f"ZREVRANGE {key} 0 -1 WITHSCORES", 'probe', 'ordering_consistent_reverse'),
            (f"ZREM {key} member_mut", 'inverse', 'cardinality_minus_one_or_zero'),
        ])
    elif group == 'ttl':
        muts.extend([
            (f"TTL {key}", 'probe', 'ttl_state'),
            (f"EXPIRE {key} 60", 'expire_variant', 'ttl_set'),
            (f"TTL {key}", 'probe', 'ttl_positive_after_set'),
            (f"PERSIST {key}", 'inverse', 'ttl_removed'),
        ])
    else:
        # fallback: if we know a kb-derived type mapping was missed, default to echo
        muts.append((f"{cmd} {' '.join(args)}".strip(), 'echo', 'noop'))

    # 去重并截断到 4 个
    seen = set()
    uniq = []
    for m in muts:
        if m[0] not in seen:
            uniq.append(m)
            seen.add(m[0])
    return uniq[:4]

SYSTEM_PROMPT = (
    "You are a Redis mutation synthesis assistant. Given one seed Redis command, "
    "you must output a compact JSON with key 'mutations'. Each mutation has: cmd, category, oracle. "
    "Rules: (1) Do NOT change the key name; (2) Avoid introducing unrelated keys; (3) Keep list/set/zset semantics logical; "
    "(4) Provide at most 4 high-signal mutations; (5) No extra text besides JSON."
)

def build_sample(example_obj):
    cmd = example_obj.get('command') or ''
    args = example_obj.get('args') or []
    raw = example_obj.get('raw') or ' '.join([cmd] + args)
    upper = cmd.upper()
    group = COMMAND_GROUPS.get(upper, 'other')
    # if group is unknown, try to infer from KB context (define/use) to produce higher-signal probes
    kb_ctx = get_kb_context(upper)
    if group == 'other' and kb_ctx:
        # NOTE (2025-09-20): KB-derived mapping - when the command isn't in COMMAND_GROUPS,
        # we attempt to map KB 'define'/'use' symbols to our group templates so that
        # we can emit higher-signal probes instead of defaulting to an echo/noop.
        # This mapping is intentionally conservative and only affects unknown commands.
        sym_to_group = {
            'sorted_set_key': 'zset',
            'list_key': 'list',
            'set_key': 'set',
            'hash_key': 'hash',
            'str_key': 'string',
            'str_key_type_num': 'string',
            'geo_key': 'geo',
            'stream_key': 'stream'
        }
        # prefer 'define' over 'use' when present to reflect key type declaration semantics
        symbols = []
        if 'define' in kb_ctx and isinstance(kb_ctx['define'], list):
            symbols.extend(kb_ctx['define'])
        if 'use' in kb_ctx and isinstance(kb_ctx['use'], list):
            symbols.extend(kb_ctx['use'])
        for s in symbols:
            g = sym_to_group.get(s)
            if g:
                group = g
                # single conservative mapping; stop at first positive mapping
                break
    muts = build_mutations(group, upper, args)
    mutations_json = {"mutations": [
        {"cmd": c, "category": cat, "oracle": oc} for (c, cat, oc) in muts
    ]}
    # inject compact KB context for the command to help the model reason about define/use and arg roles
    kb_ctx = get_kb_context(upper)
    # NOTE: KB_context fragment is injected into the user message as a small machine-readable JSON
    # to help the model preserve member/score semantics (especially for zset). Keep this fragment
    # compact to avoid token inflation.
    # keep the user_content short but include a machine-readable KB_context JSON fragment
    user_content = (
        f"Original: {raw}\n"
        f"Meta: command={upper} group={group} args={json.dumps(args, ensure_ascii=False)}\n"
        f"KB_context: {json.dumps(kb_ctx, ensure_ascii=False)}\n"
        f"Task: Generate up to 4 mutations preserving semantics and return ONLY JSON."
    )
    assistant_content = json.dumps(mutations_json, ensure_ascii=False)
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content}
        ]
    }

def main():
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    records = 0
    with open(OUT_FILE, 'w', encoding='utf-8') as wf:
        for fname in sorted(os.listdir(ENRICHED_DIR)):
            if not fname.endswith('.json'): continue
            fpath = os.path.join(ENRICHED_DIR, fname)
            try:
                data = json.load(open(fpath, 'r', encoding='utf-8'))
            except Exception as e:
                print('skip', fname, e)
                continue
            examples = data.get('examples') or []
            if not examples:
                continue
            # 只取第一条 example，防止数据爆炸；可扩展为多条
            sample = build_sample(examples[0])
            wf.write(json.dumps(sample, ensure_ascii=False) + '\n')
            records += 1
    print(f'Generated {records} samples -> {OUT_FILE}')

if __name__ == '__main__':
    main()
