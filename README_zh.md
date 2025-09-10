# QTRAN：扩展基于变形预言机的逻辑漏洞检测技术以支持多 DBMS 方言

## 摘要

QTRAN 减轻了现有 MOLTs（基于变形预言机的逻辑漏洞检测技术）对特定 DBMS 语法的依赖，并增强了其向新 DBMS 的扩展能力，可显著提高各类 DBMS 的可靠性和测试稳健性。

QTRAN 是一种新颖的基于大语言模型（LLM）的方法，能自动将现有 MOLTs 扩展到多种 DBMS。QTRAN 确保大多数转换后的 SQL 语句对适用于变形测试，并已发现 24 个此前未知的逻辑漏洞，其中 16 个已被确认。

工作流程包含两个关键阶段：迁移阶段和变异阶段。

## 前提条件

### 环境设置

本指南将帮助你使用 Python 3.11 搭建项目环境。请按照以下步骤操作：



1.  推荐使用 **Python 3.11** 或更高版本。

2.  克隆仓库



```
git clone <仓库地址>

cd <项目目录>
```



1.  激活虚拟环境

2.  安装依赖



```
pip install -r requirements.txt
```

### 构建数据库

运行前，请确保数据库已正确构建和配置。你可以按照 [Docker\_Databases](Docker_Databases.md)** 中的说明（主要使用 Docker-Compose）** 构建数据库，也可以自行构建这些数据库。

**请注意：** 数据库构建成功后，**务必将正确的数据库配置信息填入 **[database\_connector\_args.json](src/Tools/DatabaseConnect/database_connector_args.json)** 文件**，以确保 QTRAN 正常运行。

### LLM 密钥

运行 QTRAN 前，请确保你拥有 **LLM API 密钥**，以便 QTRAN 在执行过程中成功调用大模型。

将 `api_key` 设置为环境变量，并检查是否设置成功。QTRAN 将使用该 API 密钥访问 OpenAI。



```
\# Windows 系统

SET OPENAI\_API\_KEY=\${你的\_api\_key}

\# Linux/Mac 系统

export OPENAI\_API\_KEY=\${你的\_api\_key}
```

### 微调变异 LLM

QTRAN 已为 NoREC、TLP、PINOLO 和 DQE 精心构建了用于微调变异 LLM 的训练数据集。在这些数据集上微调后，变异 LLM 可实现较高的变异准确率。请使用提供的训练数据集和你的 LLM 密钥，按照微调说明（详见 [Fine-tune\_MutationLLM](Fine-tune_MutationLLM.md)）微调模型，并获取 “微调模型 ID” 供 QTRAN 工具使用。

**注意：**

微调模型需要 LLM 的 API 密钥。微调完成后，仍需使用相同的 API 密钥调用微调后的模型，不可使用不同的 API 密钥访问。

然后，请记住为 QTRAN 的变异阶段设置 MOLTs 的 “微调模型 ID”：



```
\# Windows 系统

SET NOREC\_MUTATION\_LLM\_ID=\${你的\_norec变异\_llm\_id}

SET TLP\_MUTATION\_LLM\_ID=\${你的\_tlp变异\_llm\_id}

SET PINOLO\_MUTATION\_LLM\_ID=\${你的\_pinolo变异\_llm\_id}

SET DQE\_MUTATION\_LLM\_ID=\${你的\_dqe变异\_llm\_id}

\# Linux/Mac 系统

export NOREC\_MUTATION\_LLM\_ID=\${你的\_norec变异\_llm\_id}

export TLP\_MUTATION\_LLM\_ID=\${你的\_tlp变异\_llm\_id}

export PINOLO\_MUTATION\_LLM\_ID=\${你的\_pinolo变异\_llm\_id}

export DQE\_MUTATION\_LLM\_ID=\${你的\_dqe变异\_llm\_id}
```

## 主要流程

QTRAN 将分析过程分为两个阶段：迁移阶段和变异阶段。它从现有 MOLTs 的 SQL 语句对开始，通过这两个阶段将这些语句对扩展到新的 DBMS。

### 输入

QTRAN 的输入文件是 `Input` 目录下的 JSONL 文件，每行包含一条 JSON 格式的测试数据。每条测试数据来自现有 MOLTs，格式如下。该测试数据用于 QTRAN 将原始 SQL 语句从 `sqlite`（a\_db）转换为 `clickhouse`（b\_db）的 SQL 语句对，对应的 MOLT 为 NoREC（molt）。



```
{ &#x20;

&#x20; "index": 0, &#x20;

&#x20; "a\_db": "sqlite", &#x20;

&#x20; "b\_db": "clickhouse", &#x20;

&#x20; "molt": "norec", &#x20;

&#x20; "sqls": \[ &#x20;

&#x20;   "CREATE TABLE t0(c0 INT UNIQUE);", &#x20;

&#x20;   "INSERT INTO t0(c0) VALUES (1);", &#x20;

&#x20;   "SELECT COUNT(\*) FROM t0 WHERE '1' IN (t0.c0); -- 异常：返回行" &#x20;

&#x20; ] &#x20;

}
```

### 迁移阶段

执行以下命令运行 QTRAN。演示输入文件 `demo1.jsonl` 位于 `Input` 目录中。

进入项目目录：



```
cd <项目目录>
```

命令参数说明如下：



| 参数                  | 描述                                |
| ------------------- | --------------------------------- |
| `--input_filename`  | 输入文件路径（JSONL 格式）。                 |
| `--tool`            | MOLTs 工具名称（如 "sqlancer"、"pinolo"） |
| `--temperature`     | LLM 的温度参数（默认：0.3）                 |
| `--model`           | 用于 LLM 的模型（默认：gpt-4o-mini）        |
| `--error_iteration` | 启用错误迭代（默认：True）                   |
| `--iteration_num`   | 迭代次数（默认：4）                        |

默认参数执行示例：



```
python -m src.main --input\_filename "Input/demo1.jsonl" --tool "sqlancer" --temperature 0.7 --model="gpt-3.5-turbo" --error\_iteration=True --iteration\_num 5
```

自定义参数执行示例：



```
python -m src.main --input\_filename "Input/demo1.jsonl" --tool "sqlancer"
```

迁移阶段的中间结果存储在 `Output` 文件夹中，具体路径为 `Output/demo1/TransferLLM`。每条测试用例的 “迁移结果”“迁移成本”“迁移时间” 等信息均会被记录。

### 变异阶段

变异阶段的中间结果存储在输出文件夹中，具体路径为 Output/demo1/MutationLLM。对于每个测试用例，都会记录变异结果、变异成本、变异时间以及 Oracle 的 MOLT 检查等信息。

QTRAN 检测到的可疑逻辑错误存储在输出文件夹中，具体路径为 Output/demo1/SuspiciousBugs，包括经过两个阶段扩展到新 DBMS 的最终 SQL 语句对。
