# 真实Bug数据集 - bugs_real_relaxed_filtered.jsonl

## 概述
这是从 `bugs_real_relaxed.jsonl` 中筛选出的**真正的数据库逻辑bug**数据集，排除了翻译策略导致的假阳性bug。

## 数据统计
- **总bug数量**: 61个
- **Index范围**: 2002 - 2161
- **数据来源**: bugs_real_relaxed

## 数据库分布

| 数据库转换方向 | Bug数量 |
|--------------|---------|
| sqlite → duckdb | 28 |
| duckdb → postgres | 21 |
| mysql → mariadb | 6 |
| postgres → duckdb | 4 |
| mysql → tidb | 2 |

## 筛选标准

### ✅ 保留（真实bug）
- Oracle检查失败（`end: false`）
- 无执行错误（`error: null`）
- **翻译没有改变数据语义**（未使用NULL替换、未修改值）
- 目标数据库的逻辑不一致

### ❌ 排除（假阳性）
- 翻译时改变了数据（使用NULL替换原值）
- 翻译时修改了查询语义
- 执行错误（非逻辑bug）

## Bug Index列表

```
2002, 2006, 2008, 2010, 2014, 2015, 2016, 2017, 2018, 2019, 
2021, 2023, 2031, 2039, 2040, 2043, 2048, 2049, 2050, 2051, 
2055, 2060, 2064, 2066, 2067, 2069, 2071, 2072, 2078, 2085, 
2087, 2089, 2091, 2100, 2101, 2103, 2106, 2113, 2115, 2116, 
2119, 2120, 2122, 2123, 2124, 2126, 2127, 2130, 2131, 2133, 
2134, 2135, 2138, 2140, 2149, 2150, 2151, 2152, 2158, 2160, 
2161
```

## 使用方法

### 运行测试
```bash
python src/TransferLLM/translate_sqlancer.py \
    --input Input/bugs_real_relaxed_filtered.jsonl \
    --temperature 0.3 \
    --model gpt-4o-mini
```

### 生成可疑bug报告
```bash
python src/Tools/suspicious_explainer.py bugs_real_relaxed_filtered
```

## 文件结构

每行是一个JSON对象，包含：
- `index`: bug的唯一标识
- `a_db`: 源数据库类型
- `b_db`: 目标数据库类型
- `molt`: Oracle类型（norec/tlp/semantic）
- `sqls`: SQL语句列表

## 相关文件

- **原始输入**: `Input/bugs_real_relaxed.jsonl` (168个bug)
- **筛选后输入**: `Input/bugs_real_relaxed_filtered.jsonl` (61个真实bug)
- **分析结果**: `Output/bugs_real_relaxed/true_db_bugs.json`
- **可疑bug**: `Output/bugs_real_relaxed/SuspiciousBugs/`

## 生成时间
2025-10-30

## 备注
这些bug都是通过QTRAN框架检测出的目标数据库逻辑不一致问题，已排除翻译策略导致的假阳性，可以作为高质量的bug报告提交给相应的数据库项目。



