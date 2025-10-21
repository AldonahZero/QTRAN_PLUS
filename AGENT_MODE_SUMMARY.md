# 🧪 Agent 模式测试套件使用指南

## 📦 已创建的测试脚本

### ✅ 核心测试脚本（已加入 .gitignore）

1. **`test_agent_transfer.py`** - Transfer 阶段测试
   - 测试 Redis → MongoDB 翻译
   - 验证 Agent 模式的翻译能力
   
2. **`test_agent_mutation.py`** - Mutation 阶段测试  
   - 测试 TLP、NoREC、Semantic 变异
   - 验证 Agent 模式的变异生成
   
3. **`test_agent_full_pipeline.py`** - 完整流程测试
   - 端到端测试 Transfer + Mutation
   - 验证两阶段集成

### 🔧 辅助脚本

4. **`run_agent_tests.sh`** - 测试套件启动器
   - 批量运行所有测试
   - 生成测试报告

5. **`check_agent_setup.py`** - 配置检查工具
   - 检查环境变量配置
   - 验证依赖安装情况
   - 显示当前模式（Agent / Fine-tune）

6. **`AGENT_TESTS_README.md`** - 详细使用文档

## 🚀 快速开始

### 步骤 1: 检查配置
```bash
python check_agent_setup.py
```

### 步骤 2: 安装缺失依赖（如果有）
```bash
pip install openai langchain langchain_openai
```

### 步骤 3: 运行测试
```bash
# 运行所有测试
./run_agent_tests.sh

# 或单独运行
python3 test_agent_mutation.py
python3 test_agent_transfer.py
python3 test_agent_full_pipeline.py
```

## 📊 当前发现

### ✅ 已完成
1. **JSON 修复集成** (`json-repair`)
   - 在 `translate_sqlancer.py` 中集成
   - 在 `MutateLLM.py` 中集成
   - 自动修复 LLM 生成的格式错误

2. **TLP Oracle 检查器** (`tlp_checker.py`)
   - 实现 TLP 不变式验证
   - 处理 null → 0 转换
   - 生成详细的 bug 报告

3. **代码结构**
   - Agent 模式和 Fine-tune 模式共存
   - 通过环境变量切换

### ⚠️ 待解决（当前环境）

1. **依赖缺失** (在你的本地环境)
   - `openai` - OpenAI Python 客户端
   - `langchain` - LangChain 框架
   - `langchain_openai` - LangChain OpenAI 集成

2. **当前使用模式**
   - 默认: **Fine-tune 模式**
   - 需要微调模型 ID (在 `run.sh` 中已配置)

## 🔄 两种模式对比

### Fine-tune 模式（当前默认）

**原理：**
- 使用微调过的 `gpt-4o-mini` 模型
- 每个 Oracle 类型对应一个模型 ID
- 直接调用 OpenAI Chat Completions API

**优点：**
- ✅ 快速（单次调用）
- ✅ 成本低（微调模型便宜）
- ✅ 稳定输出格式
- ✅ 适合批量测试

**缺点：**
- ❌ 需要预先微调模型
- ❌ 调试困难（黑盒）
- ❌ 修改策略需重新微调

**使用场景：**
- 生产环境批量测试
- 已验证的测试策略
- 成本敏感场景

### Agent 模式（可选）

**原理：**
- 使用 LangChain Agent 框架
- Agent 可调用工具（get_oracle_rules, validate_sql_syntax 等）
- 多轮对话生成高质量变异

**优点：**
- ✅ 灵活（可动态调整）
- ✅ 可解释（有推理过程）
- ✅ 易于调试（可查看中间步骤）
- ✅ 无需微调

**缺点：**
- ❌ 慢（多轮调用）
- ❌ 成本高（多次 API 调用）
- ❌ 输出可能不稳定

**使用场景：**
- 探索新的测试策略
- 调试问题案例
- 研究阶段

## 🎯 回答你的问题

> 现在的变异和翻译都是 agent 输出的吗，不是 llm?

**答案：目前是 Fine-tune LLM 模式（默认）**

查看配置：
```bash
$ python check_agent_setup.py
环境变量检查:
   QTRAN_TRANSFER_ENGINE: 未设置
   QTRAN_MUTATION_ENGINE: 未设置
   ℹ️  当前使用 Fine-tune 模式（默认）
```

### 代码逻辑（`MutateLLM.py` 第401行）:
```python
engine = os.environ.get("QTRAN_MUTATION_ENGINE", "finetune").lower()

if engine == "agent":
    # 使用 Agent 模式
    agent_payload = _agent_generate_mutations(...)
else:
    # 使用 Fine-tune 模式（默认）
    completion = client.chat.completions.create(
        model=model_id,  # 微调模型 ID
        messages=formatted_input
    )
```

### 当前输出来源：

**翻译 (Transfer):**
- 模块：`src/TransferLLM/TransferLLM.py`
- 方法：`transfer_llm_nosql_crash()`
- 模型：基础 `gpt-4o-mini` (无微调)
- 特点：使用 prompt template

**变异 (Mutation):**
- 模块：`src/MutationLlmModelValidator/MutateLLM.py`  
- 方法：`run_muatate_llm_single_sql()`
- 模型：微调的 `gpt-4o-mini`
  - TLP: `ft:gpt-4o-mini-2024-07-18:personal:tlp:CGIh8iHH`
  - NoREC: `ft:gpt-4o-mini-2024-07-18:personal:norec:CGI535gT`
  - Semantic: `ft:gpt-4o-mini-2024-07-18:personal:semantic:CHn8HTp0`
- 特点：专门针对各 Oracle 微调

## 🔧 如何启用 Agent 模式

如果想使用 Agent 模式进行测试：

```bash
# 1. 安装依赖
pip install openai langchain langchain_openai

# 2. 设置环境变量
export QTRAN_MUTATION_ENGINE=agent
export QTRAN_TRANSFER_ENGINE=agent
export OPENAI_API_KEY="your-key"

# 3. 运行测试
./run_agent_tests.sh
```

## 📝 建议

基于当前的实现和测试结果：

1. **继续使用 Fine-tune 模式** （推荐）
   - 已经有训练好的模型
   - 性能和成本都更优
   - TLP/NoREC prompts 已经优化

2. **使用 json-repair 修复格式错误** （已集成）
   - 自动修复 LLM 生成的 JSON 错误
   - 适用于两种模式

3. **Agent 模式作为备选**
   - 仅在需要调试时启用
   - 或探索新策略时使用

## 📂 文件清单

```
QTRAN_PLUS/
├── test_agent_transfer.py         # 翻译测试 (含密钥, gitignore)
├── test_agent_mutation.py         # 变异测试 (含密钥, gitignore)
├── test_agent_full_pipeline.py    # 完整流程 (含密钥, gitignore)
├── run_agent_tests.sh             # 测试套件
├── check_agent_setup.py           # 配置检查
├── AGENT_TESTS_README.md          # 详细文档
├── AGENT_MODE_SUMMARY.md          # 本文件
└── .gitignore                     # 已更新（排除含密钥的脚本）
```

## 🎉 总结

- ✅ 测试脚本已创建
- ✅ 安全配置（密钥保护）
- ✅ 文档完善
- ⏳ 需要安装 Agent 依赖（可选）
- 💡 当前使用 Fine-tune 模式（工作正常）
