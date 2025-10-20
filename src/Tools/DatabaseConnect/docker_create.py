"""
容器环境管理：拉取镜像、启动容器与创建测试数据库

作用概述：
- 依据配置文件生成各数据库容器，创建工具/实验隔离的数据库实例。
- 提供 run_container 与 docker_create_databases 以供主流程在启动时准备环境。
"""

import json
import subprocess
import time
import os

current_file_path = os.path.abspath(__file__)
# 获取当前文件所在目录
current_dir = os.path.dirname(current_file_path)

with open(
    os.path.join(current_dir, "docker_create_commands.json"), "r", encoding="utf-8"
) as r:
    docker_commands = json.load(r)


def get_database_connector_args(dbType):
    with open(
        os.path.join(current_dir, "database_connector_args.json"), "r", encoding="utf-8"
    ) as r:
        database_connection_args = json.load(r)
    if dbType.lower() in database_connection_args:
        return database_connection_args[dbType.lower()]


def run_command(command, capture_output=True, shell=True):
    """
    执行命令并打印结果。
    :param command: 要执行的命令列表。
    :param capture_output: 是否捕获输出。
    :param shell: 是否通过 shell 执行。
    """
    import platform

    command_str = " ".join(command)
    print(f"执行命令: {command_str}")
    # 判断当前系统
    system_type = platform.system().lower()
    if system_type == "windows":
        # Windows 下可选用 wsl
        result = subprocess.run(
            ["wsl", "-e", "bash", "-c", command_str],
            text=True,
            capture_output=capture_output,
            shell=shell,
        )
    else:
        # Linux/macOS 直接运行
        if shell:
            # shell=True 时传递字符串
            result = subprocess.run(
                command_str, text=True, capture_output=capture_output, shell=True
            )
        else:
            # shell=False 时传递列表
            result = subprocess.run(
                command, text=True, capture_output=capture_output, shell=False
            )
    # 仅在有内容（非空白）时才打印输出/错误，避免日志中出现大量空行
    if result.stdout and result.stdout.strip():
        print(f"命令输出: {result.stdout}")
    if result.stderr and result.stderr.strip():
        print(f"命令错误: {result.stderr}")
    print("---------------------------------------------------")
    return result


def check_container_running(container_name):
    """
    检查容器是否存在。
    :param container_name: 容器名称。
    :return: 如果容器存在，返回 True，否则返回 False。
    """
    # result = run_command(["docker", "ps", "-a", "-q", "-f", f"name={container_name}"])
    result = run_command(["docker", "ps", "-a", "-q", "-f", f"name={container_name}"])
    return bool(result.stdout.strip())  # 如果 stdout 非空，表示容器存在


def check_image_exists(image_name):
    """
    检查镜像是否存在。
    :param image_name: 镜像名称（例如 mysql:8.0.39）。
    :return: 如果镜像存在，返回 True，否则返回 False。
    """
    result = run_command(["docker", "images", "-q", image_name])
    return bool(result.stdout.strip())  # 如果 stdout 非空，表示镜像存在


def format_dict_strings(data, **args):
    """
    递归地遍历字典或列表，将其中的字符串项替换为 format 格式化后的字符串。
    """
    if isinstance(data, dict):
        return {key: format_dict_strings(value, **args) for key, value in data.items()}
    elif isinstance(data, list):
        return [format_dict_strings(item, **args) for item in data]
    elif isinstance(data, str):
        # 检查字符串中是否包含占位符
        if any(f"{{{key}}}" in data for key in args):
            return data.format(**args)
        return data
    else:
        return data  # 如果既不是字典、列表，也不是字符串，原样返回


def is_container_running(container_name):
    """
    判断指定容器当前是否处于运行状态。

    输入：container_name (str)
    输出：布尔值，True 表示正在运行，False 表示未运行。
    """
    result = run_command(
        ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"]
    )
    return container_name in result.stdout  # 如果 stdout 非空，表示镜像存在


def docker_create_databases(tool, exp, dbType):
    """
    根据 docker_create_commands.json 的配置，
    拉镜像、启动（或创建）容器，
    并在容器里执行初始化命令（例如建库、建用户、写入测试 key 等），
    以便准备测试/实验用的数据库环境。
    按配置自动创建并初始化数据库容器。

    输入:
      - tool: 工具名称（字符串），用于构造 dbname。
      - exp: 实验 id 或名称（字符串），用于构造 dbname。
      - dbType: 数据库类型（字符串），对应 docker_create_commands.json 中的键。

    行为：根据 dbType 的不同走不同逻辑（例如 TiDB/ClickHouse/其他），包含拉镜像、启动容器、进入容器执行建库语句等操作。
    错误处理：若命令返回非零会捕获 subprocess.CalledProcessError 并打印错误信息（保留原有行为）。
    """
    if dbType.lower() not in docker_commands:
        return
    commands = docker_commands[dbType.lower()]
    args = get_database_connector_args(dbType.lower())
    args["dbname"] = f"{tool}_{exp}_{dbType}"
    commands_formatted = format_dict_strings(commands, **args)

    try:
        if dbType.lower() in ("tidb", "tdsql"):
            # run_tidb / tdsql (tdsql treated as MySQL-protocol-compatible service)
            run_command(commands_formatted["run_container"])
            # exec_into_container, login_mysql, create_databases
            for sql in commands_formatted["create_databases"]:
                run_command(
                    commands_formatted["enter_container"]
                    + commands_formatted["login_in"]
                    + ["'" + sql + "'"]
                )
        elif dbType.lower() == "clickhouse":
            # pull_docker
            if not check_image_exists(commands_formatted["docker_name"]):
                run_command(commands_formatted["pull_docker"])
            # run_docker_container
            if not is_container_running(commands_formatted["container_name"]):
                run_command(commands_formatted["run_container"])
                time.sleep(15)
            # enable access
            if (
                "vim"
                not in run_command(
                    commands_formatted["enter_container"]
                    + ["dpkg", "-l", "|", "grep", "vim"]
                ).stdout
            ):
                for cmd in commands_formatted["access_enable"]:
                    run_command(commands_formatted["enter_container"] + cmd)
            # create admin user
            for cmd in commands_formatted["create_admin_login_in"]:
                run_command(commands_formatted["enter_container"] + cmd)
            # exec_into_container, login_mysql, create_databases
            for sql in commands_formatted["create_databases"]:
                if isinstance(sql, list):
                    run_command(
                        commands_formatted["enter_container"]
                        + commands_formatted["login_in"]
                        + sql
                    )
                elif isinstance(sql, str):
                    run_command(
                        commands_formatted["enter_container"]
                        + commands_formatted["login_in"]
                        + ["'" + sql + "'"]
                    )
        elif dbType.lower() == "redis":
            # pull image
            if not check_image_exists(commands_formatted["docker_name"]):
                run_command(commands_formatted["pull_docker"])
            # run container
            if not is_container_running(commands_formatted["container_name"]):
                run_command(commands_formatted["run_container"])
                time.sleep(5)
            # run create_databases commands (通常为 redis-cli 调用)
            for cmd in commands_formatted.get("create_databases", []):
                if isinstance(cmd, list):
                    run_command(commands_formatted["enter_container"] + cmd)
                elif isinstance(cmd, str):
                    # 字符串形式的命令，通过 shell 执行
                    run_command(
                        commands_formatted["enter_container"] + ["sh", "-c", cmd]
                    )

        elif dbType.lower() == "mongodb":
            # pull image
            if not check_image_exists(commands_formatted["docker_name"]):
                run_command(commands_formatted["pull_docker"])
            # run container
            if not is_container_running(commands_formatted["container_name"]):
                run_command(commands_formatted["run_container"])
                time.sleep(8)  # 给 mongod 一点启动时间
            # 执行初始化 JS 语句（使用 mongosh --eval）
            for js in commands_formatted.get("create_databases", []):
                if isinstance(js, list):
                    # 若以后需要拆分成数组形式，可在配置中放 list
                    run_command(commands_formatted["enter_container"] + js)
                elif isinstance(js, str):
                    # login_in 已包含 --eval，因此拼接 login_in + [js]
                    run_command(
                        commands_formatted["enter_container"]
                        + commands_formatted["login_in"]
                        + [js]
                    )

        elif dbType.lower() in ["memcached", "etcd", "consul"]:
            # 通用：拉镜像
            if not check_image_exists(commands_formatted["docker_name"]):
                run_command(commands_formatted["pull_docker"])
            # 启动容器
            if not is_container_running(commands_formatted["container_name"]):
                run_command(commands_formatted["run_container"])
                # 适度等待服务启动
                time.sleep(5)
            # 执行 create_databases / KV 测试写读
            for op in commands_formatted.get("create_databases", []):
                if isinstance(op, list):
                    run_command(commands_formatted["enter_container"] + op)
                elif isinstance(op, str):
                    # memcached 的 echo/nc 形式是一个 shell 字符串
                    run_command(
                        commands_formatted["enter_container"] + ["sh", "-c", op]
                    )

        else:
            # pull_docker
            if not check_image_exists(commands_formatted["docker_name"]):
                run_command(commands_formatted["pull_docker"])
            # run_docker_container
            if not is_container_running(commands_formatted["container_name"]):
                run_command(commands_formatted["run_container"])
                time.sleep(15)
            # exec_into_container, login_mysql, create_databases
            for sql in commands_formatted["create_databases"]:
                if isinstance(sql, list):
                    run_command(
                        commands_formatted["enter_container"]
                        + commands_formatted["login_in"]
                        + sql
                    )
                elif isinstance(sql, str):
                    run_command(
                        commands_formatted["enter_container"]
                        + commands_formatted["login_in"]
                        + ["'" + sql + "'"]
                    )

    except subprocess.CalledProcessError as e:
        print(f"命令执行失败：{e}")
        print(f"标准输出: {e.output}")
        print(f"标准错误: {e.stderr}")


def run_container(tool, exp, dbType):
    """
    尝试启动或恢复指定类型的容器实例。

    输入与 docker_create_databases 相同的参数含义（tool, exp, dbType）。
    行为：若 dbType 为 TiDB 使用专用命令，否则使用 docker start 启动容器并等待生效。
    """
    if dbType.lower() not in docker_commands:
        return
    commands = docker_commands[dbType.lower()]
    args = get_database_connector_args(dbType.lower())
    args["dbname"] = f"{tool}_{exp}_{dbType}"
    commands_formatted = format_dict_strings(commands, **args)
    try:
        if dbType.lower() in ("tidb", "tdsql"):
            # run_tidb / tdsql
            run_command(commands_formatted["run_container"])
        else:
            # run_docker_container
            run_command(["docker", "start", commands_formatted["container_name"]])
            time.sleep(15)
            """
            if not is_container_running(commands_formatted["container_name"]):
                run_command(["docker", "start", commands_formatted["container_name"]])
                time.sleep(12)
            """
    except subprocess.CalledProcessError as e:
        print(f"命令执行失败：{e}")
        print(f"标准输出: {e.output}")
        print(f"标准错误: {e.stderr}")
