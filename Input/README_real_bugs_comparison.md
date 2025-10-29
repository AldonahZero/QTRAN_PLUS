# 真实 Bug 测试数据集对比

## 🎯 关键发现

**您的观察完全正确！** demo1.jsonl 中确实包含了一些"特有"语法：

```
demo1.jsonl (14条):
  ✅ PRAGMA: 1个 (index 318)
  ✅ COLLATE BINARY: 1个 (index 318)  
  ✅ COLLATE NOCASE: 3个 (index 76, 338, 345)
  📊 包含特有语法: 4/14 = 28.6%
```

这说明**并非所有"特有"语法都无法翻译**！关键在于区分：
- ❌ **严格排除**：真的无法翻译（如 `sqlite_stat1`, `INSERT OR REPLACE`）
- ✅ **可以容忍**：虽然特有，但可能可以翻译或忽略（如 `COLLATE NOCASE`, `PRAGMA`）

## 📊 三个版本对比

| 版本 | 测试用例 | 包含可容忍语法 | 比例 | 策略 |
|------|----------|---------------|------|------|
| **demo1.jsonl** | 14 条 | 4 条 | **28.6%** | 精心设计 |
| **bugs_real.jsonl** | 148 条 | 13 条 | **8.8%** | 严格过滤 ❌ |
| **bugs_real_relaxed.jsonl** | 167 条 | 32 条 | **19.2%** | 放宽过滤 ✅ |

### 结论

**bugs_real_relaxed.jsonl** (19.2%) 更接近 **demo1.jsonl** (28.6%) 的标准！

## 🔄 过滤策略对比

### 严格版本 (bugs_real.jsonl)

**排除的模式**：
```python
# 全部排除（过于严格）
'PRAGMA', 'COLLATE BINARY', 'COLLATE NOCASE',
'VACUUM', 'ANALYZE', 'EXPLAIN',
'sqlite_stat', 'INSERT OR REPLACE', ...
```

**结果**：
- ❌ 过滤掉了一些可能可以翻译的测试用例
- ❌ 与 demo1.jsonl 的标准不一致
- ✅ 但安全性最高

### 放宽版本 (bugs_real_relaxed.jsonl) ⭐推荐

**严格排除**（真的无法翻译）：
```python
'sqlite_stat',          # SQLite 内部表
'rtreecheck',           # R*Tree 扩展
'INSERT OR REPLACE',    # 语义差异大
'UPDATE OR REPLACE',
'WITHOUT ROWID',        # 涉及底层存储
'pg_backend_pid',       # PostgreSQL 特有函数
...
```

**可以容忍**（参考 demo1.jsonl）：
```python
'PRAGMA',               # demo1 有 ✅
'COLLATE BINARY',       # demo1 有 ✅
'COLLATE NOCASE',       # demo1 有 ✅
'VACUUM',               # 可以忽略
'ANALYZE',              # 可以忽略
'EXPLAIN',              # 可以忽略
```

**结果**：
- ✅ 与 demo1.jsonl 的标准一致
- ✅ 增加了 19 条测试用例
- ✅ 更接近实际可翻译的范围

## 📁 推荐使用顺序

### 1️⃣ bugs_real_relaxed.jsonl (167条) ⭐⭐⭐⭐⭐

**最推荐！** 参考 demo1.jsonl 的标准，平衡了兼容性和数量。

```bash
./run.sh Input/bugs_real_relaxed.jsonl
```

**特点**：
- 167 条真实 Bug
- 19.2% 包含可容忍语法（接近 demo1 的 28.6%）
- 平均 3.7 条 SQL

### 2️⃣ bugs_real.jsonl (148条) ⭐⭐⭐⭐

**保守选择。** 严格过滤，最安全但可能错过一些可翻译的用例。

```bash
./run.sh Input/bugs_real.jsonl
```

**特点**：
- 148 条真实 Bug
- 8.8% 包含可容忍语法
- 最保守，成功率可能更高

### 3️⃣ bugs_real_simple.jsonl (75条) ⭐⭐⭐⭐⭐

**最简单。** 只包含 SQL≤4 且每条<100字符的测试用例。

```bash
./run.sh Input/bugs_real_simple.jsonl
```

**特点**：
- 75 条真实 Bug
- 最简单，成功率最高
- 适合快速验证

### 4️⃣ demo1.jsonl (14条) ⭐⭐⭐⭐⭐

**黄金标准。** 精心设计的测试用例。

```bash
./run.sh Input/demo1.jsonl
```

**特点**：
- 14 条精心设计
- 28.6% 包含可容忍语法
- 质量最高

## 🔍 详细对比

### 数据量对比

| 数据集 | 来源 | 数量 | 平均SQL | 可容忍语法% |
|--------|------|------|---------|-----------|
| demo1.jsonl | 精心设计 | 14 | 5.0 | 28.6% |
| **bugs_real_relaxed.jsonl** | **真实Bug(放宽)** | **167** | **3.7** | **19.2%** ⭐ |
| bugs_real.jsonl | 真实Bug(严格) | 148 | 3.8 | 8.8% |
| bugs_real_simple.jsonl | 真实Bug(简单) | 75 | 3.5 | ~5% |

### 源数据库对比

**bugs_real_relaxed.jsonl** (放宽版):
- SQLite: 81条 (+13)
- DuckDB: 50条
- MySQL: 24条
- PostgreSQL: 12条 (+6)

**bugs_real.jsonl** (严格版):
- SQLite: 68条
- DuckDB: 50条
- MySQL: 24条
- PostgreSQL: 6条

## 📝 结论

您的观察非常准确！**demo1.jsonl 确实包含特有语法**，这说明：

1. ✅ **不是所有特有语法都无法翻译**
2. ✅ **应该区分"严格排除"和"可以容忍"**
3. ✅ **bugs_real_relaxed.jsonl 更接近 demo1 的标准**

**最终推荐**：
```bash
# 最推荐：放宽版本，与 demo1 标准一致
./run.sh Input/bugs_real_relaxed.jsonl  ⭐⭐⭐⭐⭐

# 保守选择：严格版本，最安全
./run.sh Input/bugs_real.jsonl

# 快速验证：简单版本，最简单
./run.sh Input/bugs_real_simple.jsonl

# 黄金标准：demo1，精心设计
./run.sh Input/demo1.jsonl
```

---

**生成时间**: 2025-10-29  
**感谢您的观察！** 这帮助我们发现了过滤规则过于严格的问题。

