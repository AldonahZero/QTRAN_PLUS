"""NoSQL Crash/Hang Detection Pipeline

目的:
  与 SQL 语义 Oracle (逻辑一致性) 流水线解耦, 专门用于对 NoSQL(当前: redis/memcached/etcd/consul/mongodb) 命令序列做健壮性检测:
    - crash: 进程异常退出/无法建立连接
    - hang: 命令执行超时 (超过设定阈值) / 多次健康检查失败

设计原则:
  1. 只关注稳定性, 不做语义等价比较, 不生成逻辑 bug 结论。
  2. 输入可以是: 行分隔命令文件 / JSONL (每行一个 {"commands": [...]} 对象)。
  3. 每条命令独立超时控制, 整个序列有整体超时 (可选)。
  4. 记录统一事件日志: 每条命令 -> {cmd, start_ts, duration, error, classification}。
  5. 发现 crash/hang 立即记录快照(前 N 条成功命令 + 当前命令)。

输出:
  返回结构体 dict:
  {
    "dbType": "redis",
    "target": "127.0.0.1:6379",
    "sequence_id": <hash or filename>,
    "crash": true/false,
    "hang": true/false,
    "events": [...],
    "summary": {"ok": n_ok, "errors": n_err, "timeouts": n_to},
    "first_failure": { ... event ... } or None
  }

后续可扩展:
  - 添加资源占用监控 (RSS/FD) 用于内存泄漏/句柄泄漏迹象。
  - 进程重启策略 / 自动最小化 (delta debug)。
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Iterable
import time, json, socket, subprocess, base64, os

from src.Tools.DatabaseConnect.database_connector import exec_sql_statement, get_database_connector_args

DEFAULT_CMD_TIMEOUT = 3.0  # 单条命令执行超时秒
DEFAULT_HEALTH_CHECK_INTERVAL = 0.5
DEFAULT_HEALTH_RETRY = 3

SUPPORTED_NOSQL = {"redis", "memcached", "etcd", "consul", "mongodb"}

@dataclass
class Event:
    index: int
    cmd: str
    start_ts: float
    duration: float
    error: Optional[str]
    classification: str  # ok|timeout|error|crash
    raw_result: Optional[Any] = None

    def to_dict(self):
        d = asdict(self)
        # 结果可能很大, 适当截断
        if isinstance(d.get("raw_result"), str) and len(d["raw_result"]) > 200:
            d["raw_result"] = d["raw_result"][:200] + "...<truncated>"
        return d


def _health_check(dbType: str) -> bool:
    db = dbType.lower()
    try:
        args = get_database_connector_args(db)
        if db == "redis":
            import redis  # type: ignore
            r = redis.Redis(host=args.get("host","127.0.0.1"), port=int(args.get("port",6379)), socket_timeout=1)
            return r.ping() is True
        if db == "memcached":
            with socket.create_connection((args.get("host","127.0.0.1"), int(args.get("port",11211))), timeout=1) as s:
                s.sendall(b"version\r\n")
                resp = s.recv(64)
                return b"VERSION" in resp
        if db == "etcd":
            # 简单探活: 查看 docker exec etcdctl endpoint status
            container = args.get("container_name","etcd_QTRAN")
            proc = subprocess.run(["docker","exec",container,"etcdctl","endpoint","status"], capture_output=True, text=True, timeout=2)
            return proc.returncode == 0
        if db == "consul":
            import requests
            host = args.get("host","127.0.0.1")
            port = int(args.get("port",8500))
            r = requests.get(f"http://{host}:{port}/v1/status/leader", timeout=1)
            return r.status_code == 200
        if db == "mongodb":
            from pymongo import MongoClient
            host = args.get("host","127.0.0.1")
            port = int(args.get("port",27017))
            client = MongoClient(host, port, serverSelectionTimeoutMS=800)
            client.admin.command("ping")
            return True
    except Exception:
        return False
    return False


def _wait_healthy(dbType: str, retries: int = DEFAULT_HEALTH_RETRY, interval: float = DEFAULT_HEALTH_CHECK_INTERVAL) -> bool:
    for _ in range(retries):
        if _health_check(dbType):
            return True
        time.sleep(interval)
    return False


def run_nosql_sequence(dbType: str, commands: Iterable[str], sequence_id: Optional[str] = None, cmd_timeout: float = DEFAULT_CMD_TIMEOUT) -> Dict[str, Any]:
    db = dbType.lower()
    if db not in SUPPORTED_NOSQL:
        raise ValueError(f"Unsupported NoSQL dbType: {dbType}")
    args = get_database_connector_args(db)
    target = f"{args.get('host','127.0.0.1')}:{args.get('port')}"

    events: List[Event] = []
    crash = False
    hang = False
    first_failure: Optional[Event] = None

    if not _wait_healthy(db):
        return {
            "dbType": db,
            "target": target,
            "sequence_id": sequence_id,
            "crash": True,
            "hang": False,
            "events": [],
            "summary": {"ok": 0, "errors": 0, "timeouts": 0},
            "first_failure": None,
            "note": "service not healthy before start",
        }

    for idx, raw_cmd in enumerate(commands):
        cmd = (raw_cmd or "").strip()
        if not cmd:
            continue
        start_ts = time.time()
        timeout_flag = False
        error_msg: Optional[str] = None
        classification = "ok"
        exec_result = None
        try:
            # 单条命令超时控制: 简单轮询式, 因 exec_sql_statement 内部自身包含网络超时
            exec_result, duration, err = exec_sql_statement("fuzz", "seq", dbType, cmd)
            if err:
                error_msg = err
                classification = "error"
        except Exception as e:  # 捕获潜在崩溃迹象 (连接拒绝等)
            duration = time.time() - start_ts
            error_msg = str(e)
            classification = "crash" if not _health_check(db) else "error"
            if classification == "crash":
                crash = True
        else:
            duration = duration if 'duration' in locals() else (time.time() - start_ts)
        if duration >= cmd_timeout and classification == "ok":
            classification = "timeout"
            error_msg = error_msg or f"command exceeded {cmd_timeout}s"
            hang = True
        ev = Event(
            index=idx,
            cmd=cmd,
            start_ts=start_ts,
            duration=duration,
            error=error_msg,
            classification=classification,
            raw_result=str(exec_result) if exec_result is not None else None,
        )
        events.append(ev)
        if classification in {"timeout", "crash"} and not first_failure:
            first_failure = ev
        if crash:  # 确认崩溃后可提前结束
            break

    summary = {
        "ok": sum(1 for e in events if e.classification == "ok"),
        "errors": sum(1 for e in events if e.classification == "error"),
        "timeouts": sum(1 for e in events if e.classification == "timeout"),
    }
    return {
        "dbType": db,
        "target": target,
        "sequence_id": sequence_id,
        "crash": crash,
        "hang": hang,
        "events": [e.to_dict() for e in events],
        "summary": summary,
        "first_failure": first_failure.to_dict() if first_failure else None,
    }


def run_nosql_file(dbType: str, path: str) -> Dict[str, Any]:
    sequence_id = os.path.basename(path)
    # 支持两种格式: 纯文本多行 / JSONL (每行 {"commands": [...]})
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f]
    commands: List[str] = []
    if all(l.strip().startswith("{") for l in lines):
        # JSONL 模式
        for l in lines:
            try:
                obj = json.loads(l)
                if isinstance(obj, dict) and isinstance(obj.get("commands"), list):
                    commands.extend([str(c) for c in obj["commands"]])
            except Exception:
                pass
    else:
        commands = [l for l in lines if l.strip()]
    return run_nosql_sequence(dbType, commands, sequence_id=sequence_id)


if __name__ == "__main__":
    import argparse, pprint
    p = argparse.ArgumentParser(description="Run NoSQL crash/hang detection pipeline")
    p.add_argument("--db", required=True, help="redis|memcached|etcd|consul|mongodb")
    p.add_argument("--file", required=True, help="command file path")
    p.add_argument("--timeout", type=float, default=DEFAULT_CMD_TIMEOUT)
    args = p.parse_args()
    res = run_nosql_file(args.db, args.file)
    pprint.pp(res)
