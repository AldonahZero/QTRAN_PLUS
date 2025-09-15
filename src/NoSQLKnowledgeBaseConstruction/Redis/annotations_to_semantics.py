"""
Extract a semantic knowledge table from Redis.g4 (tagged) and Redis.json annotations.
Output a machine-usable KB that lists, per rule->elem, the actions and resolved types,
plus convenience indexes by symbol type (who defines/uses/invalidates), and scope/alter-order hints.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, DefaultDict
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[3]
IN_DIR = ROOT / "NoSQLFeatureKnowledgeBase" / "Redis" / "inputs" / "grammars"
OUT = ROOT / "NoSQLFeatureKnowledgeBase" / "Redis" / "outputs" / "redis_semantic_kb.json"


def main():
    ann_path = IN_DIR / "Redis.json"
    if not ann_path.exists():
        raise SystemExit(f"Missing {ann_path}")
    ann = json.loads(ann_path.read_text(encoding="utf-8"))
    annotations: Dict[str, Dict[str, Any]] = ann.get("annotations", {})

    # Flatten actions under each tag key
    tags: Dict[str, List[Dict[str, Any]]] = {}
    for tag, entries in annotations.items():
        acts: List[Dict[str, Any]] = []
        # Selector-style entries（包含 selector/def/use 等）
        if "selector" in entries:
            for k, v in entries.items():
                if k == "selector":
                    continue
                if isinstance(v, dict) and "action" in v:
                    acts.append(v)
        # 普通编号 action_0/action_1 ...
        for k, v in entries.items():
            if k.startswith("action_") and isinstance(v, dict):
                acts.append(v)
        # 兼容 0/1/2 这种写法
        for k, v in entries.items():
            if k.isdigit() and isinstance(v, dict) and "action" in v:
                acts.append(v)
        tags[tag] = acts

    by_type_define: DefaultDict[str, List[str]] = defaultdict(list)
    by_type_use: DefaultDict[str, List[str]] = defaultdict(list)
    by_type_invalidate: DefaultDict[str, List[str]] = defaultdict(list)
    scopes: List[Dict[str, Any]] = []
    alter_orders: List[Dict[str, Any]] = []

    for tag, acts in tags.items():
        for a in acts:
            action = a.get("action")
            args = a.get("args", {})
            if action == "DefineSymbol":
                t = args.get("type")
                for tt in _as_list(t):
                    by_type_define[tt].append(tag)
            elif action == "UseSymbol":
                t = args.get("type")
                for tt in _as_list(t):
                    by_type_use[tt].append(tag)
            elif action == "InvalidateSymbol":
                t = args.get("type")
                for tt in _as_list(t):
                    by_type_invalidate[tt].append(tag)
            elif action == "CreateScope":
                scopes.append({"tag": tag, "args": args})
            elif action == "AlterOrder":
                alter_orders.append({"tag": tag, "args": args})

    kb = {
        "by_tag": tags,
        "by_type": {
            "define": by_type_define,
            "use": by_type_use,
            "invalidate": by_type_invalidate
        },
        "scopes": scopes,
        "alter_orders": alter_orders
    }

    # default dicts → normal dicts
    for k in ["define", "use", "invalidate"]:
        kb["by_type"][k] = {kk: vv for kk, vv in kb["by_type"][k].items()}

    OUT.write_text(json.dumps(kb, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Semantic KB written to {OUT}")


def _as_list(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(i) for i in x]
    return [str(x)]


if __name__ == "__main__":
    main()
