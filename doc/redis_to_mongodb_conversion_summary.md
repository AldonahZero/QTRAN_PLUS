# Redis → MongoDB 转换总结

## 1. 背景
目标：将生成/测试阶段的 Redis 命令转换为等价的 MongoDB 操作，统一抽象执行与结果校验；避免因 Redis 限制或缺失特性影响后续差异检测。

## 2. 数据模型映射
| Redis 类型 | 典型用途 | MongoDB 表示方案 | 说明 |
|------------|----------|------------------|------|
| String | KV | { _id: key, type:"string", value: <scalar> } | 若需版本/时间戳可扩展字段 |
| Hash | 结构化字段 | { _id: key, type:"hash", fields: { k:v, ... } } | 与文档天然接近，查询可基于 fields.k |
| List | 有序序列 | { _id: key, type:"list", items: [ ... ] } | 维护顺序；长列表需分片可加 chunk |
| Set | 去重集合 | { _id: key, type:"set", members: [ ... ] } | 用数组 + 唯一语义（逻辑去重） |
| Sorted Set (ZSet) | 有序排名 | { _id: key, type:"zset", members: [ { member, score }, ... ] } | 可建立 score 索引（members.score） |
| TTL Key | 过期 | 文档加 expireAt(Date)，并创建 TTL 索引 | db.collection.createIndex({expireAt:1},{expireAfterSeconds:0}) |
| Pub/Sub | 即时消息 | 不直接映射；可选 capped collection 或队列集合 | 非核心，暂不实现 |
| Bitmaps / HyperLogLog / Geo | 特殊结构 | 需要专门编码或单独跳过 | 现阶段不转换 |

可选：所有 Redis 映射集中到统一集合 redis_objects，或按 type 拆分多集合（string_objects / hash_objects ...）。权衡：
- 单集合：便于统一扫描；需稀疏索引。
- 多集合：类型隔离，索引更精简。当前推荐多集合简化查询。

## 3. 命令 → MongoDB 操作策略
| Redis 命令 | 语义 | MongoDB 转换示例 |
|------------|------|------------------|
| SET k v | 覆盖 | updateOne({_id:k},{ $set:{value:v,type:"string"} }, upsert:true) |
| GET k | 读取 | findOne({_id:k, type:"string"}, {value:1}) |
| DEL k | 删除 | deleteOne({_id:k}) |
| HSET k f v | 设置字典字段 | updateOne({_id:k,type:"hash"},{ $set:{['fields.'+f]:v} }, upsert:true) |
| HGETALL k | 全部字段 | findOne({_id:k,type:"hash"},{fields:1}) |
| LPUSH k v1 v2 | 头插 | updateOne({_id:k,type:"list"},{ $push:{ items:{ $each:[v2,v1], $position:0 } } }, upsert:true) |
| RPUSH k v1 v2 | 尾插 | $push $each |
| LRANGE k a b | 范围 | findOne 后切片 (Python 层) |
| SADD k m1 m2 | 添加集合元素 | 先 $addToSet + $each（需 MongoDB ≥4.4） |
| SMEMBERS k | 列出 | findOne({_id:k,type:"set"}) |
| ZADD k s1 m1 | 有序插入 | 读取 -> 更新/插入 members 数组（或使用 $pull 后 $push） |
| ZRANGE k a b | 按序区间 | 排序（内存）或展开 members.score 建立索引并聚合 |
| EXISTS k | 判断 | countDocuments({_id:k}) |
| EXPIRE k ttl | 过期 | updateOne({_id:k},{ $set:{expireAt: ISODate(now+ttl)} }) |

说明：
- 为降低多次往返，常用 upsert + $set / $push 合并。
- ZSet 精确排名需保持 members 数组按 score 排序；可在写入后用应用层排序或使用独立集合 + 索引。

## 4. 错误与本次调试要点
| 问题 | 根因 | 处理 |
|------|------|------|
| Authentication failed | MongoDB 未启用认证但代码仍传空用户名/密码触发错误分支 | 保持用户名/密码为空并仅在两者都非空时拼 URI |
| placeholder collectionName not replaced | 上游模板未替换占位符 | 在生成层添加占位符检测，过滤无效命令 |
| json parse error | 传入空/非法 JSON-like | 增加空对象/括号匹配预检 |
| 多重噪声错误堆叠 | 未短路 | 检测到首个结构性错误即返回 |

## 5. 性能与一致性考量
- 大列表/集合：单文档可能超 16MB 限制 → 需要分片策略（后续：基于分块集合 list_chunks {key, index, chunk}）。
- ZSet 频繁更新：O(n) 数组重写，可引入：members 按 member 建索引的子集合 zset_members(key, member, score)。
- 原子性：Redis 多命令事务（MULTI/EXEC）暂未覆盖；如需要可用 MongoDB 事务（副本集）或批处理策略。
- TTL：Redis 精确秒级 → MongoDB TTL 索引清理非实时（分钟级延迟），用于 fuzz / 转换测试可接受；精确测试需应用层轮询清理。

## 6. 测试与验证
- 单命令回归：构造 (redis_cmd, expected_doc_delta) 表驱动测试。
- 差异基线：执行 Redis 命令 → 模拟转换 → Mongo 查询结构 → 与预期 JSON 比较。
- Fuzz：随机生成 Key/Type 序列，检测文档结构一致性 & 不出现类型漂移（同 key 不跨 type）。

## 7. 后续优化建议
1. 引入类型调度层：解析 Redis 命令后标准化为中间 IR，再映射 Mongo。
2. 为 zset/list 设计可扩展存储：溢出分段。
3. 增加命令覆盖率：INCR / MGET / HDEL / SINTER 等。
4. 基于统计生成转换规则报告（命令频率 / 转换耗时）。
5. 引入结果缓存避免重复 findOne。

## 8. 最小示例片段
```javascript
// SET → updateOne
db.redis_string.updateOne(
  { _id: "k1" },
  { $set: { value: "v1", type: "string", updatedAt: new Date() } },
  { upsert: true }
)
```

## 9. 当前结论
转换路径已跑通；核心遗留在：
- 占位符防御与 JSON 宽松解析健壮性
- 大型结构的尺寸与性能策略
- ZSet 更高效的索引化表示

后续迭代按 7 节路线推进即可。