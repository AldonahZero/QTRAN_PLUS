"""
QTRAN 项目入口：解析命令行参数并启动两阶段流程

作用概述：
- 程序入口，负责解析 --input_filename、--tool 等参数。
- 调用 qtran_run，根据选择的来源工具（sqlancer / pinolo）驱动"转换阶段(Transfer)"与后续流程数据准备。
- 在首次运行时，按需创建各数据库与实验环境所需容器/库实例。
- 🆕 集成轻量级协调机制：基于黑板模式动态调整工作流策略。

关联流程参考：见 abstract.md 中《核心目标》《调用链概览》《阶段一：转换》章节。
"""

import sys
import os
import openai
import argparse
import json
from src.TransferLLM.translate_sqlancer import sqlancer_qtran_run
from src.TransferLLM.TransferLLM import pinolo_qtran_run
from src.Tools.DatabaseConnect.docker_create import docker_create_databases
from src.Coordinator import SimpleCoordinator

environment_variables = os.environ
os.environ["http_proxy"] = environment_variables.get("HTTP_PROXY", "")
os.environ["https_proxy"] = environment_variables.get("HTTPS_PROXY", "")
openai.api_key = os.environ.get("OPENAI_API_KEY", "")

current_file_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file_path)


def scan_databases_from_input(input_filepath):
    """
    扫描输入文件，提取所有涉及的 a_db 和 b_db 数据库。

    参数：
    - input_filepath: JSONL 输入文件路径

    返回：
    - set: 包含所有需要初始化的数据库名称集合
    """
    databases = set()
    try:
        with open(input_filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "a_db" in data:
                        databases.add(data["a_db"].lower())
                    if "b_db" in data:
                        databases.add(data["b_db"].lower())
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        print(f"Warning: Input file not found: {input_filepath}")

    return databases


def qtran_run(
    input_filename,
    tool,
    temperature=0.3,
    model="gpt-4o-mini",
    error_iteration=True,
    iteration_num=4,
    FewShot=False,
    with_knowledge=True,
    enable_coordinator=True,
):
    """
    启动 QTRAN 主流程（转换阶段入口）。

    参数：
    - input_filename: 输入文件（jsonl），包含 SQL 或 bug 报告等。
    - tool: 来源工具，"sqlancer" 或 "pinolo"。
    - temperature/model: LLM 相关设置。
    - error_iteration/iteration_num: 是否进行错误迭代及最大迭代次数。
    - FewShot/with_knowledge: 是否启用 Few-Shot 示例与特征知识库提示。
    - enable_coordinator: 🆕 是否启用协调器机制。

    行为：
    - 初始化并创建不同 fuzzer 和数据库的容器/数据库实例。
    - 🆕 如果启用协调器，根据黑板状态动态调整工作流参数。
    - 分发到对应的翻译流程：sqlancer_qtran_run 或 pinolo_qtran_run。
    """
    if tool.lower() not in ["pinolo", "sqlancer"]:
        print(tool + " hasn't been supported.")
        return

    # 解析输入文件路径：支持绝对路径、工作目录相对路径，以及项目根目录相对路径
    def _resolve_input_path(path_like: str) -> str:
        # 1) 绝对路径
        if os.path.isabs(path_like) and os.path.exists(path_like):
            return path_like
        # 2) 当前工作目录
        cwd_path = os.path.abspath(os.path.join(os.getcwd(), path_like))
        if os.path.exists(cwd_path):
            return cwd_path
        # 3) 项目根目录（src 的上一级）
        project_root = os.path.dirname(current_dir)
        root_path = os.path.abspath(os.path.join(project_root, path_like))
        if os.path.exists(root_path):
            return root_path
        raise FileNotFoundError(
            f"Input file not found. Tried: '{path_like}', '{cwd_path}', '{root_path}'."
        )

    resolved_input = _resolve_input_path(input_filename)

    # 🆕 协调器初始化
    coordinator = None
    if enable_coordinator and os.environ.get("QTRAN_USE_MEM0", "false").lower() == "true":
        print("\n" + "="*60)
        print("🧠 初始化协调器（Coordinator）")
        print("="*60)
        coordinator = SimpleCoordinator(user_id="qtran_redis_to_mongodb")
        if coordinator.initialize_memory_manager():
            # 轮询黑板状态
            print("📡 轮询黑板状态...")
            state = coordinator.poll_state()
            
            # 决策策略
            print("🤔 分析反馈并决策策略...")
            strategy = coordinator.decide_strategy(state)
            
            # 准备基础参数
            base_params = {
                "temperature": temperature,
                "iteration_num": iteration_num,
                "model": model,
                "error_iteration": error_iteration,
                "FewShot": FewShot,
                "with_knowledge": with_knowledge,
            }
            
            # 应用策略调整参数
            print("⚙️ 应用策略调整...")
            adjusted_params = coordinator.adjust_workflow_params(base_params, strategy)
            
            # 更新实际使用的参数
            temperature = adjusted_params["temperature"]
            iteration_num = adjusted_params["iteration_num"]
            model = adjusted_params["model"]
            error_iteration = adjusted_params["error_iteration"]
            FewShot = adjusted_params["FewShot"]
            with_knowledge = adjusted_params["with_knowledge"]
            
            print("✅ 协调器初始化完成\n")
        else:
            print("⚠️ 协调器初始化失败，使用默认参数\n")
            coordinator = None
    elif enable_coordinator:
        print("ℹ️ 协调器未启用：需要设置 QTRAN_USE_MEM0=true")
        coordinator = None

    # 扫描输入文件，获取实际需要的数据库
    required_dbs = scan_databases_from_input(resolved_input)

    # 如果扫描到了数据库，只初始化这些数据库；否则使用默认列表
    if required_dbs:
        print(f"检测到输入文件中使用的数据库: {sorted(required_dbs)}")
        dbs = list(required_dbs)
    else:
        print("未检测到特定数据库，使用默认数据库列表")
        dbs = [
            "clickhouse",
            "duckdb",
            "mariadb",
            "monetdb",
            "mysql",
            "postgres",
            "sqlite",
            "tidb",
            "redis",
            "mongodb",
            "tdsql",
        ]

    fuzzers = ["norec", "tlp", "pinolo", "dqe"]

    # 可选：通过环境变量跳过 Docker 初始化（快速校验模式）
    if os.environ.get("QTRAN_SKIP_DOCKER", "0") != "1":
        print(f"开始初始化 {len(dbs)} 个数据库...")
        for db in dbs:
            docker_create_databases(tool, "temp", db)
            for fuzzer in fuzzers:
                docker_create_databases(tool, fuzzer, db)
        print("数据库初始化完成")
    else:
        print("跳过 Docker 初始化（QTRAN_SKIP_DOCKER=1）")

    if tool.lower() == "sqlancer":
        sqlancer_qtran_run(
            input_filepath=resolved_input,
            tool=tool,
            temperature=temperature,
            model=model,
            error_iteration=error_iteration,
            iteration_num=iteration_num,
            FewShot=FewShot,
            with_knowledge=with_knowledge,
        )
    elif tool.lower() == "pinolo":
        pinolo_qtran_run(
            input_filename=resolved_input,
            tool=tool,
            temperature=temperature,
            model=model,
            error_iteration=error_iteration,
            iteration_num=iteration_num,
            FewShot=FewShot,
            with_knowledge=with_knowledge,
        )
    
    # 🆕 输出协调器统计报告
    if coordinator:
        coordinator.report_stats()


def main():
    """
    命令行入口：解析参数并调用 qtran_run。
    示例：python -m src.main --input_filename Input/demo.jsonl --tool sqlancer
    """
    parser = argparse.ArgumentParser(description="Run QTRAN for SQL translation.")
    parser.add_argument(
        "--input_filename",
        type=str,
        required=True,
        help="Path to the input file (JSONL format).",
    )
    parser.add_argument(
        "--tool",
        type=str,
        required=True,
        choices=["sqlancer", "pinolo"],
        help="Tool to use (sqlancer or pinolo).",
    )
    parser.add_argument(
        "--temperature", type=float, default=0.3, help="Temperature for LLM."
    )
    parser.add_argument(
        "--model", type=str, default="gpt-4o-mini", help="Model to use for LLM."
    )
    parser.add_argument(
        "--error_iteration", type=bool, default=True, help="Enable error iteration."
    )
    parser.add_argument(
        "--iteration_num", type=int, default=4, help="Number of iterations."
    )
    parser.add_argument(
        "--FewShot", type=bool, default=False, help="Enable Few-Shot learning."
    )
    parser.add_argument(
        "--with_knowledge",
        type=bool,
        default=True,
        help="Use knowledge-based processing.",
    )
    parser.add_argument(
        "--enable_coordinator",
        type=bool,
        default=True,
        help="🆕 Enable coordinator mechanism for dynamic workflow adjustment.",
    )

    args = parser.parse_args()

    qtran_run(
        input_filename=args.input_filename,
        tool=args.tool,
        temperature=args.temperature,
        model=args.model,
        error_iteration=args.error_iteration,
        iteration_num=args.iteration_num,
        FewShot=args.FewShot,
        with_knowledge=args.with_knowledge,
        enable_coordinator=args.enable_coordinator,
    )


if __name__ == "__main__":
    main()
