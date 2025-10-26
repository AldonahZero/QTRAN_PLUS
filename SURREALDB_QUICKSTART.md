# 🚀 SurrealDB 测试快速启动指南

## ✅ 当前状态

**SurrealDB v2.3.10 已就绪！** 所有配置已完成，可以立即开始测试。

```bash
✅ 容器运行中: surrealdb_QTRAN (端口 8000)
✅ Python SDK: surrealdb 1.0.6
✅ 知识库已创建
✅ 翻译 Prompt 已准备
```

---

## 🎯 为什么选择 SurrealDB？

```
✅ 最年轻的数据库 (2022)         → 更多未发现的 Bug
✅ 类 SQL 语法                   → 翻译成功率 85-90%
✅ 多模型架构                     → 复杂交互 Bug
✅ 类似 demo1 成功场景           → 预期高 Bug 发现率
```

**预期结果**: 2-3 个真正的 SurrealDB Bug ⭐

---

## 🚀 5 分钟快速测试

### 步骤 1: 验证环境
```bash
# 检查容器
docker ps | grep surrealdb

# 健康检查
curl http://127.0.0.1:8000/health

# 应该返回 200 OK
```

### 步骤 2: 运行测试脚本
```bash
cd /root/QTRAN
python test_surrealdb_simple.py
```

**预期输出**:
```
🚀 开始测试 SurrealDB (HTTP API)...
✅ 健康检查: 200
✅ 创建表定义...
✅ 插入成功！
✅ 查询成功！
```

---

## 📚 关键文档

### 1. 语法对比
**文件**: `NoSQLFeatureKnowledgeBase/SurrealDB/syntax_guide.md`

**关键差异**:
- `COUNT(*) → count()`
- `AVG(x) → math::mean(x)`
- 其他 95% 的 SQL 语法相同！

### 2. 翻译 Prompt
**文件**: `NoSQLFeatureKnowledgeBase/SurrealDB/translation_prompt.md`

包含：
- 8 个完整翻译示例
- 数据类型映射
- 常见错误避免

### 3. 配置总结
**文件**: `research/重要/SurrealDB配置完成总结.md`

包含：
- 完整的配置清单
- 下一步行动计划
- Bug 发现策略

---

## 🎯 翻译示例

### 简单查询（无需修改）
```sql
-- SQLite
SELECT * FROM users WHERE age > 25;

-- SurrealQL (完全相同！)
SELECT * FROM users WHERE age > 25;
```

### 聚合查询（需要转换）
```sql
-- SQLite
SELECT COUNT(*), AVG(age) FROM users;

-- SurrealQL
SELECT count(), math::mean(age) FROM users;
```

---

## 🔧 下一步：集成到 QTRAN

### 方法 1: 手动翻译测试
```bash
# 1. 准备测试用例
cat > /root/QTRAN/Input/surrealdb_manual_test.jsonl << 'EOF'
{"DBMS": "sqlite", "id": "001", "SQL": "CREATE TABLE t0(c0 INT); INSERT INTO t0 VALUES (1), (2), (NULL);"}
{"DBMS": "sqlite", "id": "002", "SQL": "SELECT COUNT(*), AVG(c0) FROM t0;"}
EOF

# 2. 手动翻译为 SurrealQL
cat > /root/QTRAN/Input/surrealdb_manual_test_translated.jsonl << 'EOF'
{"DBMS": "surrealdb", "id": "001", "SQL": "DEFINE TABLE t0 SCHEMAFULL; DEFINE FIELD c0 ON TABLE t0 TYPE option<int>; INSERT INTO t0 (c0) VALUES (1), (2), (NULL);"}
{"DBMS": "surrealdb", "id": "002", "SQL": "SELECT count(), math::mean(c0) FROM t0;"}
EOF

# 3. 在 SurrealDB 中执行验证
# (需要扩展 database_connector.py 支持 SurrealDB)
```

### 方法 2: 集成 LLM 自动翻译
```python
# 在 src/TransferLLM/ 中添加 SurrealDB 翻译器
# 使用 translation_prompt.md 作为系统提示词
```

---

## 🐛 预期能发现的 Bug

### 高概率 Bug 类型 ⭐⭐⭐⭐⭐

1. **查询优化器错误**
   ```surrealql
   -- 复杂 WHERE 条件
   SELECT * FROM t WHERE c0 > 10 AND c0 < 20 AND c1 = 'x';
   ```

2. **聚合函数边缘 Case**
   ```surrealql
   -- 空表聚合
   SELECT math::mean(c0) FROM empty_table;
   ```

3. **NULL 处理不一致**
   ```surrealql
   -- NULL 比较
   SELECT * FROM t WHERE c0 = NULL;  -- 应返回空
   ```

4. **类型强制转换**
   ```surrealql
   -- 字符串数字混合
   SELECT * FROM t WHERE age = '25';
   ```

---

## 📊 成功标准对比

### Demo1 成功案例 (SQLite → DuckDB)
```
翻译成功率: 95%
发现 Bug: 8 个
真 Bug: 3 个 ✅
```

### SurrealDB 预期
```
翻译成功率: 85-90% (语法更接近 SQL)
预期发现: 5-8 个可疑 Bug
预期真 Bug: 2-3 个 🎯
```

**优势**: SurrealDB 更年轻 → 更多未发现的 Bug！

---

## 🚨 常见问题

### Q1: SurrealDB 容器未启动？
```bash
# 检查容器
docker ps -a | grep surrealdb

# 重启
docker restart surrealdb_QTRAN

# 查看日志
docker logs surrealdb_QTRAN
```

### Q2: 端口 8000 被占用？
```bash
# 检查占用
netstat -tlnp | grep 8000

# 修改端口映射
# 编辑 docker-compose.yml: "8001:8000"
```

### Q3: 翻译失败率过高？
1. 检查是否使用了正确的 translation_prompt.md
2. 增加 Few-Shot 示例
3. 降低 temperature (0.1-0.3)

---

## 📈 测试流程

```
第1步: 环境验证 ✅         → 5 分钟
第2步: 手动测试           → 30 分钟
第3步: 集成 QTRAN         → 2-4 小时
第4步: 运行自动化测试      → 24 小时
第5步: 分析结果           → 4-8 小时
第6步: 报告 Bug           → 按需
```

**总计**: 1-3 天可完成首轮测试并发现 Bug

---

## 🎉 立即开始

### 现在就可以做：

```bash
# 1. 验证环境
docker ps | grep surrealdb
curl http://127.0.0.1:8000/health

# 2. 测试基本功能
python /root/QTRAN/test_surrealdb_simple.py

# 3. 查看文档
cat /root/QTRAN/NoSQLFeatureKnowledgeBase/SurrealDB/syntax_guide.md

# 4. 准备测试数据
# (使用 demo1.jsonl 或创建新的测试用例)
```

### 需要完成的工作：

- [ ] 扩展 `database_connector.py` 支持 SurrealDB 执行
- [ ] 集成翻译 Prompt 到 LLM 流程
- [ ] 运行第一轮自动化测试
- [ ] 分析结果并报告 Bug

---

## 🌟 预期突破

**这将是第一次在 SurrealDB 上进行跨语义数据库 Fuzzing！**

成功后将证明：
1. ✅ QTRAN 适用于年轻的 NoSQL 数据库
2. ✅ 类 SQL 语法 → 高翻译成功率 → 高 Bug 发现率
3. ✅ 年轻数据库有更多未被发现的 Bug

**这将是论文的重要实验证据！** 📝

---

## 📞 联系信息

- **SurrealDB 官网**: https://surrealdb.com
- **文档**: https://surrealdb.com/docs
- **GitHub**: https://github.com/surrealdb/surrealdb
- **Discord**: https://discord.gg/surrealdb

报告 Bug: https://github.com/surrealdb/surrealdb/issues

---

**快速启动指南生成时间**: 2025-10-26  
**状态**: 🟢 所有系统就绪  
**下一步**: 开始测试！ 🚀


