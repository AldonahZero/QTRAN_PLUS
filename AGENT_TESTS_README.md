# Agent 模式测试说明

## 📋 概述

这些测试脚本用于验证 QTRAN 的 Agent 模式（使用 LangChain Agent 而非微调模型）。

## 🔐 安全注意

**⚠️ 这些测试脚本包含 OpenAI API 密钥，已添加到 .gitignore 中，请勿提交！**

包含密钥的文件：
- `test_agent_transfer.py`
- `test_agent_mutation.py`
- `test_agent_full_pipeline.py`

## 📁 测试文件

### 1. `test_agent_transfer.py` - 翻译阶段测试
- 测试 Redis → MongoDB 的翻译功能
- 使用 Agent 模式进行跨数据库方言转换
- 不执行数据库操作，只测试 LLM 生成

**运行：**
```bash
python3 test_agent_transfer.py
```

### 2. `test_agent_mutation.py` - 变异阶段测试
- 测试 TLP、NoREC、Semantic 三种变异策略
- 验证 Agent 能否正确生成变异用例
- 不执行数据库操作

**运行：**
```bash
python3 test_agent_mutation.py
```

### 3. `test_agent_full_pipeline.py` - 完整流程测试
- 端到端测试：Transfer + Mutation
- 验证两个阶段的衔接
- 模拟完整的测试流程

**运行：**
```bash
python3 test_agent_full_pipeline.py
```

### 4. `run_agent_tests.sh` - 测试套件
运行所有测试并生成总结报告

**运行：**
```bash
./run_agent_tests.sh
```

## 🔧 环境变量

测试脚本自动设置以下环境变量：

```bash
export QTRAN_TRANSFER_ENGINE="agent"    # 使用 Agent 进行翻译
export QTRAN_MUTATION_ENGINE="agent"    # 使用 Agent 进行变异
export OPENAI_API_KEY="sk-proj-..."    # OpenAI API 密钥
export HTTP_PROXY="http://127.0.0.1:7890"
export HTTPS_PROXY="http://127.0.0.1:7890"
```

## 📊 预期输出

### Transfer 测试
```
🔧 测试 Transfer 阶段 - Agent 模式
============================================================

测试 1: 简单 KV 操作
输入: ['set mykey hello;', 'get mykey;']
✅ 翻译成功
   结果: db.myCollection.insertOne({ mykey: 'hello' })...
   成本: {...}
   耗时: 2.34s
```

### Mutation 测试
```
🔧 测试 Mutation 阶段 - Agent 模式
============================================================

测试 1: MongoDB TLP Mutation
输入 SQL: db.myCollection.findOne({ mykey: "hello" })
Oracle: tlp
✅ 变异成功
   生成了 4 个变异
   变异 1: original
   变异 2: tlp_true
   变异 3: tlp_false
   变异 4: tlp_null
```

### 完整流程测试
```
🔧 完整流程测试：Transfer + Mutation (Agent 模式)
============================================================
📤 阶段 1: Transfer (翻译)
✅ Transfer 成功
🔀 阶段 2: Mutation (变异)
✅ Mutation 成功
💡 Agent 模式正常工作！
```

## 🆚 Agent vs Fine-tune 对比

| 特性 | Agent 模式 | Fine-tune 模式 |
|------|-----------|----------------|
| 引擎 | LangChain Agent | 微调模型 |
| 灵活性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 准确性 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 成本 | 较高 | 较低 |
| 可解释性 | ⭐⭐⭐⭐⭐ (有推理过程) | ⭐⭐ |
| 适用场景 | 探索、调试、新策略 | 生产环境、批量测试 |

## 🐛 故障排查

### 问题：代理连接失败
```
Error: ProxyError
```
**解决：** 确保 Clash 或其他代理工具运行在 7890 端口

### 问题：API 密钥无效
```
Error: AuthenticationError
```
**解决：** 检查 `OPENAI_API_KEY` 是否正确且未过期

### 问题：模块导入失败
```
ModuleNotFoundError: No module named 'langchain_openai'
```
**解决：** 安装依赖
```bash
pip install -r requirements.txt
```

## 📝 修改 API 密钥

如果需要更新 API 密钥，请编辑测试脚本：

```python
os.environ["OPENAI_API_KEY"] = "your-new-key-here"
```

**记住：修改后不要提交到 Git！**

## 🚀 下一步

测试通过后，可以：

1. **运行完整测试**
   ```bash
   python src/main.py --input_filename Input/queue_test.jsonl --tool sqlancer
   ```

2. **切换回 Fine-tune 模式**
   ```bash
   unset QTRAN_TRANSFER_ENGINE
   unset QTRAN_MUTATION_ENGINE
   ```

3. **对比两种模式的效果**
   - Agent: 更灵活，可调试
   - Fine-tune: 更快，更便宜
