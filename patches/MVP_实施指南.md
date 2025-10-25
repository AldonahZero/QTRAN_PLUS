# MVP 反向反馈机制 - 实施指南

**版本**: v1.0  
**日期**: 2025-10-25  
**预计用时**: 30-60 分钟  
**代码量**: ~150 行

---

## 📋 实施步骤总览

```
第1步: 修改 mem0_adapter.py     (3个新方法 + 1处修改) - 15分钟
第2步: 修改 translate_sqlancer.py (2个新函数 + 1处调用) - 15分钟  
第3步: 测试验证                  (运行测试脚本)        - 10分钟
第4步: 真实环境测试               (翻译任务)           - 20分钟
```

---

## 🔧 第1步: 修改 `src/TransferLLM/mem0_adapter.py`

### 1.1 添加 3 个新方法到 `TransferMemoryManager` 类

打开文件 `/root/QTRAN/src/TransferLLM/mem0_adapter.py`，在类的末尾（`get_metrics_report` 方法之后）添加以下方法：

```python
# 从 patches/mvp_recommendation_methods.py 复制以下 3 个方法：
# - add_recommendation()
# - get_recommendations()
# - mark_recommendation_used()
```

**提示**: 可以直接复制粘贴 `patches/mvp_recommendation_methods.py` 中的代码。

---

### 1.2 修改 `build_enhanced_prompt` 方法

在 `build_enhanced_prompt` 方法中，找到 **最后的 return 语句之前**，添加 Recommendation 增强逻辑。

**原代码** (大约在 line 420-430):
```python
def build_enhanced_prompt(...) -> str:
    # ... 原有逻辑 ...
    
    # 返回增强后的 prompt
    if enhanced_context:
        return f"{base_prompt}\n\n{enhanced_context}"
    return base_prompt
```

**修改为**:
```python
def build_enhanced_prompt(...) -> str:
    # ... 原有逻辑 ...
    
    # ========== 🔥 新增：Recommendation 增强 ==========
    recommendations = self.get_recommendations(
        origin_db=origin_db,
        target_db=target_db,
        limit=3,
        min_priority=7
    )
    
    if recommendations:
        enhanced_context += "\n\n" + "="*60 + "\n"
        enhanced_context += "🔥 HIGH PRIORITY RECOMMENDATIONS (from mutation feedback):\n"
        enhanced_context += "="*60 + "\n\n"
        
        for i, rec in enumerate(recommendations, 1):
            features_str = ", ".join(rec['features']) if rec['features'] else "N/A"
            enhanced_context += f"{i}. **{rec['action']}** (Priority: {rec['priority']}/10)\n"
            enhanced_context += f"   - Focus on: {features_str}\n"
            enhanced_context += f"   - Reason: {rec['reason']}\n"
            enhanced_context += f"   - Created: {rec['created_at']}\n\n"
            
            # 标记为已使用
            if rec.get('memory_id'):
                self.mark_recommendation_used(rec['memory_id'])
        
        enhanced_context += "Please prioritize these features in your translation.\n"
        enhanced_context += "="*60 + "\n"
    
    # 返回增强后的 prompt
    if enhanced_context:
        return f"{base_prompt}\n\n{enhanced_context}"
    return base_prompt
```

**验证**: 保存文件后检查语法是否正确。

---

## 🔧 第2步: 修改 `src/TransferLLM/translate_sqlancer.py`

### 2.1 在文件末尾添加辅助函数

打开 `/root/QTRAN/src/TransferLLM/translate_sqlancer.py`，在文件**末尾**添加：

```python
# 从 patches/mvp_recommendation_sqlancer_integration.py 复制以下 2 个函数：
# - _generate_recommendation_from_oracle()
# - _extract_sql_features()
```

---

### 2.2 在 Oracle 检查后调用 Recommendation 生成

在 `sqlancer_translate` 函数中，找到 TLP Oracle 检查的代码（大约在 **line 625**）。

**原代码**:
```python
if is_tlp_mutation(mutate_results[-1]):
    try:
        # ... 准备 tlp_results ...
        
        # 调用 TLP 检查器
        oracle_check_res = check_tlp_oracle(tlp_results)
        
    except Exception as e:
        print(f"TLP oracle check failed: {e}")
        oracle_check_res = {"end": False, "error": str(e)}
```

**修改为**:
```python
if is_tlp_mutation(mutate_results[-1]):
    try:
        # ... 准备 tlp_results ...
        
        # 调用 TLP 检查器
        oracle_check_res = check_tlp_oracle(tlp_results)
        
        # 🔥 新增：生成 Recommendation
        if use_mem0 and mem0_manager:
            _generate_recommendation_from_oracle(
                mem0_manager=mem0_manager,
                oracle_result=oracle_check_res,
                original_sql=sql_statement,
                origin_db=origin_db,
                target_db=target_db,
                oracle_type="tlp"
            )
        
    except Exception as e:
        print(f"TLP oracle check failed: {e}")
        oracle_check_res = {"end": False, "error": str(e)}
```

**提示**: 
- `use_mem0` 变量应该已经在函数开头定义（检查 line ~120）
- `mem0_manager` 应该已经初始化（检查 line ~1120）

---

## 🧪 第3步: 测试验证

### 3.1 运行测试脚本

```bash
cd /root/QTRAN

# 确保 Qdrant 正在运行
docker ps | grep qdrant

# 如果没有运行，启动 Qdrant:
docker run -d -p 6333:6333 qdrant/qdrant

# 运行测试
python test_recommendation_mvp.py
```

**预期输出**:
```
🚀 MVP 反向反馈机制 - 完整测试套件
==================================================

🧪 测试 1: 基础 Recommendation 功能
==================================================
📝 添加 Recommendation...
🔥 Added recommendation: prioritize_features (Priority: 9)
🔍 获取 Recommendation...
✅ 找到 1 条建议:
   1. prioritize_features: ['HEX', 'MIN', 'aggregate'] (优先级: 9)
      原因: tlp_violation: TLP_violation
✅ 测试 1 通过！

🧪 测试 2: Prompt 增强功能
==================================================
...

✅ 所有测试通过！MVP 反向反馈机制验证成功！
```

### 3.2 如果测试失败

**常见问题**:

1. **Qdrant 连接失败**:
   ```bash
   # 检查 Qdrant 状态
   docker ps | grep qdrant
   
   # 重启 Qdrant
   docker restart <qdrant_container_id>
   ```

2. **导入错误**:
   ```bash
   # 检查 Python 路径
   python -c "import sys; print('\n'.join(sys.path))"
   
   # 确保项目根目录在 PYTHONPATH
   export PYTHONPATH=/root/QTRAN:$PYTHONPATH
   ```

3. **Mem0 未安装**:
   ```bash
   pip install mem0ai
   ```

---

## 🚀 第4步: 真实环境测试

### 4.1 启用 Mem0 并运行翻译任务

```bash
cd /root/QTRAN

# 启用 Mem0
export QTRAN_USE_MEM0=true
export QTRAN_MEM0_MODE=balanced

# 运行 SQLancer 翻译（示例）
python -m src.TransferLLM.translate_sqlancer \
    --input-file data/sqlancer/sqlite_test.sql \
    --origin-db sqlite \
    --target-db mongodb \
    --molt tlp \
    --output-dir Output/test_recommendation
```

### 4.2 观察反馈机制

在运行过程中，注意观察以下输出：

**1. Recommendation 生成**:
```
🔥 Generated recommendation: prioritize HEX, MIN, aggregate (Priority: 9)
```

**2. Recommendation 使用**:
```
🔥 HIGH PRIORITY RECOMMENDATIONS (from mutation feedback):
============================================================

1. **prioritize_features** (Priority: 9/10)
   - Focus on: HEX, MIN, aggregate
   - Reason: tlp_violation: TLP_violation
```

**3. 翻译改进**:
- 后续翻译应该更多包含推荐的特性
- Bug 发现率应该提升

---

## 📊 验证效果

### 方法 1: 日志分析

```bash
# 统计 Recommendation 生成次数
grep "Generated recommendation" Output/test_recommendation/*.log | wc -l

# 查看生成的特性
grep "Generated recommendation" Output/test_recommendation/*.log
```

### 方法 2: A/B 对比测试

运行两组测试进行对比：

**对照组** (无 Recommendation):
```bash
export QTRAN_USE_MEM0=false
python -m src.TransferLLM.translate_sqlancer \
    --output-dir Output/control_group
```

**实验组** (有 Recommendation):
```bash
export QTRAN_USE_MEM0=true
python -m src.TransferLLM.translate_sqlancer \
    --output-dir Output/experiment_group
```

**对比指标**:
- Bug 发现数量
- 覆盖率增长速度
- 翻译首次成功率

---

## 🎯 预期效果

### 短期效果（1-2周）

| 指标 | 当前基线 | 预期提升 |
|------|---------|---------|
| 高价值特性命中率 | 随机 (~20%) | **+30-40%** (→ 50-60%) |
| TLP violation 重现率 | 低 (~10%) | **+50%** (→ 15%) |
| Bug 发现速度 | 基线 | **+20%** |

### 观察要点

1. **Recommendation 生成频率**: 每 5-10 个翻译任务应该生成 1-2 个 Recommendation
2. **Recommendation 采纳率**: 70%+ 的 Recommendation 应该被后续翻译使用
3. **特性聚焦**: 高价值特性（如 HEX + MIN）应该在后续翻译中出现更频繁

---

## 🐛 故障排查

### 问题 1: Recommendation 没有生成

**原因**: Oracle 检查没有发现问题

**解决**:
1. 检查 `oracle_check_res["end"]` 的值
2. 确认 `use_mem0` 为 `True`
3. 查看日志中是否有 Oracle violation

### 问题 2: Recommendation 没有被使用

**原因**: 优先级过低或数据库对不匹配

**解决**:
1. 降低 `min_priority` (在 `get_recommendations` 中)
2. 检查 `origin_db` 和 `target_db` 是否匹配
3. 查看 Mem0 中是否有对应的记忆

### 问题 3: 性能下降

**原因**: 每次都检索 Recommendation 增加了延迟

**解决**:
1. 设置环境变量 `QTRAN_MEM0_MODE=fast` (减少检索)
2. 降低 `limit` 参数（减少返回数量）
3. 添加缓存机制（高级优化）

---

## 📈 后续优化方向

### 优化 1: 智能优先级计算

```python
def calculate_priority(bug_type, historical_rate, rarity):
    """基于多因素动态计算优先级"""
    # 实现复杂的优先级算法
    pass
```

### 优化 2: 有效性反馈

```python
def update_effectiveness(recommendation_id, outcome):
    """记录 Recommendation 的实际效果"""
    # 用于未来的优先级调整
    pass
```

### 优化 3: 过期机制

```python
def expire_old_recommendations(days=7):
    """清理过期的 Recommendation"""
    # 避免 Mem0 积累过多旧建议
    pass
```

---

## ✅ 实施检查清单

- [ ] `mem0_adapter.py` 添加了 3 个新方法
- [ ] `mem0_adapter.py` 修改了 `build_enhanced_prompt`
- [ ] `translate_sqlancer.py` 添加了 2 个辅助函数
- [ ] `translate_sqlancer.py` 在 Oracle 检查后调用生成函数
- [ ] 测试脚本运行通过 (5/5 测试)
- [ ] Qdrant 正常运行
- [ ] 真实翻译任务生成了 Recommendation
- [ ] 后续翻译使用了 Recommendation
- [ ] 观察到 Bug 发现率提升

---

## 📚 相关文档

- [完整设计文档](./MVP_反向反馈机制实现方案.md)
- [系统对比分析](../research/重要/当前系统_vs_DCFF设计对比.md)
- [研究建议](../research/重要/研究建议.md)

---

## 💬 需要帮助？

如果遇到问题，请检查：

1. **日志输出**: 查看 `print` 输出的错误信息
2. **Mem0 状态**: 确认 Qdrant 正常运行
3. **代码位置**: 确认修改在正确的位置
4. **环境变量**: 确认 `QTRAN_USE_MEM0=true`

---

**最后更新**: 2025-10-25  
**预计收益**: Bug 发现率 +20-30%，代码量 ~150 行  
**风险等级**: 低（可通过环境变量禁用）

