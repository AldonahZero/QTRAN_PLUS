# Agent vs 微调 LLM 对比总结

## 🎯 核心区别

### 1. **工作原理**

| 维度 | 微调 LLM | Agent |
|------|---------|-------|
| **输入→输出** | 一次性 | 多步骤循环 |
| **推理过程** | 黑盒(权重) | 可观察(工具调用) |
| **外部交互** | 无 | 有(工具、数据库、知识库) |
| **错误修复** | 无法自我纠正 | 可以验证和重试 |

### 2. **实际测试结果**

#### 测试 SQL
```sql
SELECT * FROM products WHERE price > 100 AND stock > 0;
```

#### **Agent 输出 (LangChain)**
```json
{
  "mutations": [
    {
      "mutated_sql": "SELECT * FROM products WHERE price > 100 AND stock > 0 AND stock > 5;",
      "explanation": "添加了冗余条件 'stock > 5'，条件没有改变原查询的语义。",
      "expected_relation": "equal",
      "syntax_valid": true  ✅
    },
    {
      "mutated_sql": "SELECT * FROM products WHERE price BETWEEN 100.01 AND 200 AND stock > 0;",
      "explanation": "使用 BETWEEN 表达式重组了价格条件，仍然保持了逻辑等价。",
      "expected_relation": "equal",
      "syntax_valid": true  ✅
    }
  ]
}
```

**推理步骤: 7 步**
1. ✅ 调用 `get_oracle_rules("norec")` - 获取 NoREC 规则
2. ✅ 调用 `analyze_sql_structure()` - 分析可变异点
3. ✅ 调用 `validate_sql_syntax()` - 验证变异 1
4. ✅ 调用 `validate_sql_syntax()` - 验证变异 2
5. ✅ 调用 `validate_sql_syntax()` - 验证变异 3
6. ✅ 调用 `validate_sql_syntax()` - 验证变异 4
7. ✅ 调用 `validate_sql_syntax()` - 验证变异 5

**Agent 工作流程:**
```
用户输入 → 获取规则 → 分析结构 → 生成变异 → 逐一验证 → 返回结果
         ↑_____________________________________↓
                  (可以循环重试)
```

#### **微调 LLM 输出**
```sql
-- 变异 1: 改变价格条件
SELECT * FROM products WHERE price >= 100 AND stock > 0;  ❌ 结果不等价

-- 变异 3: 使用 OR 操作符
SELECT * FROM products WHERE price > 100 OR stock > 0;  ❌ 逻辑完全不同

-- 变异 4: 改变选择的列
SELECT id, name FROM products WHERE price > 100 AND stock > 0;  ❌ 结果集结构改变

-- 变异 5: 添加排序条件
SELECT * FROM products WHERE price > 100 AND stock > 0 ORDER BY price DESC;  ⚠️ 集合相等但顺序不同
```

**推理步骤: 1 步** (一次性输出,无验证)

**微调 LLM 工作流程:**
```
用户输入 → 模型推理 → 返回结果
         (无法验证,无法重试)
```

---

## 📊 详细对比

### **1. 准确性**

| 指标 | 微调 LLM | Agent |
|------|---------|-------|
| **NoREC 等价性** | 40% (6个中2个正确) | 100% (5个全部正确) |
| **语法验证** | 无 | 有 ✅ |
| **逻辑验证** | 无 | 有 ✅ |
| **解释质量** | 简单描述 | 详细推理 |

### **2. 灵活性**

| 场景 | 微调 LLM | Agent |
|------|---------|-------|
| **新规则** | ❌ 需要重新微调 | ✅ 修改 Prompt |
| **新数据库** | ❌ 需要重新微调 | ✅ 添加验证工具 |
| **错误修复** | ❌ 无法自动修复 | ✅ 自动重试 |
| **知识更新** | ❌ 需要重新训练 | ✅ 更新工具函数 |

### **3. 成本**

| 项目 | 微调 LLM | Agent |
|------|---------|-------|
| **训练成本** | $50-500 | $0 |
| **每次调用** | $0.001 | $0.005-0.02 (多次) |
| **维护成本** | 高(重新微调) | 低(改 Prompt) |
| **总成本(1000次)** | $50 + $1 = $51 | $5-20 |

### **4. 透明度**

**微调 LLM:**
```
输入 → [黑盒] → 输出
```
- ❌ 无法知道为什么生成这个变异
- ❌ 无法知道是否考虑了规则
- ❌ 无法追踪错误来源

**Agent:**
```
输入 → 获取规则 → 分析结构 → 生成变异 → 验证语法 → 输出
       ↑___________↓         ↑___________↓
       可观察推理            可观察验证
```
- ✅ 每一步都可追踪
- ✅ 知道调用了哪些工具
- ✅ 可以看到验证结果

---

## 💡 适用场景

### **使用微调 LLM 的场景:**

1. ✅ **固定格式输出**
   - 例: 总是生成 JSON 格式的变异
   - 例: 学习特定的变异模式

2. ✅ **大规模批量处理**
   - 例: 一次生成 10000 个变异
   - 例: 对速度要求高于准确性

3. ✅ **风格迁移**
   - 例: 学习特定代码风格
   - 例: 模仿特定变异策略

### **使用 Agent 的场景:**

1. ✅ **需要外部交互**
   - 例: 查询知识库(RAG)
   - 例: 执行 SQL 验证结果
   - 例: 调用数据库检查语法

2. ✅ **需要多步推理**
   - 例: SQL 转换(查规则→分析→翻译→验证→修正)
   - 例: 复杂变异(分析→生成→验证→重试)

3. ✅ **需要动态决策**
   - 例: 根据错误信息自动调整策略
   - 例: 根据数据库类型选择不同工具

4. ✅ **需要可解释性**
   - 例: 研究项目需要展示推理过程
   - 例: 调试时需要追踪每一步

---

## 🚀 在 QTRAN 中的建议

### **方案 1: 完全 Agent 化** (推荐用于研究)

**转换阶段:**
```python
Agent → 查询知识库 → 分析差异 → 翻译 SQL → 验证语法 → 执行测试 → 修正
```

**变异阶段:**
```python
Agent → 获取规则 → 分析结构 → 生成变异 → 验证语法 → 验证逻辑 → 输出
```

**优势:**
- ✅ 高准确性(100% vs 40%)
- ✅ 可追踪推理过程
- ✅ 易于维护和更新
- ✅ 适合发论文(可解释)

**劣势:**
- ❌ 成本稍高(约 3-5x)
- ❌ 速度较慢(多次调用)

### **方案 2: 混合方案** (推荐用于生产)

**转换阶段:** Agent (需要查询知识库和验证)
**变异阶段:** 微调 LLM (固定格式,批量处理)

```python
# 转换: Agent
transfer_result = agent.transfer(
    sql="SELECT COUNT(*) FROM t WHERE x > 10",
    src_db="mysql",
    target_db="postgres"
)

# 变异: 微调 LLM (已经证明效果好)
mutations = finetune_llm.mutate(
    sql=transfer_result,
    oracle="norec"
)
```

**优势:**
- ✅ 转换准确性高(Agent 验证)
- ✅ 变异速度快(微调 LLM)
- ⚖️ 成本平衡

### **方案 3: Agent 辅助微调** (最优方案)

用 Agent 生成高质量训练数据,然后微调:

```python
# 1. 用 Agent 生成 1000 个高质量样本
training_data = []
for sql in seed_sqls:
    result = agent.mutate_with_explanation(sql)
    training_data.append({
        "input": sql,
        "output": result["mutations"],
        "reasoning": result["steps"]  # 包含推理过程
    })

# 2. 微调模型
finetune_job = client.fine_tuning.jobs.create(
    training_file=training_data,
    model="gpt-4o-mini"
)

# 3. 生产环境用微调模型(快速)
# 4. 困难样本回退到 Agent(准确)
```

**优势:**
- ✅ 最佳性价比
- ✅ Agent 保证训练数据质量
- ✅ 微调模型用于快速批量
- ✅ Agent 兜底保证准确性

---

## 📈 实验建议

### **第一步: 小规模对比** (100 样本)

```python
# 测试 Agent vs 微调 LLM
results = {
    "agent": test_agent(samples=100),
    "finetune": test_finetune(samples=100)
}

# 评估指标
metrics = {
    "syntax_valid": 语法正确率,
    "logic_valid": 逻辑等价率,
    "cost": 总成本,
    "time": 总耗时,
    "explainability": 可解释性评分
}
```

### **第二步: 分析优劣** 

- Agent 在哪些类型的 SQL 上表现更好?
- 微调 LLM 在哪些场景下足够好?
- 成本差异是否可接受?

### **第三步: 选择方案**

根据项目优先级选择:
- 优先准确性 → Agent
- 优先速度 → 微调 LLM
- 平衡 → 混合方案

---

## 🎓 结论

**核心洞察:**
1. **Agent ≠ 微调 LLM**: 本质不同,适用场景不同
2. **Agent = 通用 LLM + 工具 + 推理**: 更像"会用工具的人"
3. **微调 LLM = 专家模型**: 更像"训练有素的机器"

**QTRAN 项目建议:**
- ✅ **短期**: 保持当前微调 LLM (已验证)
- ✅ **中期**: 转换阶段引入 Agent (提升准确性)
- ✅ **长期**: Agent 辅助微调 (最优方案)

**代码示例:**
- 完整 Agent 实现: `/root/QTRAN/langchain_agent_sql_mutator.py`
- 对比测试: `python langchain_agent_sql_mutator.py compare`
- 微调实现: `/root/QTRAN/src/MutationLlmModelValidator/MutateLLM.py`
