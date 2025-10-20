# JSONL 文件拆分工具

## 功能说明

将单个 JSONL 文件按 `index` 字段拆分到目录中，每个 index 对应一个单独的 JSONL 文件。

## 使用方法

### 基本用法

```bash
python split_jsonl_to_directory.py <input_jsonl_path>
```

### 指定输出目录

```bash
python split_jsonl_to_directory.py <input_jsonl_path> <output_dir>
```

## 示例

### 示例 1: 拆分 demo1.jsonl

```bash
python split_jsonl_to_directory.py Input/demo1.jsonl
```

**输出：**
- 创建目录：`Input/demo1/`
- 文件结构：
  ```
  Input/demo1/
  ├── 162.jsonl
  ├── 318.jsonl
  ├── 76.jsonl
  ├── 638.jsonl
  └── ...
  ```

### 示例 2: 拆分 demo1_tdsql.jsonl

```bash
python split_jsonl_to_directory.py Input/demo1_tdsql.jsonl
```

**输出：**
- 创建目录：`Input/demo1_tdsql/`
- 文件结构：
  ```
  Input/demo1_tdsql/
  ├── 162.jsonl
  ├── 318.jsonl
  ├── 76.jsonl
  └── ...
  ```

### 示例 3: 自定义输出目录

```bash
python split_jsonl_to_directory.py Input/demo1.jsonl Output/demo1_split
```

**输出：**
- 创建目录：`Output/demo1_split/`

## 脚本行为

1. **自动创建目录**：如果输出目录不存在，会自动创建（包括父目录）
2. **清空已存在目录**：如果输出目录已存在，会先清空再写入新文件
3. **使用 index 字段**：优先使用 JSON 记录中的 `index` 字段作为文件名
4. **回退到行号**：如果记录没有 `index` 字段，使用行号（从 0 开始）作为文件名
5. **错误处理**：跳过无法解析的 JSON 行，并打印警告信息

## 文件格式

### 输入文件格式

```jsonl
{"index": 162, "a_db": "sqlite", "b_db": "duckdb", "sqls": [...]}
{"index": 318, "a_db": "sqlite", "b_db": "monetdb", "sqls": [...]}
{"index": 76, "a_db": "sqlite", "b_db": "tidb", "sqls": [...]}
```

### 输出文件格式

每个文件包含一条 JSON 记录（单行 JSONL）：

**162.jsonl:**
```jsonl
{"index": 162, "a_db": "sqlite", "b_db": "duckdb", "sqls": [...]}
```

**318.jsonl:**
```jsonl
{"index": 318, "a_db": "sqlite", "b_db": "monetdb", "sqls": [...]}
```

## 作为 Python 模块使用

```python
from split_jsonl_to_directory import split_jsonl_to_directory

# 基本用法
split_jsonl_to_directory("Input/demo1.jsonl")

# 指定输出目录
split_jsonl_to_directory("Input/demo1.jsonl", "Output/custom_dir")

# 静默模式（不打印详细信息）
split_jsonl_to_directory("Input/demo1.jsonl", verbose=False)
```

## 批量处理示例

如果需要批量处理多个 JSONL 文件，可以使用以下脚本：

```bash
# 处理 Input 目录下所有 .jsonl 文件
for file in Input/*.jsonl; do
    python split_jsonl_to_directory.py "$file"
done
```

或者在 Python 中：

```python
from pathlib import Path
from split_jsonl_to_directory import split_jsonl_to_directory

input_dir = Path("Input")
for jsonl_file in input_dir.glob("*.jsonl"):
    print(f"处理: {jsonl_file}")
    split_jsonl_to_directory(str(jsonl_file))
```

## 注意事项

1. 脚本会 **覆盖** 已存在的输出目录
2. 文件名基于 `index` 字段，确保 index 值唯一避免文件覆盖
3. 支持 UTF-8 编码，处理中文等多语言字符
4. 空行会被自动跳过

## 错误处理

- **文件不存在**：抛出 `FileNotFoundError`
- **JSON 解析失败**：打印警告并跳过该行
- **缺少 index 字段**：使用行号并打印警告
- **权限错误**：检查目录读写权限

## 与现有目录结构的关系

本脚本创建的目录结构与项目中已有的结构一致：

```
Input/
├── demo1.jsonl          # 原始 JSONL 文件
├── demo1/               # 拆分后的目录
│   ├── 0.jsonl
│   ├── 1.jsonl
│   └── ...
├── demo1_tdsql.jsonl    # TDSQL 版本的 JSONL 文件
└── demo1_tdsql/         # TDSQL 拆分后的目录
    ├── 162.jsonl
    ├── 318.jsonl
    └── ...
```
