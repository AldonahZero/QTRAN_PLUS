# Docker 数据库构建说明（QTRAN 项目）

本文档将介绍如何创建并运行 Docker 镜像，以构建 QTRAN 所需的数据库（包括 ClickHouse、DuckDB、MariaDB、MonetDB、MySQL、Postgres、SQLite、TiDB）。请按照以下步骤复现环境。

## Docker 环境准备

确保已安装最新版本的 Docker。

## 步骤 1：创建并运行 Docker 镜像



1.  **进入 QTRAN 目录**

    切换到示例所在的 `QTRAN` 目录：



```
cd QTRAN
```



1.  **构建 Docker 镜像**

    在 `QTRAN` 目录下，通过 Dockerfile 构建镜像：



```
docker-compose up --build -d
```

## 步骤 2：运行 Docker 镜像

通过以下命令启动容器实例：



```
docker-compose up -d
```

## 步骤 3：数据库配置

部分数据库需要修改权限或进行额外配置，具体步骤如下，请按要求完成设置。

### ClickHouse

进入 ClickHouse 容器：

（参考 ClickHouse 官方问题：[https://github.com/ClickHouse/ClickHouse/issues/13057](https://github.com/ClickHouse/ClickHouse/issues/13057)，为默认账号授予管理员权限）



```
apt-get update  # 安装 apt-get（可选操作）

apt-get install vim  # 安装 vim（可选操作，用于编辑配置文件）
```

编辑用户配置文件：



```
vim /etc/clickhouse-server/users.xml  # 修改用户配置
```



```
\# 在 \<default> 标签内找到如下注释内容，取消该行注释

\<!-- \<access\_management>1\</access\_management> -->  &#x20;

\# 在 \<access\_management>1\</access\_management> 后添加以下配置

\<yandex>

&#x20;   \<users>

&#x20;       \<default>

&#x20;           \<access\_management>1\</access\_management>

&#x20;           \<named\_collection\_control>1\</named\_collection\_control>

&#x20;           \<show\_named\_collections>1\</show\_named\_collections>

&#x20;           \<show\_named\_collections\_secrets>1\</show\_named\_collections\_secrets>

&#x20;       \</default>

&#x20;   \</users>

\</yandex>
```

使用 `clickhouse-client` 登录 ClickHouse 数据库（默认账号）：



```
clickhouse-client
```

创建管理员账号：



```
CREATE user admin IDENTIFIED WITH sha256\_password BY '123456';
```

为管理员账号授予所有权限：



```
GRANT ALL PRIVILEGES ON \*.\* TO admin WITH GRANT OPTION;
```

退出登录：



```
exit
```

使用 `clickhouse-client` 登录 ClickHouse 数据库（管理员账号，登录前可通过取消对应配置注释，收回默认账号的权限）：



```
clickhouse-client -u admin --password 123456
```

修改管理员账号密码：



```
ALTER USER admin IDENTIFIED WITH plaintext\_password BY '123456';
```

### DuckDB

DuckDB 官方未维护其 Docker 镜像，因此无法通过 Docker 容器构建。对于 DuckDB，需通过文件路径（如 `<主机文件路径>/db_name.duckdb`）访问数据库，而非常规的 “主机 / 数据库” 格式。

### MariaDB

（无特殊配置说明，按默认方式使用即可）

### MonetDB

数据库创建与删除示例：



```
monetdb create PINOLO\_MonetDB  # 创建数据库

monetdb release PINOLO\_MonetDB  # 解锁权限，以便后续删除数据库

monetdb start PINOLO\_MonetDB   # 启动数据库

monetdb stop PINOLO\_MonetDB    # 停止数据库

monetdb lock db\_name           # 锁定数据库（锁定后才可删除）

monetdb destroy db\_name        # 删除数据库
```

使用 `mclient` 登录 MonetDB 数据库（默认用户名：`monetdb`，默认密码：`monetdb`）：



```
mclient -u monetdb -d PINOLO\_MonetDB
```

修改 root 密码（可选操作，默认密码为 `monetdb`，也可选择不修改）：



```
ALTER USER SET PASSWORD '123456' USING OLD PASSWORD 'monetdb';
```

### MySQL

（无特殊配置说明，按默认方式使用即可）

### PostgreSQL

（无特殊配置说明，按默认方式使用即可）

### SQLite

SQLite **无需构建**。由于几乎所有 Linux 操作系统版本都预装了 SQLite，可直接使用系统自带版本，无需额外构建。需注意以下几点：



1.  **切换数据库**：SQLite 无需 `USE` 语句，可直接指定数据库文件路径。

2.  **删除数据库文件**：若需模拟 SQLite 中的 `DROP DATABASE`，需通过文件系统命令删除 `db_name.db` 文件（例如在 Python、Shell 中执行 `rm db_name.db`）。

3.  **创建新数据库**：在 SQLite 中，创建新数据库即创建新的数据库文件，可通过 SQLite 命令行工具或程序连接到新的数据库文件 `db_name.db` 完成创建。

### TiDB



1.  **下载并安装 TiUP**（TiDB 官方包管理工具）：



```
curl --proto '=https' --tlsv1.2 -sSf https://tiup-mirrors.pingcap.com/install.sh | sh
```

若出现以下响应，说明安装成功。其中会显示 Shell 配置文件的绝对路径（如 `/root/.bashrc`），请记录该路径，后续步骤需使用：



```
Successfully set mirror to https://tiup-mirrors.pingcap.com

Detected shell: bash

Shell profile:  /root/.bashrc

Installed path: /root/.tiup/bin/tiup

\===============================================

Have a try:     tiup playground

\===============================================
```



1.  **声明全局环境变量**（将 `${your_shell_profile}` 替换为上一步获取的 Shell 配置文件绝对路径）：



```
source \${your\_shell\_profile}
```



1.  **安装 TiUP Cluster 组件**（用于集群管理）：



```
tiup cluster  # 执行该命令会自动安装组件

tiup update --self && tiup update cluster  # 更新 TiUP 自身及 Cluster 组件
```



1.  **调整 SSH 服务配置，提高多机部署模拟的 SSHD 连接限制**：

*   编辑 `/etc/ssh/sshd_config` 文件，将 `MaxSessions` 设置为 20：



```
MaxSessions 20
```



*   重启 SSHD 服务：



```
service sshd restart

sudo systemctl enable ssh.service  # 设置 SSH 服务开机自启
```



1.  **创建并启动集群**：

    按照以下配置模板创建名为 `topo.yaml` 的配置文件，模板及参数说明如下：

    **配置模板如下**：



```
global:

&#x20;       user: "tidb"

&#x20;       ssh\_port: 22

&#x20;       deploy\_dir: "/home/TiDB/deploy"

&#x20;       data\_dir: "/home/TiDB/data"

monitored:

&#x20;       node\_exporter\_port: 9100

&#x20;       blackbox\_exporter\_port: 9115

server\_configs:

&#x20;       tidb:

&#x20;               instance.tidb\_slow\_log\_threshold: 300

&#x20;       tikv:

&#x20;               readpool.storage.use-unified-pool: false

&#x20;               readpool.coprocessor.use-unified-pool: true

&#x20;       pd:

&#x20;               replication.enable-placement-rules: true

&#x20;               replication.location-labels: \["host"]

&#x20;       tiflash:

&#x20;               logger.level: "info"

pd\_servers:

&#x20;       \- host: 127.0.0.1

tidb\_servers:

&#x20;       \- host: 127.0.0.1

tikv\_servers:

&#x20;       \- host: 127.0.0.1

&#x20;         port: 20160

&#x20;         status\_port: 20180

&#x20;         config:

&#x20;                 server.labels: { host: "logic-host-1" }

&#x20;       \- host: 127.0.0.1

&#x20;         port: 20161

&#x20;         status\_port: 20181

&#x20;         config:

&#x20;                 server.labels: { host: "logic-host-2" }

&#x20;       \- host: 127.0.0.1

&#x20;         port: 20162

&#x20;         status\_port: 20182

&#x20;         config:

&#x20;                 server.labels: { host: "logic-host-3" }

tiflash\_servers:

&#x20;       \- host: 127.0.0.1

monitoring\_servers:

&#x20;       \- host: 127.0.0.1

grafana\_servers:

&#x20;       \- host: 127.0.0.1
```



*   `user: "tidb"`：表示集群内部管理将通过 `tidb` 系统用户（部署时会自动创建），默认通过 22 端口 SSH 登录目标机器。

*   `replication.enable-placement-rules`：PD（Placement Driver）的必要参数，确保 TiFlash 正常运行。

*   `host`：设置为当前部署机器的 IP，需将模板中所有 `host` 字段替换为部署机器的实际 IP。

*   执行前，先在 `/home/TiDB` 下创建 `deploy_dir` 和 `data_dir` 文件夹：



```
mkdir -p /home/TiDB/deploy\_dir

mkdir -p /home/TiDB/data\_dir
```



1.  **执行集群部署命令**：



```
tiup cluster deploy tidb\_QTRAN 8.3.0 ./topo.yaml --user root -p 123456
```

按照提示输入 `y` 并输入 root 密码，完成部署：



```
&#x20;   Do you want to continue? \[y/N]:  y

&#x20;   Input SSH password:  # 输入 root 密码
```



*   参数说明：


    *   `<cluster-name>`：集群名称（此处为 `tidb_QTRAN`）。

    *   `<version>`：集群版本（此处为 `8.3.0`），可通过 `tiup list tidb` 查看支持的 TiDB 部署版本。

    *   `-p`：通过密码登录目标机器（若使用 SSH 密钥认证，需用 `-i` 指定密钥文件路径，且 `-i` 与 `-p` 不可同时使用）。

1.  **启动 / 停止集群**：



```
tiup cluster start tidb\_QTRAN --init  # 首次启动（--init 初始化集群）

tiup cluster start tidb\_QTRAN         # 后续启动（无需 --init）

tiup cluster stop tidb\_QTRAN          # 停止集群
```



1.  **无密码访问 TiDB 数据库**：



```
mysql -h172.24.89.100 -P 4000 -u root -p  # 执行后按回车（默认无密码）
```

## 其他常用命令



*   **停止所有容器**：`docker-compose down`

*   **查看容器状态**：`docker-compose ps`

*   **查看容器日志**：`docker-compose logs`

> （注：文档部分内容可能由 AI 生成）