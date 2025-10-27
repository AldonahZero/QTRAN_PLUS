# 协调器快速参考

## 🚀 快速开始

### 启用协调器运行
```bash
cd /root/QTRAN
source venv/bin/activate

export QTRAN_USE_MEM0=true
export OPENAI_API_KEY="your_key"

python -m src.main --input_filename Input/demo.jsonl --tool sqlancer
```

### 禁用协调器运行
```bash
python -m src.main \
  --input_filename Input/demo.jsonl \
  --tool sqlancer \
  --enable_coordinator False
```

## 📁 新增文件

```
src/Coordinator/
├── __init__.py                    # 模块导出
└── SimpleCoordinator.py           # 协调器实现（247行）

tests/
└── test_coordinator.py            # 单元测试（222行）
```

## 🔧 主要改动

### `src/main.py`（约50行改动）
1. 导入 `SimpleCoordinator`
2. 添加 `enable_coordinator` 参数
3. 在工作流前插入协调逻辑
4. 在工作流后输出统计报告

**改动位置**：
- Line 21: 导入语句
- Line 61-150: 协调器初始化和参数调整（在 `qtran_run` 函数内）
- Line 209: 输出统计报告
- Line 253-257: 命令行参数

## 🎯 核心功能

| 功能 | 说明 |
|------|------|
| 状态轮询 | 从 Mem0 读取 Recommendation + Hotspot |
| 策略决策 | 基于规则调整 temperature 和 iteration_num |
| 参数应用 | 动态修改工作流参数 |
| 统计报告 | 输出协调器运行数据 |

## 📊 决策规则

```python
# 规则1: 高优先级建议 (priority >= 8)
if has_high_priority_recommendation:
    temperature = 0.2  # 降低随机性

# 规则2: 高覆盖率 Hotspot (coverage_gain > 10)
if has_high_coverage_hotspot:
    iteration_num = 6  # 增加迭代次数

# 规则3: 无反馈
if no_feedback:
    # 保持默认参数，探索模式
```

## ✅ 测试

```bash
# 运行单元测试
python tests/test_coordinator.py

# 预期输出：
# 🎉 所有测试通过！（8个测试用例）
```

## 🔍 故障排查

### ✅ 问题：Mem0 初始化失败（已修复）

**早期版本的错误**：
```
⚠️ 协调器：Mem0 初始化失败 (No module named 'src.TransferLLM.TransferMemoryManager')
⚠️ 协调器初始化失败，使用默认参数
```

**解决方案**：已在最新版本中修复
- 修复了导入路径：`mem0_adapter` 而非 `TransferMemoryManager`
- 修复了方法名：`get_recommendations()` 和 `get_coverage_hotspots()`
- 详见 [BUGFIX_coordinator.md](BUGFIX_coordinator.md)

### 问题：Mem0 服务不可用

如果看到以下警告：
```
⚠️ Failed to initialize Mem0 with Qdrant, falling back to in-memory mode
```

**原因**：Qdrant 服务未运行或无法连接

**解决**：
1. 启动 Qdrant：`docker run -p 6333:6333 qdrant/qdrant`
2. 或使用内存模式（自动回退，适合测试）

**影响**：使用 ChromaDB 内存模式，功能正常但不持久化

## 📈 效果预期

根据 DCFF 设计，协调器预期带来：
- Bug 检出率提升：+20-30%
- 覆盖率增长速度：+30-40%
- 测试效率提升：+15-25%

## 📚 完整文档

- [CHANGELOG_coordinator.md](CHANGELOG_coordinator.md) - 详细实现说明
- [docs/协调器使用指南.md](docs/协调器使用指南.md) - 完整用户指南

---

**版本**: v1.7  
**更新**: 2025-10-27  
**状态**: ✅ 可用

