"""JSON 安全转换工具

提供 make_json_safe(obj) 递归函数, 将可能无法被 json 序列化的对象转换为可序列化的基础类型:

规则:
1. ObjectId -> str(ObjectId)
2. datetime/date/time -> ISO8601 字符串
3. bytes/bytearray -> utf-8 解码(失败则 base64)
4. Decimal -> float (若为 NaN/Infinity 则转为字符串)
5. set/tuple -> list
6. Enum -> enum.value
7. 其它自定义对象 -> str(obj)
8. dict / list 递归处理

保持对基本类型(int/float/bool/None/str) 原样返回.
"""

from __future__ import annotations

from typing import Any


def make_json_safe(obj: Any) -> Any:
    """递归清洗对象, 确保可被 json 序列化.

    参数:
        obj: 任意 Python 对象
    返回:
        可直接 json.dumps 的对象 (只包含 dict/list/str/int/float/bool/None)
    """
    # 局部导入, 避免在未安装相关包时崩溃
    # ObjectId
    try:
        from bson import ObjectId  # type: ignore
    except Exception:  # pragma: no cover

        class ObjectId:  # type: ignore
            pass

    # Decimal
    try:
        from decimal import Decimal
    except Exception:  # pragma: no cover
        Decimal = ()  # type: ignore

    # Enum
    try:
        from enum import Enum
    except Exception:  # pragma: no cover

        class Enum:  # type: ignore
            pass

    # 时间类型
    try:
        import datetime as _dt
    except Exception:  # pragma: no cover
        _dt = None  # type: ignore

    # 基础可直接返回
    if obj is None or isinstance(obj, (str, int, float, bool)):
        # float 的 NaN/Inf 在 json 中非法, 转为字符串
        if isinstance(obj, float):
            if obj != obj:  # NaN
                return "NaN"
            if obj == float("inf"):
                return "Infinity"
            if obj == float("-inf"):
                return "-Infinity"
        return obj

    # ObjectId
    if isinstance(obj, ObjectId):  # type: ignore
        return str(obj)

    # Decimal
    if "Decimal" in globals() and isinstance(obj, Decimal):  # type: ignore
        try:
            f = float(obj)  # type: ignore
            if f != f:
                return "NaN"
            if f == float("inf"):
                return "Infinity"
            if f == float("-inf"):
                return "-Infinity"
            return f
        except Exception:
            return str(obj)

    # Enum
    if isinstance(obj, Enum):  # type: ignore
        return make_json_safe(obj.value)  # type: ignore

    # datetime / date / time
    if _dt and isinstance(obj, (_dt.datetime, _dt.date, _dt.time)):
        try:
            # 为 datetime 补充 timezone 信息 (若无 tzinfo 当作 naive)
            if isinstance(obj, _dt.datetime) and obj.tzinfo is None:
                return obj.isoformat() + "Z"
            return obj.isoformat()
        except Exception:
            return str(obj)

    # bytes / bytearray
    if isinstance(obj, (bytes, bytearray)):
        try:
            return obj.decode("utf-8")  # type: ignore
        except Exception:
            import base64

            return base64.b64encode(obj).decode("ascii")  # type: ignore

    # set / tuple -> list
    if isinstance(obj, (set, tuple)):
        return [make_json_safe(x) for x in obj]

    # list
    if isinstance(obj, list):
        return [make_json_safe(x) for x in obj]

    # dict
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            # key 需要是字符串
            if isinstance(k, (str, int, float, bool)):
                key = str(k)
            else:
                key = repr(k)
            new_dict[key] = make_json_safe(v)
        return new_dict

    # 兜底: 任意对象 -> str
    try:
        return str(obj)
    except Exception:
        return f"<unserializable {type(obj).__name__}>"


__all__ = ["make_json_safe"]


def safe_parse_result(s: Any) -> Any:
    """
    尝试安全地将可能来自不同来源的结果解析为 Python 对象（优先 JSON）。

    解析策略：
    1) 若已是非字符串对象则直接返回
    2) 尝试 json.loads
    3) 尝试 repair_json 后 json.loads
    4) 简单清洗（ObjectId(...) -> 字符串; 为无引号键加引号）后 json.loads
    5) ast.literal_eval 作为最后回退

    解析失败时会抛出异常以便上层记录
    """
    import json
    import re
    import ast
    from json_repair import repair_json

    if s is None:
        return None
    if not isinstance(s, str):
        return s

    txt = s.strip()

    # 1) 优先 JSON
    try:
        return json.loads(txt)
    except Exception:
        pass

    # 2) repair_json
    try:
        repaired = repair_json(txt)
        return json.loads(repaired)
    except Exception:
        pass

    # 3) 简单清洗
    try:
        cleaned = re.sub(r"ObjectId\(['\"]?([0-9a-fA-F]+)['\"]?\)", r'"\1"', txt)
        cleaned = re.sub(
            r"(?P<pre>[{,]\s*)(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:",
            r'\g<pre>"\g<key>":',
            cleaned,
        )
        return json.loads(cleaned)
    except Exception:
        pass

    # 4) ast.literal_eval 回退
    try:
        return ast.literal_eval(txt)
    except Exception:
        raise


__all__.append("safe_parse_result")
