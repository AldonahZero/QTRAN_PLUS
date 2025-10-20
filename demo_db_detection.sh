#!/bin/bash
# 数据库检测功能演示脚本

echo "======================================"
echo "🎯 QTRAN 智能数据库初始化演示"
echo "======================================"
echo ""

echo "📋 步骤 1: 查看输入文件"
echo "--------------------------------------"
echo "文件: Input/demo1.jsonl (前3行)"
head -n 3 Input/demo1.jsonl | python -m json.tool
echo ""

echo "📊 步骤 2: 自动检测数据库"
echo "--------------------------------------"
python test_db_detection.py
echo ""

echo "🚀 步骤 3: 模拟运行（仅检测，不实际执行）"
echo "--------------------------------------"
echo "如果要实际运行，请执行："
echo "  python -m src.main --input_filename Input/demo1.jsonl --tool sqlancer"
echo ""

echo "💡 提示:"
echo "  - 旧方式: 初始化 10 个数据库（clickhouse, duckdb, mariadb, monetdb, mysql, postgres, sqlite, tidb, redis, mongodb）"
echo "  - 新方式: 只初始化 7 个数据库（根据输入文件自动检测）"
echo "  - 节省时间: 约 30%"
echo ""

echo "✅ 演示完成！"
