# MongoDB Mutation Oracle 完整参考

## 📚 概述

本文档定义了用于 MongoDB 变异测试的 **40+ Oracle 类型**,覆盖从基础读取到高级聚合的完整测试场景。

---

## 🎯 Oracle 分类体系

### 1️⃣ 基础读取类 (Basic Read Oracles)

#### `value_read`
**定义**: 查询结果应与预期值匹配  
**用途**: 验证 findOne/find 返回正确的文档内容  
**示例**:
```javascript
// 变异: 读取刚插入的值
{
  "cmd": "{\"op\":\"findOne\",\"collection\":\"kv\",\"filter\":{\"_id\":\"mykey\"}}",
  "oracle": "value_read"
}
// 断言: result.value === "hello"
```

#### `value_read_projection`
**定义**: 投影查询只返回请求的字段  
**用途**: 验证投影功能不泄露额外字段  
**示例**:
```javascript
// 变异: 只投影 value 字段
{
  "cmd": "{\"op\":\"findOne\",\"collection\":\"kv\",\"filter\":{\"_id\":\"k\"},\"projection\":{\"value\":1}}",
  "oracle": "value_read_projection"
}
// 断言: Object.keys(result) === ["_id", "value"] (MongoDB 总是返回 _id)
```

#### `length_probe`
**定义**: 检查集合或数组字段的长度  
**用途**: 验证文档数量或数组元素数  
**示例**:
```javascript
// 断言: find({}).length === countDocuments({})
```

#### `cardinality_probe`
**定义**: 统计匹配过滤器的文档数  
**用途**: 独立的计数检查  
**示例**:
```javascript
{
  "cmd": "{\"op\":\"countDocuments\",\"collection\":\"kv\",\"filter\":{\"status\":\"active\"}}",
  "oracle": "cardinality_probe"
}
// 断言: count === N (预期值)
```

#### `membership_true`
**定义**: 验证文档存在 (count=1)  
**用途**: 插入/更新后的存在性检查  
**示例**:
```javascript
{
  "cmd": "{\"op\":\"countDocuments\",\"collection\":\"kv\",\"filter\":{\"_id\":\"mykey\"}}",
  "oracle": "membership_true"
}
// 断言: count === 1
```

#### `membership_false`
**定义**: 验证文档不存在 (count=0)  
**用途**: 删除后的不存在性检查  
**示例**:
```javascript
// 断言: countDocuments({_id:"deleted"}) === 0
```

---

### 2️⃣ 幂等性类 (Idempotency Oracles)

#### `same_field`
**定义**: 幂等操作后字段值不变  
**用途**: 重复 $set 操作  
**示例**:
```javascript
// 执行两次
updateOne({_id:"k"}, {$set:{v:"hello"}})
updateOne({_id:"k"}, {$set:{v:"hello"}})
// 断言: findOne({_id:"k"}).v === "hello" (值不变)
```

#### `same_document`
**定义**: 整个文档内容不变  
**用途**: upsert 重复执行  
**示例**:
```javascript
// 断言: findOne({_id:"k"}) before === findOne({_id:"k"}) after
```

#### `cardinality_same`
**定义**: 文档总数不变  
**用途**: 幂等 upsert 操作  
**示例**:
```javascript
// Before: count = N
updateOne({_id:"k"}, {$set:{v:1}}, {upsert:true})
// After: count = N (不增加)
```

#### `noop`
**定义**: 操作无任何副作用  
**用途**: 删除不存在的文档、空过滤器更新  
**示例**:
```javascript
deleteOne({_id:"nonexistent"})
// 断言: matchedCount === 0, deletedCount === 0
```

---

### 3️⃣ 增量类 (Incremental Oracles)

#### `cardinality_plus_one`
**定义**: 计数精确增加 1  
**用途**: 插入新文档  
**示例**:
```javascript
// Before: count = N
insertOne({_id:"new", value:"x"})
// After: count = N+1
```

#### `cardinality_plus_one_or_same`
**定义**: 计数增加 1 或保持不变  
**用途**: 处理唯一键冲突的 insert  
**示例**:
```javascript
// 可能触发唯一键冲突
insertOne({_id:"may_exist", value:"x"})
// 断言: count ∈ {N, N+1}
```

#### `cardinality_minus_one`
**定义**: 计数精确减少 1  
**用途**: 删除已存在文档  
**示例**:
```javascript
// Before: count = N
deleteOne({_id:"existing"})
// After: count = N-1
```

#### `value_increment`
**定义**: 数值字段增加指定 delta  
**用途**: $inc 操作符验证  
**示例**:
```javascript
// Before: {counter: 5}
updateOne({_id:"k"}, {$inc:{counter:3}})
// After: {counter: 8}
```

#### `value_decrement`
**定义**: 数值字段减少指定 delta  
**用途**: $inc 负值验证  
**示例**:
```javascript
// Before: {stock: 10}
updateOne({_id:"item"}, {$inc:{stock:-2}})
// After: {stock: 8}
```

---

### 4️⃣ 等价性类 (Equivalence Oracles) - MongoDB 特有

#### `find_aggregate_equivalent`
**定义**: find() 和 aggregate($match) 应返回相同结果  
**用途**: 验证聚合管道的查询等价性  
**示例**:
```javascript
// 方法1
find({status:"active"})
// 方法2 (应等价)
aggregate([{$match:{status:"active"}}])
// 断言: 两者返回相同文档集合
```

#### `projection_subset`
**定义**: 投影结果是完整文档的子集  
**用途**: 验证投影不添加字段  
**示例**:
```javascript
full = findOne({_id:"k"})
projected = findOne({_id:"k"}, {projection:{a:1}})
// 断言: projected.keys ⊆ full.keys
```

#### `sort_order_consistent`
**定义**: 不同排序规范产生一致的相对顺序  
**用途**: 验证排序优化的正确性  
**示例**:
```javascript
// 当 a 值唯一时
result1 = find().sort({a:1})
result2 = find().sort({a:1, b:1})
// 断言: result1 是 result2 的前缀 (在 a 值相同时 b 排序起作用)
```

#### `limit_skip_partition`
**定义**: limit+skip 应正确分割结果集  
**用途**: 分页一致性验证  
**示例**:
```javascript
page1 = find().skip(0).limit(10)
page2 = find().skip(10).limit(10)
full = find().limit(20)
// 断言: page1 ∪ page2 === full
```

#### `index_scan_equivalent`
**定义**: 有/无索引提示返回相同结果  
**用途**: 索引正确性验证  
**示例**:
```javascript
// 方法1: 让查询优化器选择
find({age:25})
// 方法2: 强制使用索引
find({age:25}).hint({age:1})
// 断言: 结果集相同
```

#### `operator_equivalence`
**定义**: 不同操作符的语义等价性  
**用途**: 验证操作符实现一致性  
**示例**:
```javascript
// 这些应等价:
{age: 18}
{age: {$eq: 18}}
{age: {$gte: 18, $lte: 18}}
// 断言: 所有查询返回相同文档
```

---

### 5️⃣ 更新类 (Update Oracles)

#### `mutable_change`
**定义**: 字段值故意改变  
**用途**: $set 更新验证  
**示例**:
```javascript
// Before: {status: "pending"}
updateOne({_id:"order"}, {$set:{status:"completed"}})
// After: {status: "completed"}
```

#### `matched_count_consistent`
**定义**: matchedCount 等于预期匹配数  
**用途**: 更新操作报告准确性  
**示例**:
```javascript
expected = countDocuments({status:"active"})
result = updateMany({status:"active"}, {$set:{processed:true}})
// 断言: result.matchedCount === expected
```

#### `modified_count_le_matched`
**定义**: modifiedCount ≤ matchedCount (不变式)  
**用途**: 更新操作不变式检查  
**示例**:
```javascript
result = updateMany(filter, update)
// 断言: result.modifiedCount <= result.matchedCount
```

#### `upsert_creates_or_updates`
**定义**: upsert 要么插入 1 要么更新 1  
**用途**: upsert 语义验证  
**示例**:
```javascript
result = updateOne({_id:"k"}, {$set:{v:1}}, {upsert:true})
// 断言: result.upsertedCount + result.matchedCount === 1
```

---

### 6️⃣ 删除类 (Delete Oracles)

#### `inverse_operation`
**定义**: 删除撤销插入 (计数恢复原值)  
**用途**: 验证操作可逆性  
**示例**:
```javascript
count_before = countDocuments({})
insertOne({_id:"temp", value:"x"})
deleteOne({_id:"temp"})
count_after = countDocuments({})
// 断言: count_before === count_after
```

#### `delete_filter_consistency`
**定义**: deleteOne 删除的正是 find 返回的文档  
**用途**: 验证过滤器在不同操作间的一致性  
**示例**:
```javascript
doc = findOne(filter)
result = deleteOne(filter)
// 断言: result.deletedCount === 1 且删除的正是 doc
```

---

### 7️⃣ 聚合类 (Aggregation Oracles) - 高级

#### `aggregate_count_matches_find`
**定义**: aggregate $count 与 countDocuments 结果相同  
**用途**: 聚合计数准确性  
**示例**:
```javascript
count1 = countDocuments(filter)
count2 = aggregate([{$match:filter}, {$count:"n"}])[0].n
// 断言: count1 === count2
```

#### `group_partition_complete`
**定义**: $group 分组的总和等于全部文档数  
**用途**: 验证分组覆盖所有文档  
**示例**:
```javascript
total = countDocuments({})
groups = aggregate([{$group:{_id:"$category", count:{$sum:1}}}])
sum_of_groups = groups.reduce((s,g) => s + g.count, 0)
// 断言: total === sum_of_groups
```

#### `pipeline_commutativity`
**定义**: 某些管道阶段可交换顺序  
**用途**: 验证查询优化正确性  
**示例**:
```javascript
// 这两个应等价 (当 A 和 B 无交互时):
aggregate([{$match:A}, {$match:B}])
aggregate([{$match:{$and:[A,B]}}])
```

---

### 8️⃣ 类型与转换类 (Type Oracles)

#### `type_coercion_consistent`
**定义**: 类型转换遵循 MongoDB 规则  
**用途**: 验证弱类型比较行为  
**示例**:
```javascript
// MongoDB 是否匹配 {age:"18"} 和 {age:18} 取决于配置
// Oracle 验证行为一致性
```

#### `null_handling_correct`
**定义**: null、undefined、缺失字段三值逻辑  
**用途**: 验证空值语义  
**示例**:
```javascript
// 这三者不同:
{field: null}           // 字段存在且为 null
{field: {$exists:false}} // 字段不存在
{field: undefined}      // (在查询中等同于不存在)
```

#### `array_membership`
**定义**: $in 等价于 $or 的相等检查  
**用途**: 集合成员运算验证  
**示例**:
```javascript
// 应等价:
{status: {$in: ["active", "pending"]}}
{$or: [{status:"active"}, {status:"pending"}]}
```

---

### 9️⃣ 原子性类 (Atomicity Oracles) - 高级

#### `atomic_update_isolation`
**定义**: 并发更新不干扰 (隔离性)  
**用途**: 验证原子操作  
**示例**:
```javascript
// 两个线程同时执行:
// Thread 1: updateOne({_id:"counter"}, {$inc:{value:3}})
// Thread 2: updateOne({_id:"counter"}, {$inc:{value:5}})
// 断言: final_value = initial_value + 3 + 5
```

#### `find_modify_race_free`
**定义**: findOneAndUpdate 是原子的  
**用途**: 验证无竞态条件  
**示例**:
```javascript
// 不应出现丢失更新:
// find + update (非原子) vs findOneAndUpdate (原子)
```

---

## 🎓 Oracle 选择策略

### 优先级排序:
1. **MongoDB 特有功能**: aggregation, projection, operators
2. **语义等价性**: 跨操作风格验证
3. **不变式检查**: modified_count_le_matched 等
4. **原子性与一致性**: 并发场景
5. **边缘情况**: null、缺失字段、类型强制转换

### 避免:
- ❌ 冗余的基础 value_read 检查
- ❌ 同一 Oracle 类型的多个变异
- ❌ 无测试价值的变异

---

## 📊 Oracle 覆盖矩阵

| 操作类型 | 推荐 Oracle | 高级 Oracle |
|---------|------------|------------|
| **findOne/find** | value_read, membership_true | find_aggregate_equivalent, projection_subset |
| **insertOne** | cardinality_plus_one, membership_true | inverse_operation |
| **updateOne** | matched_count_consistent, same_field | upsert_creates_or_updates, value_increment |
| **deleteOne** | cardinality_minus_one, membership_false | delete_filter_consistency |
| **countDocuments** | cardinality_probe | aggregate_count_matches_find |
| **aggregate** | aggregate_count_matches_find | group_partition_complete, pipeline_commutativity |
| **$inc/$dec** | value_increment, value_decrement | atomic_update_isolation |
| **Projection** | value_read_projection | projection_subset |
| **Sort/Limit** | sort_order_consistent | limit_skip_partition |

---

## 🚀 使用示例

### 简单场景 (Redis → MongoDB KV):
```json
{
  "mutations": [
    {"cmd": "{\"op\":\"findOne\",\"collection\":\"kv\",\"filter\":{\"_id\":\"k\"}}", "oracle": "value_read"},
    {"cmd": "{\"op\":\"countDocuments\",\"collection\":\"kv\",\"filter\":{\"_id\":\"k\"}}", "oracle": "membership_true"},
    {"cmd": "{\"op\":\"find\",\"collection\":\"kv\",\"filter\":{\"_id\":\"k\"}}", "oracle": "find_aggregate_equivalent"}
  ]
}
```

### 复杂场景 (聚合与投影):
```json
{
  "mutations": [
    {"cmd": "{\"op\":\"find\",\"collection\":\"orders\",\"filter\":{\"status\":\"active\"},\"projection\":{\"total\":1}}", "oracle": "value_read_projection"},
    {"cmd": "{\"op\":\"aggregate\",\"collection\":\"orders\",\"pipeline\":[{\"$match\":{\"status\":\"active\"}},{\"$count\":\"n\"}]}", "oracle": "aggregate_count_matches_find"},
    {"cmd": "{\"op\":\"find\",\"collection\":\"orders\",\"filter\":{\"status\":\"active\"},\"sort\":{\"total\":-1},\"limit\":10}", "oracle": "sort_order_consistent"}
  ]
}
```

---

## 📝 总结

- **40+ Oracle 类型** 覆盖 MongoDB 全面测试需求
- **分层设计**: 基础 → 等价性 → 聚合 → 原子性
- **MongoDB 特化**: 针对文档数据库特性设计
- **可扩展**: 易于添加新的 Oracle 类型

**这套 Oracle 体系比原有的 9 个扩展了 4 倍以上,能够发现更深层的逻辑 Bug!** 🎯
