#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Redis Semantic KB Query CLI

Features:
- list-commands [--grep PATTERN]
- show COMMAND [--args] [--json]
- find-type TYPE [--action DefineSymbol|UseSymbol|InvalidateSymbol]
- tag2cmd TAG
- list-tags [--cmd COMMAND]

Data source: NoSQLFeatureKnowledgeBase/Redis/outputs/redis_semantic_kb.json
"""

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
KB_PATH = os.path.join(
    ROOT,
    "NoSQLFeatureKnowledgeBase",
    "Redis",
    "outputs",
    "redis_semantic_kb.json",
)


def load_kb() -> Dict[str, Any]:
    if not os.path.exists(KB_PATH):
        print(f"KB not found: {KB_PATH}", file=sys.stderr)
        sys.exit(2)
    with open(KB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_list_commands(kb: Dict[str, Any], args: argparse.Namespace) -> None:
    bc = kb.get("by_command", {})
    names = sorted(bc.keys())
    if args.grep:
        pat = re.compile(args.grep, re.IGNORECASE)
        names = [n for n in names if pat.search(n)]
    for n in names:
        print(n)


def _print_actions(actions: Dict[str, Any]) -> None:
    for act in sorted(actions.keys()):
        vals = actions[act]
        if isinstance(vals, list):
            print(f"  {act}:")
            for v in vals:
                print(f"    - {v}")
        else:
            print(f"  {act}: {vals}")


def _print_args(args_map: Dict[str, Any]) -> None:
    for label in sorted(args_map.keys()):
        print(f" arg[{label}] :")
        acts = args_map[label]
        _print_actions(acts)


def cmd_show(kb: Dict[str, Any], args: argparse.Namespace) -> None:
    bc = kb.get("by_command", {})
    entry = bc.get(args.command.lower())
    if not entry:
        print(f"Command not found: {args.command}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps(entry, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(f"Command: {args.command.lower()}")
    print(" actions:")
    _print_actions(entry.get("actions", {}))
    if args.args:
        print(" args:")
        _print_args(entry.get("args", {}))
    print(" tags:")
    for t in entry.get("tags", []):
        print(f"  - {t}")


def cmd_find_type(kb: Dict[str, Any], args: argparse.Namespace) -> None:
    bc = kb.get("by_command", {})
    needle = args.type
    which = args.action
    found = []
    for cmd, entry in bc.items():
        actions = entry.get("actions", {})
        if which:
            types = actions.get(which, [])
            if needle in types:
                found.append((cmd, which, "(command)"))
        else:
            for act, types in actions.items():
                if isinstance(types, list) and needle in types:
                    found.append((cmd, act, "(command)"))
        # Search in args
        for label, acts in entry.get("args", {}).items():
            if which:
                types = acts.get(which, [])
                if isinstance(types, list) and needle in types:
                    found.append((cmd, which, label))
            else:
                for act, types in acts.items():
                    if isinstance(types, list) and needle in types:
                        found.append((cmd, act, label))
    if not found:
        print("No matches.")
        return
    for cmd, act, label in sorted(found):
        print(f"{cmd:16s} {act:18s} {label}")


def cmd_tag2cmd(kb: Dict[str, Any], args: argparse.Namespace) -> None:
    t2c = kb.get("tag_to_command", {})
    tag = args.tag
    print(t2c.get(tag, "<not-found>"))


def cmd_list_tags(kb: Dict[str, Any], args: argparse.Namespace) -> None:
    if args.command:
        bc = kb.get("by_command", {})
        entry = bc.get(args.command.lower())
        if not entry:
            print(f"Command not found: {args.command}", file=sys.stderr)
            sys.exit(1)
        for t in entry.get("tags", []):
            print(t)
        return
    # otherwise list all
    for t in sorted(kb.get("tag_to_command", {}).keys()):
        print(t)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Query Redis Semantic KB")
    sub = p.add_subparsers(dest="subcmd", required=True)

    sp = sub.add_parser("list-commands", help="List known commands")
    sp.add_argument("--grep", help="Filter by regex", default=None)
    sp.set_defaults(func=cmd_list_commands)

    sp = sub.add_parser("show", help="Show command detail")
    sp.add_argument("command")
    sp.add_argument("--args", action="store_true", help="Show per-arg actions")
    sp.add_argument("--json", action="store_true", help="Raw JSON output")
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("find-type", help="Find commands using a type")
    sp.add_argument("type", help="Type name to search (e.g., sorted_set_key)")
    sp.add_argument("--action", choices=["DefineSymbol", "UseSymbol", "InvalidateSymbol"], help="Restrict to specific action")
    sp.set_defaults(func=cmd_find_type)

    sp = sub.add_parser("tag2cmd", help="Map tag to command")
    sp.add_argument("tag", help="e.g., AppendRule1->elem")
    sp.set_defaults(func=cmd_tag2cmd)

    sp = sub.add_parser("list-tags", help="List tags (optionally for a command)")
    sp.add_argument("--command", help="Command name to filter")
    sp.set_defaults(func=cmd_list_tags)

    return p


def main(argv: List[str] = None) -> None:
    parser = build_parser()
    ns = parser.parse_args(argv)
    kb = load_kb()
    ns.func(kb, ns)


if __name__ == "__main__":
    main()
