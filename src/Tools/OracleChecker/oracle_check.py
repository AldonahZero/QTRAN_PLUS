"""
预言机检查：比较两次查询结果集关系，判断是否满足 metamorphic 关系

作用概述：
- 定义 Result 结构及其比较逻辑（相等、子集、超集、部分不匹配等）。
- 提供 Check(origin, mutated, isUpper, isSame) 以表达预言机关系判断。
- 提供 execSQL_result_convertor 将执行结果转为标准 Result 输入。
"""

from typing import Tuple, Sequence
from sqlalchemy.engine.row import Row
from typing import List, Tuple, Optional, Union, Sequence
from time import time
import pymysql
from sqlalchemy import create_engine, text


class Result:
    def __init__(
        self,
        column_names: List[str],
        column_types: List[str],
        rows: List[List[str]],
        err: Optional[Exception] = None,
    ):
        self.column_names = column_names
        self.column_types = column_types
        self.rows = rows
        self.err = err

    def to_string(self) -> str:
        result_str = "ColumnName(ColumnType)s: "
        result_str += " ".join(
            [
                f"{name}({type_})"
                for name, type_ in zip(self.column_names, self.column_types)
            ]
        )
        result_str += "\n"
        for i, row in enumerate(self.rows):
            result_str += f"row {i}: {' '.join(row)}\n"
        if self.err:
            result_str += f"Error: {self.err}\n"
        return result_str

    def flat_rows(self) -> List[str]:
        return [",".join(row) for row in self.rows]

    def is_empty(self) -> bool:
        return len(self.column_names) == 0

    def get_error_code(self) -> Tuple[int, Optional[Exception]]:
        if not self.err:
            return -1, Exception("[Result.GetErrorCode]result.err == None")
        else:
            return -1, Exception(
                f"[Result.GetErrorCode]not mysql.connector.Error {type(self.err).__name__}"
            )

    def cmp(self, another: "Result") -> Tuple[int, Optional[Exception]]:
        if self.err:
            return -2, Exception("[Result.CMP]self error")
        if another.err:
            return -2, Exception("[Result.CMP]another error")
        # 判断两个结果集是否为空
        empty1 = self.is_empty()
        empty2 = another.is_empty()

        # 若两个结果集其中一个为空
        if empty1 or empty2:
            # 都为空则说明两个结果集相等
            if empty1 and empty2:
                return 0, None
            return (-1, None) if empty1 else (1, None)

        if len(self.column_names) != len(another.column_names):
            return 2, None

        res1 = self.flat_rows()
        res2 = another.flat_rows()

        mp = {}
        # 遍历res2，如果元素r已在字典中，就将其频次加1；否则将其初始频次设置为1。
        for r in res2:
            mp[r] = mp.get(r, 0) + 1

        all_in_another = True
        # 检查res1中的元素是否存在于res2中
        for r in res1:
            if r in mp:
                # 若它的频次只有1，则从字典中删除该元素；若频次大于1，则将频次减1。
                if mp[r] <= 1:
                    del mp[r]
                else:
                    mp[r] -= 1
            else:
                # 将all_in_another置为False，表示res1存在元素不在res2中。
                all_in_another = False

        # 如果res1所有的元素都在res2中（all_in_another == True）：
        # mp为空（res2中的所有元素都已匹配完成）：返回(0, None)，表示两个列表完全相等。
        # 若非mp空：返回(-1, None)，表示res1是res2的子集，但res2还有多余元素。

        # 如果res1某些元素不在res2中（all_in_another == False）：
        # mp为空：返回(1, None)，表示res1有多余元素，但res2正好用尽。表示res2是res1的子集，但res1还有多余元素。
        # 若非mp空：返回(2, None)，表示res1和res2都有不匹配的地方。
        if all_in_another:
            if not mp:
                return 0, None
            return -1, None
        else:
            if not mp:
                return 1, None
            return 2, None


def Check(
    originResult: Result, mutatedResult: Result, isUpper: bool, isSame: bool
) -> Tuple[bool, str]:
    """
    预言机判断：
    - isSame=True：要求完全相等；
    - isSame=False：允许包含关系，若 isUpper=True 则 mutated 是 origin 的超集，反之是子集。
    返回 (是否满足, 错误或 None)。
    """
    cmp, err = originResult.cmp(mutatedResult)
    if err:
        return False, err
    # 相等，则满足oracle
    if isSame:
        if cmp == 0:
            return True, None
        else:
            return False, None
    else:
        if cmp == 0:
            return True, None
        if (isUpper and cmp == -1) or (not isUpper and cmp == 1):
            return True, None
        return False, None


def convert_to_result(data: Sequence[Row]) -> Result:
    """将 SQLAlchemy Row 列表转换为 Result 结构。空结果返回空列与空行。"""
    if not data:
        return Result(column_names=[], column_types=[], rows=[], err=None)

    first_row = data[0]
    column_names = list(first_row.keys())

    # 假设所有列的数据类型为字符串
    column_types = ["str" for _ in column_names]

    # 将数据行转换为字符串的列表
    rows = [[str(row[key]) for key in column_names] for row in data]
    return Result(column_names=column_names, column_types=column_types, rows=rows)


# 示例用法
def usage_example():
    column_names = ["ID", "Name", "Age"]
    column_types = ["int", "string", "int"]

    rows = [["1", "Alice", "30"], ["2", "Bob", "25"], ["3", "Charlie", "35"]]

    another_rows = [["2", "Bob", "25"], ["3", "Charlie", "35"]]

    # 创建 Result 对象
    result = Result(column_names, column_types, rows)
    another_result = Result(column_names, column_types, another_rows)
    is_upper = True
    end, error = Check(
        result, another_result, is_upper
    )  # check result->another_result是否符合is_upper
    # Check result: False,check "result->another_result"是否为upper，显然不是故返回false
    if error:
        print(f"Error occurred: {error}")
    else:
        print(f"Check result: {end}")


# 将得到的list结构的sql执行结果，转换格式
def execSQL_result_convertor(exec_result):
    """
    标准格式如下：
            column_names = ["c1", "c2", "c3"]
            column_types = ["int", "string", "int"]
            rows = [
                ["1", "Alice", "30"],
                ["2", "Bob", "25"],
                ["3", "Charlie", "35"]
            ]
    :return:
    """
    converted_result = {"column_names": [], "column_types": [], "rows": []}

    # 1) None -> 空结果
    if exec_result is None:
        return converted_result

    # 2) 支持我们统一的 NoSQL KV 结果结构(dict)，例如：
    #    {"type":"kv_get","success":True,"value":"hello","meta":{...}}
    #    转换策略：
    #      - 如果 value 是 list => 每个元素一行，单列 value
    #      - 如果 value 是 dict => 展平为两列 key/value
    #      - 其它标量 => 单行单列 value
    if (
        isinstance(exec_result, dict)
        and "type" in exec_result
        and "value" in exec_result
    ):
        val = exec_result.get("value")
        # 列名定义
        if isinstance(val, list):
            converted_result["column_names"] = ["value"]
            converted_result["column_types"] = ["str"]
            for v in val:
                converted_result["rows"].append([str(v)])
        elif isinstance(val, dict):
            # 统一为 key,value 两列
            converted_result["column_names"] = ["key", "value"]
            converted_result["column_types"] = ["str", "str"]
            for k, v in val.items():
                converted_result["rows"].append([str(k), str(v)])
        else:  # 标量 / None
            converted_result["column_names"] = ["value"]
            converted_result["column_types"] = ["str"]
            if val is not None:
                converted_result["rows"].append([str(val)])
        return converted_result

    # 3) 原始关系型结果：期望 list-like 且内部元素可索引（行序列）
    if isinstance(exec_result, (list, tuple)) and exec_result:
        # 行可能是 tuple/list；如果首行不是序列（例如单标量），统一包一层
        first_row = exec_result[0]
        if not isinstance(first_row, (list, tuple)):
            # 单列场景，全部当作一列'value'
            converted_result["column_names"] = ["c0"]
            converted_result["column_types"] = [type(first_row).__name__]
            for r in exec_result:
                converted_result["rows"].append([str(r)])
            return converted_result
        # 正常二维
        col_count = len(first_row)
        for i in range(col_count):
            converted_result["column_names"].append("c" + str(i))
            converted_result["column_types"].append(type(first_row[i]).__name__)
        for row in exec_result:
            try:
                converted_result["rows"].append([str(row[i]) for i in range(col_count)])
            except Exception:
                # 行长度异常，补齐/截断
                safe = []
                for i in range(col_count):
                    try:
                        safe.append(str(row[i]))
                    except Exception:
                        safe.append("<ERR>")
                converted_result["rows"].append(safe)
        return converted_result

    # 4) 其它无法识别的类型，退化为单值表
    converted_result["column_names"] = ["value"]
    converted_result["column_types"] = [type(exec_result).__name__]
    converted_result["rows"].append([str(exec_result)])
    return converted_result
