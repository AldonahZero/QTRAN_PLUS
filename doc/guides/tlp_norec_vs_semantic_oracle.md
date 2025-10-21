# MongoDB 的 SQLancer 风格 Oracle 设计

## 📖 背景: SQLancer 的核心思想

SQLancer 是一个自动化数据库测试工具,通过 **逻辑等价性验证** 来发现数据库逻辑Bug。它不依赖预先定义的测试用例,而是通过以下两种核心技术:

### 1. TLP (Ternary Logic Partitioning) - 三值逻辑分区

**核心思想**: 将查询结果集按照一个谓词 P 分成三个互斥且完备的子集:
- **R_true**: P 为真的行
- **R_false**: P 为假的行  
- **R_null**: P 为 NULL 的行

**不变式**: `R = R_true ∪ R_false ∪ R_null`

如果这个不变式被违反,说明数据库存在逻辑Bug。

### 2. NoREC (Non-optimizing Reference Engine Construction) - 非优化参考引擎

**核心思想**: 对比优化查询 vs 非优化查询的结果:
- **Q_opt**: 使用数据库优化器的查询
- **Q_ref**: 手动构造的等价查询(绕过优化)

**不变式**: `Results(Q_opt) = Results(Q_ref)`

如果结果不一致,说明查询优化器存在Bug。

---

## 🎯 为什么这两种方法更好?

与我之前设计的 semantic oracle (基于操作后置条件验证)相比,TLP 和 NoREC 有以下优势:

| 特性 | Semantic Oracle | TLP/NoREC |
|------|----------------|-----------|
| **Bug 类型** | 单个操作的语义错误 | 逻辑一致性错误 |
| **依赖** | 需要理解操作语义 | 只需要逻辑等价性 |
| **假阳性** | 高(Oracle 实现错误) | 低(数学证明的不变式) |
| **覆盖率** | 操作级别 | 查询组合级别 |
| **可扩展性** | 需要为每个操作定义 Oracle | 自动生成分区/等价查询 |
| **SQLancer 兼容** | ❌ 不兼容 | ✅ 完全兼容 |

**关键区别**: 
- Semantic Oracle: "deleteOne 后文档数应该减1" ← 这是**操作语义**
- TLP: "查询结果 = P为真的结果 ∪ P为假的结果 ∪ P为NULL的结果" ← 这是**逻辑不变式**

---

## 🔍 TLP 在 MongoDB 中的应用

### 原理

给定一个 MongoDB 查询:
```javascript
Q: find({status: "active"})
```

选择一个分区谓词 P (例如: `score >= 100`),生成三个分区查询:

```javascript
Q_true:  find({status: "active", score: {$gte: 100}})
Q_false: find({status: "active", score: {$lt: 100}})
Q_null:  find({status: "active", score: {$exists: false}})
```

**TLP 不变式验证**:
```python
count(Q) == count(Q_true) + count(Q_false) + count(Q_null)
```

### 为什么这能找到Bug?

**场景 1: 三值逻辑处理错误**
```javascript
// Bug: MongoDB 错误处理了 NULL 值
Q: find({age: {$gte: 18}})  // 返回 100 个文档

Q_true: find({age: {$gte: 18}, name: {$type: "string"}})  // 60 个
Q_false: find({age: {$gte: 18}, name: {$not: {$type: "string"}}, name: {$exists: true}})  // 30 个
Q_null: find({age: {$gte: 18}, name: {$exists: false}})  // 5 个

// 60 + 30 + 5 = 95 ≠ 100 → Bug Found!
// 原因: 5 个文档的 name 字段被错误处理
```

**场景 2: 过滤器组合错误**
```javascript
// Bug: $and 操作符与 $exists 组合有问题
Q: find({$and: [{type: "order"}, {items: {$exists: true}}]})  // 50 个

Q_true: find({$and: [{type: "order"}, {items: {$exists: true}}, {discount: {$gte: 0}}]})  // 30 个
Q_false: find({$and: [{type: "order"}, {items: {$exists: true}}, {discount: {$lt: 0}}]})  // 15 个
Q_null: find({$and: [{type: "order"}, {items: {$exists: true}}, {discount: {$exists: false}}]})  // 10 个

// 30 + 15 + 10 = 55 ≠ 50 → Bug Found!
// 原因: 某些文档被重复计数或漏计
```

### TLP Prompt 设计要点

1. **自动选择分区谓词**: 
   - 从原查询中未使用的字段中选择
   - 优先选择可能产生 NULL 的字段(可选字段)
   
2. **保证分区互斥且完备**:
   - P_true: P 为真
   - P_false: P 为假 **且** 字段存在
   - P_null: 字段不存在
   
3. **生成可执行的 MongoDB 查询**:
   - 使用 `$exists`, `$type`, `$not` 等操作符
   - 保持原查询的其他条件不变

---

## 🔧 NoREC 在 MongoDB 中的应用

### 原理

给定一个可能被优化的查询:
```javascript
Q_opt: find({category: "books", price: {$lt: 50}}).hint({category: 1, price: 1})
```

构造绕过优化的等价查询:
```javascript
Q_ref1: find({category: "books", price: {$lt: 50}}).hint({$natural: 1})  // 强制全表扫描
Q_ref2: aggregate([{$match: {category: "books", price: {$lt: 50}}}])  // 不同执行路径
```

**NoREC 不变式验证**:
```python
Results(Q_opt) == Results(Q_ref1) == Results(Q_ref2)
```

### 为什么这能找到Bug?

**场景 1: 索引选择错误**
```javascript
// Bug: 复合索引优化器选择了错误的索引前缀
Q_opt: find({category: "electronics", price: {$gte: 100}, stock: {$gt: 0}})
       .hint({category: 1, price: 1, stock: 1})
// 返回 50 个文档

Q_ref: find({category: "electronics", price: {$gte: 100}, stock: {$gt: 0}})
       .hint({$natural: 1})
// 返回 55 个文档

// 50 ≠ 55 → Optimizer Bug Found!
// 原因: 索引扫描漏掉了某些边界情况的文档
```

**场景 2: 聚合管道优化错误**
```javascript
// Bug: $match + $sort 管道优化重排序有问题
Q_opt: aggregate([
  {$match: {status: "active"}},
  {$sort: {date: -1}},
  {$limit: 10}
])
// 返回 10 个文档,但日期顺序错误

Q_ref: find({status: "active"}).sort({date: -1}).limit(10)
// 返回 10 个文档,日期顺序正确

// 虽然文档数相同,但顺序不同 → Pipeline Optimization Bug!
```

**场景 3: 覆盖索引(Covered Query)错误**
```javascript
// Bug: 覆盖索引查询返回了错误的值
Q_opt: find({category: "toys"}, {projection: {name: 1, price: 1}})
       .hint({category: 1, name: 1, price: 1})  // 覆盖索引
// 某个文档返回: {name: "Ball", price: 15}

Q_ref: find({category: "toys"})  // 全文档扫描
// 同一文档返回: {name: "Ball", price: 20}

// 投影值不一致 → Covered Index Bug!
```

### NoREC Prompt 设计要点

1. **识别优化点**:
   - 索引提示 (hint)
   - 聚合管道
   - 投影优化
   - 排序优化
   
2. **构造等价参考查询**:
   - 使用 `hint: {$natural: 1}` 强制全表扫描
   - 用 `find` 替代 `aggregate`(或反之)
   - 移除投影,返回完整文档
   
3. **多个参考变体**:
   - 至少生成 2 个不同的参考查询
   - 使用不同的执行路径(索引 vs 全表扫描 vs 聚合)

---

## 📊 TLP vs NoREC 对比

| 维度 | TLP | NoREC |
|------|-----|-------|
| **目标** | 查询逻辑一致性 | 查询优化正确性 |
| **测试内容** | 过滤器逻辑、三值逻辑 | 索引选择、执行计划 |
| **变异数量** | 4 个(原查询 + 3个分区) | 4-5 个(优化查询 + 2-3个参考 + 计数) |
| **Bug 类型** | 逻辑错误、NULL处理 | 优化器错误、索引Bug |
| **计算开销** | 中等(4次查询) | 高(多次查询,可能全表扫描) |
| **适用场景** | 复杂过滤器、逻辑操作符 | 索引查询、聚合管道 |

**互补性**: 
- TLP 找逻辑Bug (WHERE 子句)
- NoREC 找性能优化Bug (执行计划)

---

## 🎓 与 Semantic Oracle 的对比

### 我之前设计的 Semantic Oracle (错误示范)

```json
{
  "cmd": "deleteOne({_id: 'temp'})",
  "oracle": "cardinality_minus_one"
}
```

**问题**:
1. ❌ 需要人工实现 `cardinality_minus_one` 的检查逻辑
2. ❌ 容易出现 Oracle 实现错误(就像你看到的误报)
3. ❌ 只测试单个操作,不测试查询组合
4. ❌ 与 SQLancer 设计理念不符

### 正确的 TLP Oracle

```json
{
  "mutations": [
    {"cmd": "find({})", "oracle": "tlp_base"},
    {"cmd": "find({type: {$type: 'string'}})", "oracle": "tlp_partition"},
    {"cmd": "find({type: {$not: {$type: 'string'}}, type: {$exists: true}})", "oracle": "tlp_partition"},
    {"cmd": "find({type: {$exists: false}})", "oracle": "tlp_partition"}
  ]
}
```

**优势**:
1. ✅ Oracle 检查逻辑简单: `count(Q) == count(Q_true) + count(Q_false) + count(Q_null)`
2. ✅ 数学上可证明的不变式,不会误报(除非真有Bug)
3. ✅ 测试查询组合和三值逻辑
4. ✅ 与 SQLancer 完全兼容

---

## 🚀 实现建议

### 1. 修改 `MutateLLM.py` 支持 TLP/NoREC

```python
def select_mutation_prompt(molt, is_mongodb_target):
    if is_mongodb_target:
        if molt == "tlp":
            return "MutationData/MutationLLMPrompt/tlp_mongodb.json"
        elif molt == "norec":
            return "MutationData/MutationLLMPrompt/norec_mongodb.json"
        elif molt == "semantic":
            # 保留旧的语义oracle(用于对比实验)
            return "MutationData/MutationLLMPrompt/semantic_mongodb.json"
    # ... 其他逻辑
```

### 2. 实现 TLP Oracle 检查器

```python
def check_tlp_oracle(mutations_results):
    """
    验证 TLP 不变式: count(Q) == count(Q_true) + count(Q_false) + count(Q_null)
    """
    original = mutations_results[0]  # category: "original"
    p_true = mutations_results[1]    # category: "tlp_true"
    p_false = mutations_results[2]   # category: "tlp_false"
    p_null = mutations_results[3]    # category: "tlp_null"
    
    count_original = len(original["value"]) if isinstance(original["value"], list) else 1
    count_partitions = (
        len(p_true["value"]) + 
        len(p_false["value"]) + 
        len(p_null["value"])
    )
    
    if count_original != count_partitions:
        return {
            "end": False,
            "error": None,
            "bug_type": "TLP_violation",
            "details": {
                "original_count": count_original,
                "partition_sum": count_partitions,
                "difference": count_original - count_partitions
            }
        }
    
    # 检查分区是否互斥
    ids_true = {doc["_id"] for doc in p_true["value"]}
    ids_false = {doc["_id"] for doc in p_false["value"]}
    ids_null = {doc["_id"] for doc in p_null["value"]}
    
    overlap = (ids_true & ids_false) | (ids_true & ids_null) | (ids_false & ids_null)
    if overlap:
        return {
            "end": False,
            "error": None,
            "bug_type": "partition_overlap",
            "details": {
                "overlapping_ids": list(overlap)
            }
        }
    
    return {"end": True, "error": None}
```

### 3. 实现 NoREC Oracle 检查器

```python
def check_norec_oracle(mutations_results):
    """
    验证 NoREC 不变式: Results(Q_opt) == Results(Q_ref)
    """
    optimized = mutations_results[0]  # category: "optimized"
    reference = mutations_results[1]  # category: "reference"
    count_check = mutations_results[-1]  # category: "count_check"
    
    # 结果集比较(不考虑顺序,除非有排序)
    ids_opt = sorted([doc["_id"] for doc in optimized["value"]])
    ids_ref = sorted([doc["_id"] for doc in reference["value"]])
    
    if ids_opt != ids_ref:
        return {
            "end": False,
            "error": None,
            "bug_type": "optimizer_bug",
            "details": {
                "optimized_count": len(ids_opt),
                "reference_count": len(ids_ref),
                "missing_in_opt": list(set(ids_ref) - set(ids_opt)),
                "extra_in_opt": list(set(ids_opt) - set(ids_ref))
            }
        }
    
    # 计数一致性检查
    if len(ids_opt) != count_check["value"]:
        return {
            "end": False,
            "error": None,
            "bug_type": "count_inconsistency",
            "details": {
                "result_count": len(ids_opt),
                "countDocuments_result": count_check["value"]
            }
        }
    
    return {"end": True, "error": None}
```

### 4. 更新 `translate_sqlancer.py` Oracle 分发

```python
def run_oracle_check(mutations_results, oracle_type):
    if oracle_type == "tlp_partition":
        return check_tlp_oracle(mutations_results)
    elif oracle_type == "norec_ref":
        return check_norec_oracle(mutations_results)
    elif oracle_type.startswith("semantic_"):
        # 旧的语义oracle(逐步废弃)
        return check_semantic_oracle(mutations_results, oracle_type)
    else:
        return {"end": False, "error": f"Unknown oracle type: {oracle_type}"}
```

---

## 📈 预期效果

### 使用 TLP/NoREC 后:

1. **更少的误报**:
   - TLP: 数学证明的不变式,几乎无误报
   - NoREC: 等价查询对比,误报率低
   
2. **更深的Bug检测**:
   - TLP: 发现三值逻辑处理错误、过滤器组合Bug
   - NoREC: 发现索引选择错误、查询优化Bug
   
3. **更好的 SQLancer 兼容性**:
   - 可以直接对比与原始 SQLancer 的Bug发现率
   - 论文中可以引用 SQLancer 的理论基础

4. **更清晰的Bug报告**:
   ```json
   {
     "bug_type": "TLP_violation",
     "details": {
       "original_count": 100,
       "partition_sum": 95,
       "difference": 5,
       "explanation": "5 documents lost in partitioning - likely NULL handling bug"
     }
   }
   ```

---

## 🎯 总结

| 方面 | Semantic Oracle (旧) | TLP/NoREC (新) |
|------|---------------------|----------------|
| **理论基础** | 操作后置条件 | 逻辑等价性不变式 |
| **SQLancer 兼容** | ❌ | ✅ |
| **误报率** | 高(如你遇到的问题) | 极低 |
| **Bug 类型** | 操作语义错误 | 逻辑一致性 + 优化错误 |
| **实现复杂度** | 高(每个oracle需要专门实现) | 低(统一的检查逻辑) |
| **可扩展性** | 低 | 高 |
| **论文价值** | 一般 | 高(与SQLancer直接对比) |

**建议**: 
1. 使用 `tlp_mongodb.json` 和 `norec_mongodb.json` 替代 `semantic_mongodb.json`
2. 保留 semantic 作为对比实验组
3. 在论文中强调:"我们将 SQLancer 的 TLP/NoREC 方法首次应用于 NoSQL 数据库测试"

这样才是真正符合 SQLancer 思想的设计! 🎯
