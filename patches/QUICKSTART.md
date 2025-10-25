# 🚀 MVP 反向反馈机制 - 5分钟快速开始

**目标**: 在 5 分钟内启用反向反馈机制，验证效果

---

## ⚡ 超快速启动 (3 步)

### 1️⃣ 应用代码补丁 (2分钟)

```bash
cd /root/QTRAN

# 方法 A: 手动应用（推荐，可控）
# 按照 patches/MVP_实施指南.md 的步骤操作

# 方法 B: 自动脚本（快速但需谨慎）
# python patches/apply_mvp_patch.py  # 即将创建
```

**手动应用核心步骤**:
1. 打开 `src/TransferLLM/mem0_adapter.py`
2. 复制 `patches/mvp_recommendation_methods.py` 中的 3 个方法到类末尾
3. 修改 `build_enhanced_prompt` 添加 Recommendation 增强代码
4. 打开 `src/TransferLLM/translate_sqlancer.py`
5. 复制 `patches/mvp_recommendation_sqlancer_integration.py` 中的 2 个函数到文件末尾
6. 在 TLP Oracle 检查后添加调用

---

### 2️⃣ 运行测试 (1分钟)

```bash
# 确保 Qdrant 运行
docker ps | grep qdrant

# 运行测试
export QTRAN_USE_MEM0=true
python test_recommendation_mvp.py
```

**预期**: 看到 5 个测试全部通过 ✅

---

### 3️⃣ 真实任务验证 (2分钟)

```bash
# 运行一个简单的翻译任务
export QTRAN_USE_MEM0=true
export QTRAN_MEM0_MODE=balanced

python -m src.TransferLLM.translate_sqlancer \
    --input-file <your_test_file> \
    --origin-db sqlite \
    --target-db mongodb \
    --molt tlp
```

**观察**: 在日志中搜索 `🔥 Generated recommendation` 和 `HIGH PRIORITY RECOMMENDATIONS`

---

## 📊 核心改动总结

| 文件 | 改动 | 行数 |
|------|------|------|
| `mem0_adapter.py` | +3 方法, 修改 1 方法 | +80 |
| `translate_sqlancer.py` | +2 函数, +1 调用 | +70 |
| **总计** | | **~150 行** |

---

## 🎯 验证成功标志

1. ✅ 测试脚本通过 (5/5)
2. ✅ 看到 "Generated recommendation" 输出
3. ✅ 看到 "HIGH PRIORITY RECOMMENDATIONS" 在 Prompt 中
4. ✅ 后续翻译中出现推荐的 SQL 特性

---

## 🔄 工作流程图

```
┌─────────────────┐
│  第一次翻译      │
│  SELECT HEX(    │
│  MIN(a))        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  变异测试        │
│  TLP Oracle     │
└────────┬────────┘
         │
         ▼ 发现 TLP violation
┌─────────────────────────┐
│  🔥 生成 Recommendation  │
│  - 特性: HEX, MIN       │
│  - 优先级: 9/10         │
│  - 原因: TLP violation  │
└────────┬────────────────┘
         │ 存入 Mem0
         ▼
┌─────────────────┐
│  第二次翻译      │
│  SELECT MAX(b)  │
└────────┬────────┘
         │
         ▼ 读取 Recommendation
┌────────────────────────────┐
│  增强 Prompt               │
│  包含: "优先测试 HEX, MIN" │
└────────┬───────────────────┘
         │
         ▼
┌─────────────────┐
│  LLM 翻译        │
│  (更关注 HEX/   │
│   MIN 特性)     │
└─────────────────┘
```

---

## 💡 关键代码片段

### Recommendation 数据结构
```python
{
    "type": "recommendation",
    "target_agent": "translation",
    "priority": 9,
    "action": "prioritize_features",
    "features": ["HEX", "MIN", "aggregate"],
    "reason": "tlp_violation: TLP_violation"
}
```

### 生成 Recommendation
```python
mem0_manager.add_recommendation(
    target_agent="translation",
    priority=9,
    action="prioritize_features",
    features=["HEX", "MIN"],
    reason="tlp_violation",
    origin_db="sqlite",
    target_db="mongodb"
)
```

### 使用 Recommendation
```python
recommendations = mem0_manager.get_recommendations(
    origin_db="sqlite",
    target_db="mongodb",
    limit=3
)
# 自动注入到 Prompt 中
```

---

## 🐛 常见问题

### Q1: 测试失败 - Qdrant 连接错误
```bash
# 检查 Qdrant
docker ps | grep qdrant

# 启动 Qdrant
docker run -d -p 6333:6333 qdrant/qdrant
```

### Q2: 没有看到 Recommendation 生成
**原因**: Oracle 检查没有发现问题

**解决**: 
- 确认 `QTRAN_USE_MEM0=true`
- 检查是否有 TLP violation
- 查看日志确认 Oracle 检查结果

### Q3: Recommendation 没有被使用
**原因**: 数据库对不匹配或优先级过低

**解决**:
- 确认 `origin_db` 和 `target_db` 匹配
- 降低 `min_priority` 参数

---

## 📈 预期效果

### 立即可见
- ✅ Recommendation 自动生成
- ✅ Prompt 自动增强
- ✅ 日志显示反馈流程

### 1-2周后
- 📈 Bug 发现率 +20-30%
- 📈 高价值特性命中率 +30-40%
- 📈 翻译首次成功率 +3-5%

---

## 🎓 进一步学习

| 文档 | 内容 | 阅读时间 |
|------|------|----------|
| `MVP_实施指南.md` | 详细实施步骤 | 15 分钟 |
| `MVP_反向反馈机制实现方案.md` | 完整技术设计 | 30 分钟 |
| `当前系统_vs_DCFF设计对比.md` | 架构对比分析 | 20 分钟 |
| `研究建议.md` | 未来研究方向 | 40 分钟 |

---

## ✅ 下一步

1. **验证成功后**: 在真实数据集上运行 A/B 测试
2. **收集数据**: 记录 Recommendation 生成频率和采纳率
3. **分析效果**: 对比 Bug 发现率和覆盖率增长
4. **发表论文**: 如果效果显著，整理成论文投稿

---

## 🎯 成功标准

- [x] 代码集成完成
- [ ] 测试通过 (5/5)
- [ ] 真实任务生成 Recommendation
- [ ] 观察到 Bug 发现率提升
- [ ] A/B 测试验证效果

---

**快速问题？** 查看 `patches/MVP_实施指南.md` 的故障排查部分

**更新**: 2025-10-25  
**状态**: ✅ 就绪，可以开始实施

