"""
Execute Redis parsed examples to collect expected outputs.
Inputs: NoSQLFeatureKnowledgeBase/Redis/parsed_examples/*.json
Outputs: NoSQLFeatureKnowledgeBase/Redis/parsed_examples_enriched/*.json with "expected" field.
Requires a local Redis reachable from database_connector_args.json (host/port/username/password).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[3]
# Ensure repo root on sys.path for `src.*` imports
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import redis as redis_pkg
    from redis.exceptions import RedisError
except Exception:  # pragma: no cover
    redis_pkg = None  # type: ignore
    RedisError = Exception  # type: ignore
EX_DIR = ROOT / "NoSQLFeatureKnowledgeBase" / "Redis" / "parsed_examples"
OUT_DIR = ROOT / "NoSQLFeatureKnowledgeBase" / "Redis" / "parsed_examples_enriched"
CONF = ROOT / "src" / "Tools" / "DatabaseConnect" / "database_connector_args.json"


def get_redis_config():
    if not CONF.exists():
        return {"host": "127.0.0.1", "port": 6379, "username": "", "password": ""}
    data = json.loads(CONF.read_text(encoding="utf-8"))
    return data.get("redis", {"host": "127.0.0.1", "port": 6379, "username": "", "password": ""})


def run_example(client, item: Dict[str, Any]) -> Dict[str, Any]:
    cmd = item.get("command")
    args = item.get("args", [])
    if not cmd:
        return item
    try:
        raw = client.execute_command(cmd, *args)
        # normalize
        def flat(v):
            if isinstance(v, (bytes, bytearray)):
                try:
                    return v.decode("utf-8", errors="replace")
                except Exception:
                    return repr(v)
            if isinstance(v, list):
                return [flat(x) for x in v]
            return str(v)

        fv = flat(raw)
        if isinstance(fv, list):
            item["expected"] = [[str(x)] for x in fv]
        else:
            item["expected"] = [[str(fv)]]
    except Exception as e:
        item["expected_error"] = str(e)
    return item


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = get_redis_config()
    client = None
    if redis_pkg is not None:
        try:
            client = redis_pkg.Redis(host=cfg.get("host"), port=int(cfg.get("port", 6379)), username=(cfg.get("username") or None), password=(cfg.get("password") or None), decode_responses=False)
        except Exception:
            client = None
    for p in EX_DIR.glob("*.json"):
        data = json.loads(p.read_text(encoding="utf-8"))
        examples: List[Dict[str, Any]] = data.get("examples", [])
        enriched = []
        for x in examples:
            xi = dict(x)
            if client is None:
                xi["expected_error"] = "redis client not available"
                enriched.append(xi)
            else:
                enriched.append(run_example(client, xi))
        out = {"command": data.get("command"), "examples": enriched}
        (OUT_DIR / p.name).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Enriched examples written to {OUT_DIR}")


if __name__ == "__main__":
    main()
