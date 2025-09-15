"""
NoSQL 连接与执行：MongoDB 与 Redis 的统一执行入口

用途：
- 为 MongoDB 与 Redis 提供最小可用的执行封装，并返回(结果, 耗时, 错误)。
- 结果尽量标准化为列表字典/标量列表，便于与 Oracle 检查对接。

注意：
- MongoDB 采用 pymongo，输入建议为一个结构化的请求对象（operation, collection, query/pipeline, options）。
- Redis 采用 redis-py，输入建议为命令数组或 {cmd, args} 结构。
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import os

from src.Tools.DatabaseConnect.database_connector import get_database_connector_args

try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
except Exception:  # pragma: no cover
    MongoClient = None  # type: ignore
    PyMongoError = Exception  # type: ignore

try:
    import redis as redis_pkg
    from redis.exceptions import RedisError
except Exception:  # pragma: no cover
    redis_pkg = None  # type: ignore
    RedisError = Exception  # type: ignore


def _canonize_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """将 MongoDB 文档进行稳定化：
    - 去除 _id（可选）
    - 嵌套值递归转字符串，保证可比较
    - 键排序（比较时不依赖键序）
    """
    def normalize(v: Any) -> Any:
        if isinstance(v, dict):
            return {k: normalize(v[k]) for k in sorted(v.keys())}
        if isinstance(v, list):
            return [normalize(x) for x in v]
        try:
            return str(v)
        except Exception:
            return repr(v)

    doc = {k: v for k, v in doc.items() if k != "_id"}
    return {k: normalize(doc[k]) for k in sorted(doc.keys())}


def exec_mongodb_statement(tool: str, exp: str, statement: Dict[str, Any]) -> Tuple[Optional[List[List[str]]], float, Optional[str]]:
    """执行 MongoDB 语句。

    输入约定 statement：
    {
      "database": "<db>",
      "collection": "<col>",
      "operation": "find|aggregate|insert_one|insert_many|update_many|delete_many|distinct|count_documents",
      "query": {...},          # find / count / delete / distinct / update 等
      "projection": {...},     # find
      "sort": [(k, 1|-1)],
      "limit": 100,
      "skip": 0,
      "pipeline": [ ... ],     # aggregate
      "document": {...},       # insert_one
      "documents": [ {...} ],  # insert_many
      "update": {"$set": {...}},
      "key": "field"          # distinct
    }
    返回：([canonized documents] 或 写操作的统计信息), 耗时, 错误
    """
    args = get_database_connector_args("mongodb")
    if MongoClient is None:
        return None, 0.0, "pymongo not installed"

    host, port = args.get("host"), args.get("port")
    username, password = args.get("username"), args.get("password")

    start = time.time()
    try:
        mongo_uri = f"mongodb://{host}:{port}"
        if username:
            auth = f"{username}:{password}@"
            mongo_uri = f"mongodb://{auth}{host}:{port}"

        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        db_name = statement.get("database") or f"{tool}_{exp}_mongodb".lower()
        db = client[db_name]
        col = db[statement.get("collection", "t")]

        op = (statement.get("operation") or "find").lower()
        docs_serialized: Optional[List[List[str]]] = None

        if op == "find":
            cursor = col.find(
                statement.get("query", {}),
                projection=statement.get("projection"),
                skip=int(statement.get("skip", 0)),
                limit=int(statement.get("limit", 0)) or 0,
            )
            if statement.get("sort"):
                cursor = cursor.sort(statement["sort"])  # type: ignore[arg-type]
            docs = list(cursor)
            canon = [_canonize_document(d) for d in docs]
            docs_serialized = [[json.dumps(c, sort_keys=True, ensure_ascii=False)] for c in canon]
        elif op == "aggregate":
            pipeline = statement.get("pipeline", [])
            docs = list(col.aggregate(pipeline))
            canon = [_canonize_document(d) for d in docs]
            docs_serialized = [[json.dumps(c, sort_keys=True, ensure_ascii=False)] for c in canon]
        elif op == "distinct":
            key = statement.get("key")
            values = col.distinct(key, statement.get("query", {}))
            docs_serialized = [[str(v)] for v in values]
        elif op == "count_documents":
            cnt = col.count_documents(statement.get("query", {}))
            docs_serialized = [[str(cnt)]]
        elif op == "insert_one":
            res = col.insert_one(statement.get("document", {}))
            docs_serialized = [["1", str(res.inserted_id)]]
        elif op == "insert_many":
            res = col.insert_many(statement.get("documents", []))
            docs_serialized = [[str(len(res.inserted_ids))]]
        elif op == "update_many":
            res = col.update_many(statement.get("query", {}), statement.get("update", {}))
            docs_serialized = [[str(res.matched_count), str(res.modified_count)]]
        elif op == "delete_many":
            res = col.delete_many(statement.get("query", {}))
            docs_serialized = [[str(res.deleted_count)]]
        else:
            return None, 0.0, f"unsupported mongodb operation: {op}"

        elapsed = time.time() - start
        return docs_serialized, elapsed, None
    except PyMongoError as e:
        return None, 0.0, str(e)
    except Exception as e:  # pragma: no cover
        return None, 0.0, str(e)


def _flatten_redis_value(v: Any) -> Union[str, List[str]]:
    if isinstance(v, (bytes, bytearray)):
        try:
            return v.decode("utf-8", errors="replace")
        except Exception:
            return repr(v)
    if isinstance(v, list):
        return [str(_flatten_redis_value(x)) for x in v]
    return str(v)


def exec_redis_statement(tool: str, exp: str, statement: Union[List[Any], Dict[str, Any]]) -> Tuple[Optional[List[List[str]]], float, Optional[str]]:
    """执行 Redis 命令。

    - statement 若为列表，例如 ["ZADD", "z", 1, "a", 2, "b"].
    - 或者字典 {"cmd": "GET", "args": ["k"]}。

    返回：[[serialized]] 形式的结果，以便与现有 Result 转换器对接。
    """
    args = get_database_connector_args("redis")
    if redis_pkg is None:
        return None, 0.0, "redis-py not installed"

    host, port = args.get("host"), int(args.get("port"))
    username, password = args.get("username"), args.get("password")

    start = time.time()
    try:
        client = redis_pkg.Redis(host=host, port=port, username=username or None, password=password or None, decode_responses=False)

        if isinstance(statement, dict):
            cmd = statement.get("cmd")
            argv = statement.get("args", [])
        else:
            cmd = str(statement[0])
            argv = list(statement[1:])

        # 使用 execute_command 支持任意命令
        raw = client.execute_command(cmd, *argv)
        flat = _flatten_redis_value(raw)

        rows: List[List[str]] = []
        if isinstance(flat, list):
            rows = [[str(x)] for x in flat]
        else:
            rows = [[str(flat)]]

        elapsed = time.time() - start
        return rows, elapsed, None
    except RedisError as e:
        return None, 0.0, str(e)
    except Exception as e:  # pragma: no cover
        return None, 0.0, str(e)


__all__ = [
    "exec_mongodb_statement",
    "exec_redis_statement",
]
