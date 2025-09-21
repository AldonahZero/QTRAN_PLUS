"""
数据库连接与执行抽象：统一不同引擎的连接池与 SQL 执行

作用概述：
- 为 MySQL/MariaDB/TiDB/Postgres/SQLite/DuckDB/ClickHouse/MonetDB 提供统一的连接与执行接口。
- 提供按测试场景命名隔离的库名/文件名策略，支持数据库清理（database_clear）。
- 供转换与变异阶段调用 exec_sql_statement 执行 SQL 并返回结果/耗时/错误。
"""

# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/8/24 9:57
# @Author  : shaocanfan
# @File    : database_connector.py

import pymysql
from sqlalchemy import text, exc, PoolProxiedConnection
import redis  # redis-py client
import json
from src.Tools.json_utils import make_json_safe
from sqlalchemy.exc import OperationalError
import time
from sqlalchemy import create_engine
import subprocess
import os
from src.Tools.DatabaseConnect.docker_create import run_container
import threading
import sys
import socket
import base64

try:
    import requests  # For Consul HTTP API
except Exception:  # pragma: no cover
    requests = None  # type: ignore

current_file_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file_path)


class DatabaseConnectionPool:
    def __init__(
        self,
        dbType,
        host,
        port,
        username,
        password,
        dbname,
        pool_size=20,
        max_overflow=20,
    ):
        self.dbType = dbType.upper()
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.dbname = dbname
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.engine = None
        self.create_engine()

    # 检查连接是否成功
    def check_connection(self):
        try:
            with self.engine.connect() as connection:
                self.execSQL("SELECT 1;")
            return True
        except OperationalError as e:
            print(f"连接失败: {e}")
            return False

    def create_engine(self):
        try:
            if self.dbType in ["MYSQL", "MARIADB", "TIDB"]:
                self.engine = create_engine(
                    f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.dbname}",
                    pool_size=self.pool_size,
                    max_overflow=self.max_overflow,
                    isolation_level="READ COMMITTED",
                )
            elif self.dbType == "POSTGRES":
                self.engine = create_engine(
                    f"postgresql+psycopg2://{self.username}:{self.password}@{self.host}:{self.port}/{self.dbname}",
                    pool_size=self.pool_size,
                    max_overflow=self.max_overflow,
                )
            elif self.dbType == "MONETDB":
                self.engine = create_engine(
                    f"monetdb+pymonetdb://{self.username}:{self.password}@{self.host}:{self.port}/{self.dbname}",
                    pool_size=self.pool_size,
                )
            elif self.dbType == "SQLITE":
                # For SQLite, it uses a file path, not a typical "host/database" format
                db_path = f"sqlite:///{os.path.join(current_dir, self.dbname)}.db"
                # db_path = f'sqlite:///{self.dbname}'
                self.engine = create_engine(
                    db_path, pool_size=self.pool_size, max_overflow=self.max_overflow
                )
            elif self.dbType == "CLICKHOUSE":
                self.engine = create_engine(
                    f"clickhouse+http://{self.username}:{self.password}@{self.host}:{self.port}/{self.dbname}",
                    pool_size=self.pool_size,
                    max_overflow=self.max_overflow,
                )
            elif self.dbType == "OCEANBASE":
                # For OceanBase, if SQLAlchemy is not supported, you would use a different mechanism
                self.engine = None
            elif self.dbType == "DUCKDB":
                # For duckdb, it uses a file path, not a typical "host/database" format
                db_path = f"duckdb:///{os.path.join(current_dir, self.dbname)}.duckdb"
                # db_path = f'duckdb:///{self.dbname}'
                self.engine = create_engine(
                    db_path, pool_size=self.pool_size, max_overflow=self.max_overflow
                )
            else:
                raise ValueError("Unsupported database type")
        except exc.SQLAlchemyError as e:
            print(f"Failed to create engine: {e}")
            raise

    def close(self):
        try:
            if self.engine:
                self.engine.dispose()  # Dispose the engine to close all connections
        except Exception as e:
            print(f"Failed to close database connection: {e}")
            raise

    def execSQL(self, query):
        start_time = time.time()  # 开始计时
        affected_rows = 0  # 初始化受影响的行数
        result = None  # 初始化结果为 None
        try:
            if self.dbType == "OCEANBASE":
                conn = pymysql.connect(
                    host=self.host,
                    port=int(self.port),
                    user=self.username,
                    password=self.password,
                    database=self.dbname,
                )
                cursor = conn.cursor()
                cursor.execute(query)
                affected_rows = cursor.rowcount
                if (
                    query.strip()
                    .upper()
                    .startswith(("INSERT", "UPDATE", "DELETE", "CREATE"))
                ):
                    conn.commit()  # 提交事务
                else:
                    result = cursor.fetchall()  # 获取查询结果
                conn.close()
            elif self.dbType == "POSTGRES":
                with self.engine.connect() as connection:
                    # 设置自动提交
                    connection.execution_options(isolation_level="AUTOCOMMIT")
                    res = connection.execute(text(query))
                    affected_rows = res.rowcount
                    if (
                        query.strip()
                        .upper()
                        .startswith(("INSERT", "UPDATE", "DELETE", "CREATE"))
                    ):
                        connection.commit()
                    else:
                        # 对于其他类型的查询，如 SELECT，获取结果
                        result = res.fetchall()
            else:
                with self.engine.connect() as connection:
                    res = connection.execute(text(query))
                    affected_rows = res.rowcount
                    if (
                        query.strip()
                        .upper()
                        .startswith(("INSERT", "UPDATE", "DELETE", "CREATE"))
                    ):
                        connection.commit()
                    else:
                        # 对于其他类型的查询，如 SELECT，获取结果
                        result = res.fetchall()
            end_time = time.time()  # 结束计时
            execution_time = end_time - start_time  # 计算执行时间
            print("Affected rows:", affected_rows)
            return result, execution_time, None  # 返回结果和执行时间
        except Exception as e:
            error_message = f"Error executing '{query}':" + str(e)
            print(f"Error executing '{query}':", e)
            # return None, 0 , error_message
            return None, 0, str(e)


# 每次执行后要清除数据库内的所有表格
def database_clear(tool, exp, dbType):
    """按场景重置数据库：删除文件型库或在容器内重建/清空表。"""
    args = get_database_connector_args(dbType.lower())
    args["dbname"] = (
        f"{tool}_{exp}_{dbType}".lower()
        if "tlp" not in exp
        else f"{tool}_tlp_{dbType}".lower()
    )
    # 特殊处理：删除对应的db文件即可
    if dbType.lower() in ["sqlite"]:
        db_filepath = os.path.join(current_dir, f'{args["dbname"]}.db')
        if os.path.exists(db_filepath):
            print(db_filepath)
            os.remove(db_filepath)
            print(db_filepath + "已删除")
        else:
            print(db_filepath + "不存在")
    # 新增：Redis 单独处理
    elif dbType.lower() == "redis":
        if redis is None:
            print("redis 库未安装，无法清理")
            return
        try:
            r = redis.Redis(
                host=args.get("host", "127.0.0.1"),
                port=int(args.get("port", 6379)),
                username=args.get("username") or None,
                password=args.get("password") or None,
                decode_responses=False,
            )
            r.flushdb()
            print(args["dbname"] + " (redis) 已清空")
        except Exception as e:
            print("Redis 清理失败:", e)
        return
    elif dbType.lower() == "mongodb":
        # MongoDB: 删除整个数据库（如果存在）
        try:
            try:
                from pymongo import MongoClient  # 延迟导入，避免未安装时崩溃
            except ImportError:
                print("pymongo 未安装，无法清理 mongodb 数据库")
                return
            host = args.get("host", "127.0.0.1")
            port = int(args.get("port", 27017))
            username = args.get("username") or None
            password = args.get("password") or None
            # 构建连接 URI（支持无认证与用户密码）
            if username and password:
                uri = f"mongodb://{username}:{password}@{host}:{port}/admin"
            else:
                uri = f"mongodb://{host}:{port}/"
            client = MongoClient(uri, serverSelectionTimeoutMS=3000)
            dbname = args["dbname"]
            if dbname in client.list_database_names():
                client.drop_database(dbname)
                print(f"{dbname} (mongodb) 已删除")
            else:
                print(f"{dbname} (mongodb) 不存在")
        except Exception as e:
            print("MongoDB 清理失败:", e)
        return
    elif dbType.lower() == "memcached":
        # 直接 flush_all
        try:
            import socket as _s

            host = args.get("host", "127.0.0.1")
            port = int(args.get("port", 11211))
            with _s.create_connection((host, port), timeout=3) as sk:
                sk.sendall(b"flush_all\r\n")
                resp = sk.recv(128).decode(errors="replace").strip()
            if resp.lower().startswith("ok") or resp.lower().startswith("reset"):
                print(args["dbname"] + " (memcached) 已清空")
            else:
                print("memcached flush_all 返回:" + resp)
        except Exception as e:
            print("Memcached 清理失败:", e)
        return
    elif dbType.lower() == "etcd":
        # 使用 etcdctl 删除全部 key: etcdctl del "" --from-key
        try:
            container = args.get("container_name", "etcd_QTRAN")
            subprocess.run(
                [
                    "docker",
                    "exec",
                    container,
                    "etcdctl",
                    "--endpoints=localhost:2379",
                    "del",
                    "",
                    "--from-key",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            print(args["dbname"] + " (etcd) 全部键已删除")
        except Exception as e:
            print("etcd 清理失败:", e)
        return
    elif dbType.lower() == "consul":
        # 遍历列出所有键然后逐个删除（避免依赖额外工具）。
        try:
            import requests as _req

            host = args.get("host", "127.0.0.1")
            port = int(args.get("port", 8500))
            base = f"http://{host}:{port}/v1/kv"
            # 获取所有 key
            r = _req.get(f"{base}/?recurse=true")
            if r.status_code == 200:
                try:
                    items = r.json()
                except Exception:
                    items = []
                deleted = 0
                for entry in items or []:
                    k = entry.get("Key")
                    if not k:
                        continue
                    dr = _req.delete(f"{base}/{k}")
                    if dr.status_code == 200 and dr.text.strip() == "true":
                        deleted += 1
                print(f"{args['dbname']} (consul) 已删除 {deleted} 个键")
            elif r.status_code == 404:
                print(args["dbname"] + " (consul) 无键")
            else:
                print("Consul 列取键失败 status=" + str(r.status_code))
        except Exception as e:
            print("Consul 清理失败:", e)
        return
    elif dbType.lower() in ["duckdb"]:
        db_filepath = os.path.join(current_dir, f'{args["dbname"]}.duckdb')
        if os.path.exists(db_filepath):
            print(db_filepath)
            os.remove(db_filepath)
            print(db_filepath + "已删除")
        else:
            print(db_filepath + "不存在")
    elif dbType.lower() in ["monetdb"]:
        container_name = args["container_name"]
        # 停止数据库
        subprocess.run(
            ["docker", "exec", container_name, "monetdb", "stop", args["dbname"]]
        )
        subprocess.run(
            [
                "docker",
                "exec",
                container_name,
                "monetdb",
                "destroy",
                "-f",
                args["dbname"],
            ]
        )
        subprocess.run(
            ["docker", "exec", container_name, "monetdb", "create", args["dbname"]]
        )
        subprocess.run(
            ["docker", "exec", container_name, "monetdb", "release", args["dbname"]]
        )
        subprocess.run(
            ["docker", "exec", container_name, "monetdb", "start", args["dbname"]]
        )
        print(dbType + "," + args["dbname"] + "重置成功")
    else:
        pool = DatabaseConnectionPool(
            args["dbType"],
            args["host"],
            args["port"],
            args["username"],
            args["password"],
            f"{tool.lower()}_temp_{dbType.lower()}",
        )
        with open(
            os.path.join(current_dir, "database_clear", dbType.lower() + ".json"),
            "r",
            encoding="utf-8",
        ) as rf:
            ddls = json.load(rf)
        for ddl in ddls:
            ddl = ddl.replace("db_name", args["dbname"])
            pool.execSQL(ddl)
        print(args["dbname"] + "重置成功")
        pool.close()


# -------------------- Unified Normalization Helper -------------------- #
def _unify_result(op_type: str, success: bool, value, meta: dict | None = None):
    """Return a normalized result dict following doc/kb/kv_nosql_return_structures.md.

    Structure:
    {"type": op_type, "success": bool, "value": <scalar/list/dict/None>, "meta": {...optional...}}
    Meta keys are pruned if empty.
    """
    out = {"type": op_type, "success": success, "value": value}
    if meta:
        # Remove None values to keep output compact
        meta_clean = {k: v for k, v in meta.items() if v is not None}
        if meta_clean:
            out["meta"] = meta_clean
    return out


# -------------------- Memcached Execution & Normalization ------------- #
def exec_memcached_command(conn_args, tool, exp, command_text: str):
    """Execute a single memcached command via plain TCP socket.

    Supported core commands (simple subset):
      - set <key> <flags> <exptime> <bytes> [noreply]\n<value>\n
      - get <key>\n
      - delete <key>\n
      - incr/decr <key> <value>\n
    Normalization mapping:
      set -> kv_set (success if STORED)
      get -> kv_get (value=string or None)
      delete -> kv_delete (success if DELETED)
      incr/decr -> kv_set (value=new numeric string)
    Unknown commands fall back to raw textual response.
    """
    host = conn_args.get("host", "127.0.0.1")
    port = int(conn_args.get("port", 11211))
    if not command_text or not command_text.strip():
        return {"type": "empty", "value": None}, 0, None
    start = time.time()
    try:
        with socket.create_connection((host, port), timeout=3) as sock:
            sock.settimeout(3)
            # Write command. For set we need to include data line already in command_text.
            send_bytes = command_text.strip() + (
                "\r\n" if not command_text.endswith("\n") else ""
            )
            sock.sendall(send_bytes.encode())

            # For set with data block, ensure caller provided trailing CRLF after value.
            # We'll read until END or STORED/NOT_STORED/ERROR line encountered.
            buf = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                # Break heuristics
                if (
                    b"\r\nEND\r\n" in buf
                    or b"STORED\r\n" in buf
                    or b"NOT_STORED\r\n" in buf
                    or b"DELETED\r\n" in buf
                    or b"NOT_FOUND\r\n" in buf
                    or b"ERROR\r\n" in buf
                ):
                    break
        raw_text = buf.decode(errors="replace")
        first_line = raw_text.splitlines()[0] if raw_text else ""
        tokens = command_text.split()
        primary = tokens[0].lower()
        norm = None
        if primary == "get":
            # Format: VALUE <key> <flags> <bytes> \r\n <data> \r\n END
            if raw_text.startswith("VALUE"):
                lines = raw_text.splitlines()
                if len(lines) >= 3 and lines[-1] == "END":
                    header = lines[0].split()
                    val_line = lines[1]
                    value = val_line  # raw bytes (already decoded)
                    norm = _unify_result(
                        "kv_get", True, value, meta={"raw_code": "VALUE"}
                    )
                else:
                    norm = _unify_result(
                        "kv_get", False, None, meta={"raw_code": first_line}
                    )
            elif first_line == "END":  # key miss
                norm = _unify_result("kv_get", True, None, meta={"raw_code": "END"})
            else:
                norm = _unify_result(
                    "kv_get", False, None, meta={"raw_code": first_line}
                )
        elif primary == "set":
            success = first_line == "STORED"
            norm = _unify_result("kv_set", success, None, meta={"raw_code": first_line})
        elif primary == "delete":
            success = first_line == "DELETED"
            norm = _unify_result(
                "kv_delete", success, None, meta={"raw_code": first_line}
            )
        elif primary in {"incr", "decr"}:
            # Response is the new value or NOT_FOUND / ERROR
            if first_line.isdigit():
                norm = _unify_result(
                    "kv_set", True, first_line, meta={"raw_code": first_line}
                )
            else:
                norm = _unify_result(
                    "kv_set", False, None, meta={"raw_code": first_line}
                )
        else:
            norm = _unify_result(
                "unsupported", True, raw_text.strip(), meta={"raw_code": first_line}
            )
        return norm, time.time() - start, None
    except Exception as e:
        return None, 0, str(e)


# -------------------- Consul Execution & Normalization ---------------- #
def exec_consul_command(conn_args, tool, exp, command_text: str):
    """Execute simplified Consul KV operations via HTTP API.

    Supported textual forms (space separated):
      PUT <key> <value>
      GET <key>
      DELETE <key>
      RANGE <prefix>
    """
    if requests is None:
        return None, 0, "requests not installed"
    host = conn_args.get("host", "127.0.0.1")
    port = int(conn_args.get("port", 8500))
    base = f"http://{host}:{port}/v1/kv"
    if not command_text or not command_text.strip():
        return {"type": "empty", "value": None}, 0, None
    parts = command_text.strip().split()
    op = parts[0].upper()
    start = time.time()
    try:
        if op == "PUT" and len(parts) >= 3:
            key = parts[1]
            value = " ".join(parts[2:])
            resp = requests.put(f"{base}/{key}", data=value.encode())
            success = resp.status_code == 200 and resp.text.strip() == "true"
            norm = _unify_result(
                "kv_set", success, None, meta={"raw_code": resp.text.strip()}
            )
        elif op == "GET" and len(parts) == 2:
            key = parts[1]
            resp = requests.get(f"{base}/{key}")
            if resp.status_code == 200:
                try:
                    arr = resp.json()
                    if arr:
                        entry = arr[0]
                        val_b64 = entry.get("Value")
                        value = base64.b64decode(val_b64).decode() if val_b64 else None
                        norm = _unify_result(
                            "kv_get",
                            True,
                            value,
                            meta={
                                "indices": {
                                    "CreateIndex": entry.get("CreateIndex"),
                                    "ModifyIndex": entry.get("ModifyIndex"),
                                },
                                "flags": entry.get("Flags"),
                                "raw_code": "FOUND",
                            },
                        )
                    else:
                        norm = _unify_result(
                            "kv_get", True, None, meta={"raw_code": "EMPTY"}
                        )
                except Exception as je:  # pragma: no cover
                    return None, 0, f"json parse error: {je}"
            elif resp.status_code == 404:
                norm = _unify_result(
                    "kv_get", True, None, meta={"raw_code": "NOT_FOUND"}
                )
            else:
                norm = _unify_result(
                    "kv_get", False, None, meta={"raw_code": str(resp.status_code)}
                )
        elif op == "DELETE" and len(parts) == 2:
            key = parts[1]
            resp = requests.delete(f"{base}/{key}")
            success = resp.status_code == 200 and resp.text.strip() == "true"
            norm = _unify_result(
                "kv_delete", success, None, meta={"raw_code": resp.text.strip()}
            )
        elif op == "RANGE" and len(parts) == 2:
            prefix = parts[1]
            resp = requests.get(f"{base}/{prefix}", params={"recurse": "true"})
            if resp.status_code == 200:
                try:
                    arr = resp.json()
                except Exception as je:
                    return None, 0, f"json parse error: {je}"
                items = []
                for entry in arr:
                    val_b64 = entry.get("Value")
                    value = base64.b64decode(val_b64).decode() if val_b64 else None
                    items.append({"key": entry.get("Key"), "value": value})
                norm = _unify_result(
                    "kv_range", True, items, meta={"count": len(items)}
                )
            else:
                norm = _unify_result(
                    "kv_range", False, None, meta={"raw_code": str(resp.status_code)}
                )
        else:
            norm = _unify_result(
                "unsupported", False, None, meta={"raw_code": command_text.split()[0]}
            )
        return norm, time.time() - start, None
    except Exception as e:
        return None, 0, str(e)


# -------------------- etcd Execution & Normalization ------------------ #
def exec_etcd_command(conn_args, tool, exp, command_text: str):
    """Execute simplified etcdctl commands via docker exec (etcdctl -w json ...).

    Supported textual forms:
      PUT <key> <value>
      GET <key>
      RANGE <prefix>
      DELETE <key>
    Implementation detail: we rely on container name in args[container_name].
    """
    container = conn_args.get("container_name") or "etcd_QTRAN"
    port = int(conn_args.get("port", 2379))  # not directly used (docker exec)
    if not command_text or not command_text.strip():
        return {"type": "empty", "value": None}, 0, None
    parts = command_text.strip().split()
    op = parts[0].upper()
    start = time.time()
    base_cmd = [
        "docker",
        "exec",
        container,
        "etcdctl",
        "--endpoints=localhost:2379",
        "-w",
        "json",
    ]
    try:
        if op == "PUT" and len(parts) >= 3:
            key = parts[1]
            value = " ".join(parts[2:])
            proc = subprocess.run(
                base_cmd + ["put", key, value],
                capture_output=True,
                text=True,
                timeout=8,
            )
            success = proc.returncode == 0
            meta = {}
            try:
                data = json.loads(proc.stdout or "{}")
                header = data.get("header", {})
                meta["revision"] = header.get("revision")
            except Exception:
                pass
            norm = _unify_result("kv_set", success, None, meta=meta)
        elif op == "GET" and len(parts) == 2:
            key = parts[1]
            proc = subprocess.run(
                base_cmd + ["get", key], capture_output=True, text=True, timeout=8
            )
            if proc.returncode == 0:
                try:
                    data = json.loads(proc.stdout or "{}")
                    kvs = data.get("kvs", [])
                    if kvs:
                        value_b64 = kvs[0].get("value")
                        value = (
                            base64.b64decode(value_b64).decode() if value_b64 else None
                        )
                        norm = _unify_result(
                            "kv_get",
                            True,
                            value,
                            meta={
                                "version": kvs[0].get("version"),
                                "revision": data.get("header", {}).get("revision"),
                            },
                        )
                    else:
                        norm = _unify_result(
                            "kv_get", True, None, meta={"raw_code": "EMPTY"}
                        )
                except Exception as je:
                    return None, 0, f"json parse error: {je}"
            else:
                norm = _unify_result(
                    "kv_get", False, None, meta={"raw_code": proc.stderr.strip()[:60]}
                )
        elif op == "RANGE" and len(parts) == 2:
            prefix = parts[1]
            proc = subprocess.run(
                base_cmd + ["get", prefix, "--prefix"],
                capture_output=True,
                text=True,
                timeout=12,
            )
            if proc.returncode == 0:
                try:
                    data = json.loads(proc.stdout or "{}")
                    kvs = data.get("kvs", [])
                    items = []
                    for kv in kvs:
                        key_dec = base64.b64decode(kv.get("key", "").encode()).decode()
                        val_b64 = kv.get("value")
                        val_dec = (
                            base64.b64decode(val_b64).decode() if val_b64 else None
                        )
                        items.append({"key": key_dec, "value": val_dec})
                    norm = _unify_result(
                        "kv_range",
                        True,
                        items,
                        meta={
                            "count": len(items),
                            "revision": data.get("header", {}).get("revision"),
                        },
                    )
                except Exception as je:
                    return None, 0, f"json parse error: {je}"
            else:
                norm = _unify_result(
                    "kv_range", False, None, meta={"raw_code": proc.stderr.strip()[:60]}
                )
        elif op == "DELETE" and len(parts) == 2:
            key = parts[1]
            proc = subprocess.run(
                base_cmd + ["del", key], capture_output=True, text=True, timeout=8
            )
            success = proc.returncode == 0
            deleted = None
            try:
                data = json.loads(proc.stdout or "{}")
                deleted = data.get("deleted")
            except Exception:
                pass
            norm = _unify_result("kv_delete", success, None, meta={"deleted": deleted})
        else:
            norm = _unify_result("unsupported", False, None, meta={"raw_code": op})
        return norm, time.time() - start, None
    except Exception as e:
        return None, 0, str(e)


def exec_sql_statement(tool, exp, dbType, sql_statement):
    """统一入口：根据 dbType 获取连接参数并执行 SQL，返回 (结果, 耗时, 错误)。"""
    # 创建连接池实例
    if tool.lower() in ["sqlancer", "sqlright"]:
        tool = "sqlancer"
    args = get_database_connector_args(dbType.lower())

    args["dbname"] = (
        f"{tool}_{exp}_{dbType}".lower()
        if "tlp" not in exp
        else f"{tool}_tlp_{dbType}".lower()
    )

    nosql_targets = {"redis", "mongodb", "memcached", "etcd", "consul"}
    # Redis 特殊处理：走单独的执行函数（不使用 SQLAlchemy）
    if dbType.lower() in nosql_targets:
        lower = dbType.lower()
        if lower == "redis":
            return exec_redis_command(args, tool, exp, sql_statement)
        if lower == "mongodb":
            if isinstance(sql_statement, dict):
                return exec_mongodb_json_operation(args, tool, exp, sql_statement)
            if isinstance(sql_statement, str):
                stripped = sql_statement.strip()
                if stripped.startswith("{") and stripped.endswith("}"):
                    try:
                        import json as _json

                        op_obj = _json.loads(stripped)
                        if isinstance(op_obj, dict) and op_obj.get("op"):
                            return exec_mongodb_json_operation(args, tool, exp, op_obj)
                    except Exception:
                        pass
                return exec_mongodb_command(args, tool, exp, sql_statement)
            return (
                None,
                0,
                f"unsupported mongo statement type: {type(sql_statement).__name__}",
            )
        if lower == "memcached":
            if not isinstance(sql_statement, str):
                return None, 0, "memcached command must be string"
            return exec_memcached_command(args, tool, exp, sql_statement)
        if lower == "consul":
            if not isinstance(sql_statement, str):
                return None, 0, "consul command must be string"
            return exec_consul_command(args, tool, exp, sql_statement)
        if lower == "etcd":
            if not isinstance(sql_statement, str):
                return None, 0, "etcd command must be string"
            return exec_etcd_command(
                {**args, "container_name": args.get("container_name", "etcd_QTRAN")},
                tool,
                exp,
                sql_statement,
            )

    # 先检查容器是否打开，即数据库是否能正常链接，如果没有正常链接则打开容器
    pool = DatabaseConnectionPool(
        args["dbType"],
        args["host"],
        args["port"],
        args["username"],
        args["password"],
        args["dbname"],
    )

    if dbType not in ["clickhouse"] and not pool.check_connection():
        run_container(tool, exp, dbType)
    result, exec_time, error_message = pool.execSQL(sql_statement)
    pool.close()
    return result, exec_time, error_message


def exec_redis_command(conn_args, tool, exp, redis_command):
    """
    执行 Redis 命令，返回统一三元组：(标准化结果, 耗时, 错误)。

    约定：
    - redis_command: 单条命令文本，支持简单多空格，区分大小写不敏感。
    - 返回的 result 结构：dict: {"type": <str>, "value": <JSON-able>} 或 None。
    - 错误时 result=None, time=0, error=错误字符串。
    - 不支持管道/多条以分号分隔的复合命令（可后续扩展）。
    """
    if redis is None:
        return None, 0, "redis library not installed"
    start = time.time()
    try:
        host = conn_args.get("host", "127.0.0.1")
        port = int(conn_args.get("port", 6379))
        username = conn_args.get("username") or None
        password = conn_args.get("password") or None
        # 建立连接（短连接模式；如需性能可加入连接池/全局缓存）
        client = redis.Redis(
            host=host,
            port=port,
            username=username,
            password=password,
            decode_responses=False,
        )

        # 解析命令：按空白切分，首元素为命令
        if not redis_command or not redis_command.strip():
            return {"type": "empty", "value": None}, 0, None
        # 去掉结尾可能的分号
        cmd_text = redis_command.strip()
        if cmd_text.endswith(";"):
            cmd_text = cmd_text[:-1]
        parts = cmd_text.split()
        if not parts:
            return {"type": "empty", "value": None}, 0, None
        command = parts[0].upper()
        args = parts[1:]

        # 定义一个执行并标准化的内部函数
        def wrap_value(raw):
            # bytes -> utf-8 str; list/tuple -> 递归; set -> list 排序; int/float 直接
            def convert(v):
                if isinstance(v, bytes):
                    try:
                        return v.decode("utf-8")
                    except Exception:
                        return v.hex()
                if isinstance(v, (list, tuple)):
                    return [convert(x) for x in v]
                if isinstance(v, set):
                    return sorted([convert(x) for x in v])
                if isinstance(v, dict):
                    return {convert(k): convert(val) for k, val in v.items()}
                return v

            cv = convert(raw)
            value_type = (
                "null"
                if cv is None
                else (
                    "int"
                    if isinstance(cv, int)
                    else (
                        "float"
                        if isinstance(cv, float)
                        else (
                            "list"
                            if isinstance(cv, list)
                            else "dict" if isinstance(cv, dict) else "str"
                        )
                    )
                )
            )
            return {"type": value_type, "value": cv}

        # 基于常见命令做分派；其它命令使用 generic execute_command
        result_raw = None
        if command in {"GET", "SET", "DEL", "EXISTS", "INCR", "DECR", "LLEN", "PING"}:
            if command == "GET":
                result_raw = client.get(*args)
            elif command == "SET":
                # SET key value -> True/False
                result_raw = client.set(*args)
            elif command == "DEL":
                result_raw = client.delete(*args)
            elif command == "EXISTS":
                result_raw = client.exists(*args)
            elif command == "INCR":
                result_raw = client.incr(*args)
            elif command == "DECR":
                result_raw = client.decr(*args)
            elif command == "LLEN":
                result_raw = client.llen(*args)
            elif command == "PING":
                result_raw = client.ping()
        elif command in {"LRANGE"}:
            # LRANGE key start stop
            if len(args) != 3:
                raise ValueError("LRANGE requires 3 arguments: key start stop")
            result_raw = client.lrange(args[0], int(args[1]), int(args[2]))
        elif command in {"SMEMBERS"}:
            result_raw = client.smembers(*args)
        elif command in {"SISMEMBER"}:
            if len(args) != 2:
                raise ValueError("SISMEMBER requires key member")
            result_raw = client.sismember(args[0], args[1])
        elif command in {"HGETALL"}:
            result_raw = client.hgetall(*args)
        elif command in {"HGET"}:
            if len(args) != 2:
                raise ValueError("HGET requires key field")
            result_raw = client.hget(args[0], args[1])
        else:
            # 回退：尝试直接执行底层命令（可能失败）
            try:
                result_raw = client.execute_command(command, *args)
            except Exception as e:
                # 未知命令直接返回错误
                return None, 0, f"Unsupported or failed command '{command}': {e}"

        exec_time = time.time() - start
        norm = wrap_value(result_raw)
        return norm, exec_time, None
    except Exception as e:
        return None, 0, str(e)


# ...existing code...


def exec_mongodb_json_operation(conn_args, tool, exp, op_obj):
    """
    执行基于我们约束 schema 的 MongoDB JSON 操作对象。
    期待结构:
      {
        "op": "insertOne|updateOne|find|findOne|deleteOne|createCollection",
        "collection": "kv",
        "document": {...},            # insertOne
        "filter": {...},              # find / findOne / updateOne / deleteOne
        "update": {...},              # updateOne
        "sort": {"field": 1|-1},      # find
        "limit": int,                 # find
        "skip": int or "RANDOM_PLACEHOLDER",
        "projection": {...},          # find / findOne
        "upsert": true|false          # updateOne
      }
    返回: (标准化结果dict, 耗时, 错误)
    """
    try:
        from pymongo import MongoClient
    except ImportError:
        return None, 0, "pymongo not installed"

    if not isinstance(op_obj, dict):
        return None, 0, "mongo json op must be dict"

    op_name = op_obj.get("op")
    collection = op_obj.get("collection")
    if not op_name or not collection:
        return None, 0, "missing required fields: op / collection"

    allowed_ops = {
        "insertOne",
        "updateOne",
        "find",
        "findOne",
        "deleteOne",
        "createCollection",
    }
    if op_name not in allowed_ops:
        return None, 0, f"unsupported op: {op_name}"

    host = conn_args.get("host", "127.0.0.1")
    port = int(conn_args.get("port", 27017))
    username = conn_args.get("username") or None
    password = conn_args.get("password") or None
    dbname = conn_args["dbname"]
    if username and password:
        uri = f"mongodb://{username}:{password}@{host}:{port}/"
    else:
        uri = f"mongodb://{host}:{port}/"

    start = time.time()
    try:
        from pymongo.errors import CollectionInvalid

        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        db = client[dbname]

        if op_name == "createCollection":
            try:
                db.create_collection(collection)
                out = {"type": "createCollection", "value": {"created": collection}}
            except CollectionInvalid:
                out = {
                    "type": "createCollection",
                    "value": {"created": False, "reason": "already exists"},
                }
            return out, time.time() - start, None

        coll_ref = db[collection]

        if op_name == "insertOne":
            doc = op_obj.get("document")
            if not isinstance(doc, dict):
                return None, 0, "insertOne requires 'document' dict"
            res = coll_ref.insert_one(doc)
            out = {"type": "insertOne", "value": {"inserted_id": str(res.inserted_id)}}

        elif op_name == "updateOne":
            flt = op_obj.get("filter") or {}
            upd = op_obj.get("update")
            if not isinstance(upd, dict):
                return None, 0, "updateOne requires 'update' dict"
            upsert = bool(op_obj.get("upsert", False))
            res = coll_ref.update_one(flt, upd, upsert=upsert)
            out = {
                "type": "updateOne",
                "value": {
                    "matched": res.matched_count,
                    "modified": res.modified_count,
                    "upserted_id": str(res.upserted_id) if res.upserted_id else None,
                },
            }

        elif op_name == "find":
            flt = op_obj.get("filter") or {}
            proj = op_obj.get("projection")
            cur = coll_ref.find(flt, proj)
            sort_spec = op_obj.get("sort")
            if isinstance(sort_spec, dict):
                for k, v in sort_spec.items():
                    try:
                        cur = cur.sort(k, int(v))
                    except Exception:
                        return None, 0, f"invalid sort value for {k}: {v}"
            skip_v = op_obj.get("skip")
            if isinstance(skip_v, int):
                cur = cur.skip(skip_v)
            # RANDOM_PLACEHOLDER 由上层后处理，这里忽略
            limit_v = op_obj.get("limit")
            if isinstance(limit_v, int):
                cur = cur.limit(limit_v)
            docs = []
            for d in cur:
                d["_id"] = str(d["_id"])
                docs.append(d)
            out = {"type": "find", "value": docs}

        elif op_name == "findOne":
            flt = op_obj.get("filter") or {}
            proj = op_obj.get("projection")
            d = coll_ref.find_one(flt, proj)
            if d:
                d["_id"] = str(d["_id"])
            out = {"type": "findOne", "value": d}

        elif op_name == "deleteOne":
            flt = op_obj.get("filter") or {}
            res = coll_ref.delete_one(flt)
            out = {"type": "deleteOne", "value": {"deleted_count": res.deleted_count}}

        else:
            return None, 0, f"unsupported op: {op_name}"

        # 最终统一清洗 (深度递归)
        return make_json_safe(out), time.time() - start, None
    except Exception as e:
        return None, 0, str(e)


def exec_mongodb_command(conn_args, tool, exp, mongo_command):
    """执行 MongoDB Shell 风格命令，返回 (标准化结果, 耗时, 错误)。

    支持基本形式：
      db.<collection>.insertOne({...});
      db.<collection>.find({...});
      db.<collection>.deleteOne({...});
      db.<collection>.updateOne({filter},{update});

    解析容错：
      - 允许 { key: 'v'} 形式，自动补引号 / 单引号替换。
      - 若 collection == collectionName (占位符) 则提示错误。
      - 不支持聚合 / 复杂链式（可后续扩展）。
    """
    try:
        from pymongo import MongoClient
    except ImportError:
        return None, 0, "pymongo not installed"

    if not mongo_command or not mongo_command.strip():
        return {"type": "empty", "value": None}, 0, None

    cmd = mongo_command.strip().rstrip(";")
    start = time.time()
    if not cmd.startswith("db."):
        return None, 0, f"unsupported mongodb command form: {cmd}"

    # 解析 db.<coll>.<op>(...)
    body = cmd[3:]
    if "." not in body:
        return None, 0, f"malformed mongodb command: {cmd}"
    coll, rest = body.split(".", 1)
    collection = coll.strip()
    if collection.lower() == "collectionname":
        return None, 0, "placeholder collectionName not replaced"
    if "(" not in rest:
        return None, 0, f"malformed operation segment: {rest}"
    op_name = rest.split("(", 1)[0].strip()
    args_part = rest[len(op_name) :].strip()
    if not args_part.startswith("(") or not args_part.endswith(")"):
        return None, 0, f"malformed arguments: {args_part}"
    inner = args_part[1:-1].strip()  # 去掉括号

    # 拆分两个 JSON（只针对 updateOne(filter,update)）
    filter_doc = update_doc = None
    try:
        if op_name == "updateOne":
            # 简单括号层次拆分，假设不嵌套逗号。可后续改为计数法。
            depth = 0
            split_idx = -1
            for i, ch in enumerate(inner):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                elif ch == "," and depth == 0:
                    split_idx = i
                    break
            if split_idx == -1:
                return None, 0, "updateOne requires two JSON arguments"
            filter_raw = inner[:split_idx].strip()
            update_raw = inner[split_idx + 1 :].strip()
            filter_doc = _parse_mongo_json_like(filter_raw)
            update_doc = _parse_mongo_json_like(update_raw)
        elif op_name in {"insertOne", "find", "deleteOne"}:
            arg_raw = inner.strip()
            if arg_raw == "" and op_name == "find":
                filter_doc = {}
            else:
                filter_doc = _parse_mongo_json_like(arg_raw)
        else:
            return None, 0, f"unsupported operation: {op_name}"
    except ValueError as ve:
        return None, 0, f"json parse error: {ve}"

    # 连接
    host = conn_args.get("host", "127.0.0.1")
    port = int(conn_args.get("port", 27017))
    username = conn_args.get("username") or None
    password = conn_args.get("password") or None
    dbname = conn_args["dbname"]
    if username and password:
        uri = f"mongodb://{username}:{password}@{host}:{port}/"
    else:
        uri = f"mongodb://{host}:{port}/"
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        db = client[dbname]
        coll_ref = db[collection]
        if op_name == "insertOne":
            res = coll_ref.insert_one(filter_doc)
            out = {"type": "insertOne", "value": {"inserted_id": str(res.inserted_id)}}
        elif op_name == "find":
            docs = []
            for d in coll_ref.find(filter_doc):
                d["_id"] = str(d["_id"])
                docs.append(d)
            out = {"type": "find", "value": docs}
        elif op_name == "deleteOne":
            res = coll_ref.delete_one(filter_doc)
            out = {"type": "deleteOne", "value": {"deleted_count": res.deleted_count}}
        elif op_name == "updateOne":
            res = coll_ref.update_one(filter_doc, update_doc)
            out = {
                "type": "updateOne",
                "value": {"matched": res.matched_count, "modified": res.modified_count},
            }
        else:
            return None, 0, f"unsupported operation: {op_name}"
        return make_json_safe(out), time.time() - start, None
    except Exception as e:
        return None, 0, str(e)


def _parse_mongo_json_like(src: str):
    """宽松解析 形如 { a: 'b', c: 1 } 的 JSON-like 字符串 -> Python dict。
    步骤：
      1. 去掉首尾空白
      2. 单引号替换为双引号
      3. 给未加引号的 key 补双引号（正则）
      4. json.loads
    失败抛 ValueError
    """
    import json as _json
    import re as _re

    s = src.strip()
    if not s:
        return {}
    # 容许直接 {}
    # 简单保护：如果不是以 { 开头以 } 结尾，则视为语法错误
    if not (s.startswith("{") and s.endswith("}")):
        raise ValueError(f"not an object literal: {s}")
    s = s.replace("'", '"')
    # 引号补全：在 { 或 , 后跟可能的 key (非引号开头) 到 冒号 前加引号
    s = _re.sub(r"([,{]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)", '\1"\2"\3', s)
    try:
        return _json.loads(s)
    except Exception as e:
        raise ValueError(str(e))


def run_with_timeout(func, timeout, *args, **kwargs):
    result = [None, None, None]  # 使用列表来存储返回值，因为列表是可变的

    def thread_func():
        result[0], result[1], result[2] = func(*args, **kwargs)

    thread = threading.Thread(target=thread_func)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        # 若线程未完成则中断并抛出超时异常
        thread.join()  # 等待线程结束
        raise TimeoutError("Function call timed out.")

    return result[0], result[1], result[2]  # 返回函数的执行结果


def database_define_pinolo(tool, exp, dbType):
    # 创建连接池实例
    args = get_database_connector_args(dbType.lower())
    args["dbname"] = f"{tool}_{exp}_{dbType}"
    pool = DatabaseConnectionPool(
        args["dbType"],
        args["host"],
        args["port"],
        args["username"],
        args["password"],
        args["dbname"],
    )
    with open(
        os.path.join(current_dir, tool.lower(), exp.lower(), dbType.lower() + ".json"),
        "r",
        encoding="utf-8",
    ) as rf:
        ddls = json.load(rf)
        for ddl in ddls:
            pool.execSQL(ddl)
    pool.close()


def get_database_connector_args(dbType):
    with open(
        os.path.join(current_dir, "database_connector_args.json"), "r", encoding="utf-8"
    ) as r:
        database_connection_args = json.load(r)
    if dbType.lower() in database_connection_args:
        return database_connection_args[dbType.lower()]


def database_connect_test():
    # 1.PINOLO
    # database_define_pinolo('pinolo', 'exp1','mysql')
    # database_define_pinolo('pinolo', 'exp1','mariadb')
    # database_define_pinolo('pinolo', 'exp1', 'tidb')
    # database_define_pinolo('pinolo', 'exp1','sqlite')
    # database_define_pinolo('pinolo', 'exp1','postgres')
    # database_define_pinolo('pinolo', 'exp1',"duckdb")
    # database_define_pinolo('pinolo', 'exp1',"monetdb")
    # database_define_pinolo('pinolo', 'exp1',"clickhouse")

    # 1.PINOLO
    # mysql
    sql_statement = "SELECT (~MONTHNAME(_UTF8MB4'2011-04-18')) AS `f1`,(`f4`) AS `f2`,(CEILING(6)) AS `f3` FROM (SELECT `col_char(20)_key_signed` AS `f4`,`col_bigint_undef_signed` AS `f5`,`col_double_undef_unsigned` AS `f6` FROM `table_3_utf8_undef`) AS `t1`"
    # print(exec_sql_statement('pinolo', 'exp1','mysql', sql_statement))  #TEST OK

    # Mariadb
    sql_statement = "SELECT json_array_intersect(@json1, @json2);"
    # print(exec_sql_statement('pinolo', 'exp1','mariadb', sql_statement))  # TEST OK
    sql_statement = "SELECT 1;"
    # print(exec_sql_statement('pinolo', 'exp1','mariadb', sql_statement))  # TEST OK

    # tidb
    # print(exec_sql_statement("pinolo", 'exp1','tidb', sql_statement))  # TEST OK

    # SQLite
    sqlite_sql = "SELECT * FROM table_3_utf8_undef;"
    # print(exec_sql_statement("pinolo", 'exp1','sqlite', sqlite_sql))  # TEST OK

    # postgres
    postgres_sql = "SELECT (f4) AS f1, (~CAST(CAST(PI() AS numeric) AS int)) AS f2, (-EXTRACT(DOY FROM DATE '2004-05-01')) AS f3 FROM (SELECT col_bigint_key_unsigned AS f4, col_char_20_undef_signed AS f5, col_float_key_signed AS f6 FROM table_3_utf8_undef) AS t1"
    # print(exec_sql_statement("pinolo", 'exp1','postgres', postgres_sql))  # TEST OK

    # duckdb
    duckdb_sql = "SELECT * FROM table_3_utf8_undef;"
    # print(exec_sql_statement("pinolo",'exp1', 'duckdb', duckdb_sql))  # TEST OK

    # monetdb
    monetdb_sql = "SELECT * FROM table_3_utf8_undef;"
    # print(exec_sql_statement("pinolo",'exp1', 'monetdb', monetdb_sql))  # TEST OK

    # clickhouse
    clickhouse_sql = "SELECT * FROM table_3_utf8_undef;"
    # print(exec_sql_statement("pinolo",'exp1', 'clickhouse', clickhouse_sql))  # TEST OK

    # 1.sqlancer
    # mysql
    sqls = [
        "CREATE TABLE t0(c0 INT UNIQUE, c1 INT, c2 INT, c3 INT UNIQUE) ENGINE = MyISAM;",
        'INSERT INTO t0(c0) VALUES(DEFAULT), ("a");',
        'INSERT IGNORE INTO t0(c3) VALUES("a"), (1);',
        'REPLACE INTO t0(c1, c0, c3) VALUES(1, 2, 3), (1, "a", "a");',
        "SELECT (NULL) IN (SELECT t0.c3 FROM t0 WHERE t0.c0);",
    ]
    """
    for sql in sqls:
        print(sqls.index(sql))
        print(exec_sql_statement("sqlancer",'exp1', 'mysql', sql))  #TEST OK
    print(database_clear_sqlancer("sqlancer",'exp1', 'mysql'))
    print(exec_sql_statement("sqlancer", 'exp1', 'mysql', "SHOW TABLES;"))
    """

    # Mariadb
    sqls = [
        "CREATE TABLE t0(c0 INT);",
        "INSERT INTO t0 VALUES (1);",
        "CREATE INDEX i0 ON t0(c0);",
        "SELECT * FROM t0 WHERE 0.5 = c0; -- unexpected: row is fetched",
    ]
    """
    for sql in sqls:
        print(sqls.index(sql))
        print(exec_sql_statement("sqlancer", 'exp1','mariadb', sql))  # TEST OK
    database_clear_sqlancer("sqlancer",'exp1', 'mariadb')
    print(exec_sql_statement("sqlancer", 'exp1', 'mariadb', "SHOW TABLES;"))
    """

    # tidb
    sqls = [
        "CREATE TABLE t0(c0 INT, c1 TEXT AS (0.9));",
        "INSERT INTO t0(c0) VALUES (0);",
        "SELECT 0 FROM t0 WHERE false UNION SELECT 0 FROM t0 WHERE NOT t0.c1; -- expected: {0}, actual: {}",
    ]
    """
    for sql in sqls:
        print(sqls.index(sql))
        print(exec_sql_statement("sqlancer",'exp1','tidb', sql))  #TEST OK
    database_clear_sqlancer("sqlancer", 'exp1','tidb')
    print(exec_sql_statement("sqlancer", 'exp1', 'tidb', "SHOW TABLES;"))
    """

    # SQLite
    sqls = [
        "CREATE TABLE t0(c0 INT UNIQUE);",
        "INSERT INTO t0(c0) VALUES (1);",
        "SELECT * FROM t0 WHERE '1' IN (t0.c0); -- unexpected: fetches row",
    ]
    """
    for sql in sqls:
        print(sqls.index(sql))
        print(exec_sql_statement("sqlancer",'exp1','sqlite', sql))  #TEST OK
    database_clear_sqlancer("sqlancer", 'exp1','sqlite')
    """

    # postgres:sqlancer中无支持的postgres的tlp和norec bug
    sqls = ["CREATE TABLE t0(c0 INT);", "INSERT INTO t0(c0) VALUES(0), (0);"]
    """
    for sql in sqls:
        print(sqls.index(sql))
        print(exec_sql_statement("sqlancer",'exp1','postgres', sql))  #TEST OK
    database_clear_sqlancer("sqlancer", 'exp1','postgres')
    """

    # duckdb:同sqlite
    sqls = [
        "CREATE TABLE t0(c0 INT);",
        "INSERT INTO t0(c0) VALUES (0);",
        "SELECT * FROM t0 WHERE NOT(NULL OR TRUE); -- expected: {}, actual: {1}",
    ]
    """
    for sql in sqls:
        print(sqls.index(sql))
        print(exec_sql_statement("sqlancer",'exp1','duckdb', sql))  #TEST OK
    database_clear_sqlancer("sqlancer", 'exp1','duckdb')
    """

    # monetdb
    sqls = [
        "CREATE TABLE t0(c0 INT);",
        "INSERT INTO t0(c0) VALUES (0);",
        "SELECT * FROM t0;",
    ]
    """
    for sql in sqls:
        print(sqls.index(sql))
        print(sql)
        print(exec_sql_statement("sqlancer",'exp1','monetdb', sql))  #TEST OK
    database_clear_sqlancer("sqlancer", 'exp1','monetdb')
    """

    # clickhouse
    sqls = [
        "CREATE TABLE t0 (c0 Int32) ENGINE = MergeTree() ORDER BY c0;",
        "INSERT INTO t0 VALUES (1);",
        "SELECT * FROM t0 WHERE c0 = 1;",
    ]
    for sql in sqls:
        print(sqls.index(sql))
        print(exec_sql_statement("sqlancer", "exp1", "clickhouse", sql))  # TEST OK
    print(database_clear("sqlancer", "exp1", "clickhouse"))


exec_sql_statement("pinolo", "exp1", "clickhouse", "SELECT 1;")
