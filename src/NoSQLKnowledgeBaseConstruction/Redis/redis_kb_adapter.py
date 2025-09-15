# -*- coding: utf-8 -*-
"""
Redis KB adapter: minimal helpers to use the KB like the SQL side.

Functions:
- select_redis_candidates(sql_semantics) -> list[str]
- build_prompt_with_kb(cmd, sql_semantics) -> dict
- validate_with_kb(cmd, generated_seq) -> (ok: bool, reasons: list[str])

Data sources:
- NoSQLFeatureKnowledgeBase/Redis/outputs/sql_to_redis_mapping.json
- NoSQLFeatureKnowledgeBase/Redis/outputs/redis_semantic_kb.json
- NoSQLFeatureKnowledgeBase/Redis/outputs/redis_commands_knowledge.json
"""
import json
import os
from typing import Any, Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
REDIS_ROOT = os.path.join(ROOT, 'NoSQLFeatureKnowledgeBase', 'Redis')
OUT = os.path.join(REDIS_ROOT, 'outputs')

PATH_MAPPING = os.path.join(OUT, 'sql_to_redis_mapping.json')
PATH_SEMKB = os.path.join(OUT, 'redis_semantic_kb.json')
PATH_CARDS = os.path.join(OUT, 'redis_commands_knowledge.json')


def _load_json(path: str) -> Any:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def select_redis_candidates(sql_semantics: str) -> List[str]:
    """Very small heuristic based on mappings; fallback to common commands."""
    mp = _load_json(PATH_MAPPING) or {}
    mappings = mp.get('mappings', {})
    sql_semantics_up = sql_semantics.upper()
    candidates: List[str] = []
    for k, v in mappings.items():
        if k in sql_semantics_up:
            desc = str(v.get('redis', '')) if isinstance(v, dict) else str(v)
            # Extract possible command tokens (rough split by non-word chars)
            for token in desc.replace('/', ' ').replace(':', ' ').split():
                t = token.strip().lower()
                if t and t.isalpha():
                    candidates.append(t)
    # Minimal fallback
    if not candidates:
        candidates = ['get', 'set', 'zadd', 'zrange', 'hset', 'hget']
    # Dedup preserve order
    seen = set()
    uniq: List[str] = []
    for c in candidates:
        if c not in seen:
            uniq.append(c)
            seen.add(c)
    return uniq


def _get_by_command(cmd: str) -> Dict[str, Any]:
    kb = _load_json(PATH_SEMKB) or {}
    return (kb.get('by_command') or {}).get(cmd.lower(), {})


def _get_examples(cmd: str, max_n: int = 2) -> List[str]:
    cards = _load_json(PATH_CARDS) or {}
    entry = (cards.get('commands') or {}).get(cmd.lower()) or {}
    examples = entry.get('examples') or []
    out: List[str] = []
    for ex in examples[:max_n]:
        if isinstance(ex, dict):
            s = ex.get('example') or ex.get('cmd') or ex.get('text')
            if s:
                out.append(str(s))
        elif isinstance(ex, str):
            out.append(ex)
    return out


def build_prompt_with_kb(cmd: str, sql_semantics: str) -> Dict[str, Any]:
    byc = _get_by_command(cmd)
    prompt = {
        'task': 'redis-generation',
        'target_command': cmd.lower(),
        'sql_semantics': sql_semantics,
        'constraints': {
            'actions': byc.get('actions', {}),
            'args': byc.get('args', {}),
            'alter_orders': [],
        },
        'few_shot': _get_examples(cmd),
        'instructions': [
            'Use only types allowed by args[label].',
            'Satisfy lifecycle: Define before Use; do not Use invalidated resources.',
            'Respect alter-orders if any to avoid non-determinism.',
        ]
    }
    return prompt


def validate_with_kb(cmd: str, generated_seq: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Shallow validation: check presence of required types and basic lifecycle order.
    generated_seq: [{ 'cmd': 'zadd', 'args': { 'elem': 'rank', ... }, 'effect': {...}}]
    """
    reasons: List[str] = []
    byc = _get_by_command(cmd)
    if not byc:
        return True, reasons  # no constraints known

    # Very minimal checks placeholder
    arg_rules = byc.get('args') or {}
    actions = byc.get('actions') or {}

    # Example: if command requires a specific key type in UseSymbol, ensure sequence has a key arg
    use_types = set(actions.get('UseSymbol') or [])
    if use_types:
        # naive: require at least one arg label in first step
        if not generated_seq or not isinstance(generated_seq[0], dict):
            reasons.append('empty-seq')
        # more detailed checks would parse actual args; omitted for brevity

    ok = not reasons
    return ok, reasons


__all__ = [
    'select_redis_candidates',
    'build_prompt_with_kb',
    'validate_with_kb',
]
