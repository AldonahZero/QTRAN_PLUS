# Redis / Memcached / etcd / Consul / MongoDB 返回结果结构差异速览（Redis=100% 基准）

目标：以 **Redis 作为 100% 参考基准**（基于“命令粒度交互模型 + 返回值简洁度 + 数据结构多样性 + 非 JSON 原生”四个维度），量化其它 KV / 文档系统在“结果结构风格”上的相似度，并给出统一抽象建议。

相似度评分说明（主观工程向打分）：
- 维度：
  1. 交互模型：命令式（RESP / 文本） vs API / JSON 文档式
  2. 返回结构：是否多为纯标量 / 简单列表（而非富元数据对象）
  3. 数据结构多样性：是否只支持扁平 KV（多结构越少越不似 Redis）
  4. 元数据噪声：返回是否夹带版本 / 修订 / 索引 / BSON ID 等
- 总分：各维度权 25%，四维加权后四舍五入
- Redis 作为 100%，其余相对化

---

## 1. 类型定位与相似度量化

| 系统 | 类型定位 | 数据模型核心 | 元数据丰富度 | 典型返回是否含版本/事务信息 | 与 Redis 相似度 (=Redis 100%) | 说明摘要 |
|------|----------|--------------|--------------|----------------------------|-------------------------------|----------|
| Redis | 内存多结构 KV | 多结构 (String/Hash/List/Set/ZSet/Stream ...) | 低 | 否 | 100% | 基准 |
| Memcached | 纯缓存 KV | key→bytes (仅 String 语义) | 极低 | 否 | 85% | 命令式/简单返回，高度相似但无多结构 |
| etcd | 一致性 KV (Raft) | 版本化 KV（revision/version/lease） | 高 | 是 | 40% | JSON + 元数据重 + 无多结构 |
| Consul KV | 服务发现附带 KV | 分层 key，索引/Flags | 中 | 是 | 45% | JSON 数组 + 索引字段；与 Redis 仅在“值是字符串”层面接近 |
| MongoDB | 文档数据库 | 集合→文档(BSON) | 高 | 可（_id/ack 等） | 20% | 文档/查询范式差异大 |

> 评分粗粒度用于工程策略（是否可直接套用 Redis 归一化逻辑）。Memcached ≫ etcd ≈ Consul ≫ MongoDB。

---

## 2. 原生典型操作与原始返回（保持与之前一致，未改）

### Redis
| 类别 | 示例 | 原始返回 |
|------|------|----------|
| 写 | SET k v | OK / True |
| 读 | GET k | v 或 (nil) |
| 结构 | ZADD k s m | 新增成员数(int) |
| 结构读 | ZRANGE k 0 -1 WITHSCORES | 成员/分数列表 |
| 元操作 | INCR k | 新值(int) |

### Memcached
| 类别 | 示例 | 原始返回 |
|------|------|----------|
| 写 | set k v 0 300 | STORED / NOT_STORED |
| 读 | get k | VALUE 块 + END |
| 条件写 | cas k v cas_token | STORED / EXISTS / NOT_FOUND |
| 删除 | delete k | DELETED / NOT_FOUND |

### etcd (v3)
| 类别 | 示例 | 返回关键字段 |
|------|------|--------------|
| 写 | Put(k,v) | header.revision, prev_kv |
| 读 | Range(k) | kvs[{key,value,version,mod_revision,...}], count |
| 删 | DeleteRange | deleted, header.revision |
| 事务 | Txn | succeeded, responses[], header.revision |
| Watch | Watch | events[], revision |

### Consul KV
| 类别 | 示例 | 返回 |
|------|------|------|
| 写 | PUT /v1/kv/k | true/false |
| 读 | GET /v1/kv/k | [{"Key","Value(base64)","CreateIndex","ModifyIndex","Flags"}] |
| 递归读 | GET /v1/kv/prefix?recurse | 多条同结构 |
| 删 | DELETE /v1/kv/k | true/false |

### MongoDB
| 类别 | 示例 | 核心结果 |
|------|------|----------|
| insertOne | doc | inserted_id |
| updateOne | filter+update | matched_count / modified_count / upserted_id |
| findOne | filter | 文档或 None |
| find | filter | 多文档迭代 |
| deleteOne | filter | deleted_count |

---

## 3. 统一抽象（QTRAN 标准化 Result）

```json
{
  "type": "<op_type>",
  "success": true,
  "value": "... / list / object / null",
  "meta": {
    "raw_code": "OK|STORED|...",
    "version": 3,
    "revision": 1052,
    "indices": {"CreateIndex":10,"ModifyIndex":15},
    "cas": 12345,
    "flags": 0,
    "lease": 7654321,
    "count": 2,
    "inserted_id": "mykey",
    "upserted_id": "..."
  }
}
```
缺省字段不出现。

### 3.1 op_type 分类
| op_type | 适用 | 说明 |
|---------|------|------|
| kv_set | Redis / Memcached / etcd / Consul | 普通键写 |
| kv_get | 同上 | 单键读 |
| kv_range | etcd / Consul (前缀) | 多键 |
| kv_delete | All KV | 删除 |
| structure_write | Redis (ZADD/HSET/...) | 结构类写 |
| structure_read | Redis (ZRANGE/HGETALL/...) | 结构类读 |
| doc_insert | MongoDB | insertOne |
| doc_update | MongoDB | updateOne |
| doc_find_one | MongoDB | findOne |
| doc_find | MongoDB | find 多文档 |
| txn | etcd | 事务 |
| unsupported | 任意 | 暂未映射 |

---

## 4. 相似度差异解读（为何这些分值）

| 系统 | 关键差异导致扣分项 |
|------|--------------------|
| Memcached | -15%：无多结构（Redis 特征）+ 文本协议值返回格式不同 |
| etcd | -60%：JSON 元数据臃肿 + 事务/版本语义显性 + 无多结构 |
| Consul | -55%：JSON 数组 + 索引/Flags + Base64 必须解码 |
| MongoDB | -80%：文档模型 + 查询/更新操作语义不同 + BSON ID/结果结构层级化 |

---

## 5. 归一化策略与是否直接复用 Redis 逻辑

| 系统 | 可直接复用 Redis 标量归一逻辑 | 是否需额外解码/裁剪 | 建议 |
|------|-------------------------------|---------------------|------|
| Memcached | 是（简化后） | 需解析 VALUE 块 | 轻适配包装 |
| etcd | 否 | Base64 / revision 过滤 | 独立 normalizer |
| Consul | 否 | Base64 / 索引裁剪 | 独立 normalizer |
| MongoDB | 否 | 文档裁剪/字段挑选 | 独立 normalizer |

---

## 6. 等价比较建议（结合相似度）

| 场景 | Redis ↔ Memcached | Redis ↔ etcd | Redis ↔ Consul | Redis ↔ MongoDB |
|------|-------------------|--------------|----------------|-----------------|
| kv_get 简单值 | 可直接 value 比较 | 需解码 + 忽略 meta | 需解码 + 忽略索引 | 需映射到 doc.value |
| kv_set / 写 | 统一 success | success | success | success（剥离 inserted_id） |
| 结构(ZSET/HASH) | Redis 专属 | 模拟成本高（前缀 + 客户端排序） | 不适合 | 需映射到集合文档（评分低） |
| 随机/非确定 | skip | skip | skip | skip |

---

## 7. 示例归一化（含 redis 基准对齐）

Redis GET →  
```
{"type":"kv_get","success":true,"value":"hello"}
```
Memcached get →  
```
{"type":"kv_get","success":true,"value":"hello"}
```
etcd Range(k) →  
```
{"type":"kv_get","success":true,"value":"hello"}
```
Consul GET →  
```
{"type":"kv_get","success":true,"value":"hello"}
```
MongoDB findOne ({"_id":"mykey","value":"hello"}) →  
```
{"type":"kv_get","success":true,"value":"hello"}
```

> 通过裁剪与字段提取实现跨系统“值层面”对齐；多余 meta 进入 meta，不参与相等性判定。

---

## 8. 后续待办
- [ ] normalize_memcached_result
- [ ] normalize_etcd_result
- [ ] normalize_consul_result
- [ ] normalize_mongodb_result（已有局部，需统一签名）
- [ ] Equality：三态 true/false/null + reason
- [ ] 结构型与文档型隔离统计

---

## 9. 快速 FAQ

| 问题 | 答案 |
|------|------|
| 为什么 Memcached 不是 90%+？ | 缺失 Redis 多数据结构特征 |
| etcd/Consul 为什么接近？ | 都有 JSON+元数据；Consul 稍简，故 45% vs 40% |
| MongoDB 为什么仅 20%？ | 数据模型、返回形态、操作粒度全面不同 |
| 这些分值会用于阈值吗？ | 可用于决定是否启用“直接比较”或“深度映射” |
| 结构型操作能跨 KV 对比吗？ | 不能，需单独策略或放弃比较 |

---

（完）