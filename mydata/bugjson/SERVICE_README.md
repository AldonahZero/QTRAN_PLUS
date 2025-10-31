# Bug爬虫系统服务配置说明

## 📋 概述

Bug爬虫已配置为 systemd 系统服务，实现：
- ✅ 开机自动启动
- ✅ 定期自动运行（每天凌晨2点）
- ✅ 完整的日志记录
- ✅ 失败自动重试
- ✅ 资源限制保护

## 🚀 快速使用

### 管理命令

```bash
# 进入目录
cd /root/QTRAN/mydata/bugjson

# 查看服务状态
./manage_crawler_service.sh status

# 立即运行一次
./manage_crawler_service.sh run

# 查看日志
./manage_crawler_service.sh logs

# 查看最近100行日志
./manage_crawler_service.sh logs 100

# 重启定时器
./manage_crawler_service.sh restart

# 修改运行频率
./manage_crawler_service.sh schedule

# 卸载服务
./manage_crawler_service.sh uninstall
```

## ⚙️ 服务配置

### 当前配置

- **首次运行**: 系统启动15分钟后
- **定期运行**: 每天凌晨2点（±30分钟随机延迟）
- **日志位置**: `/var/log/bug-crawler/`
- **资源限制**: CPU 50%，内存 1GB
- **超时时间**: 1小时
- **失败重试**: 5分钟后自动重试

### 文件位置

```
/etc/systemd/system/
├── bug-crawler.service          # 服务定义
└── bug-crawler.timer            # 定时器配置

/root/QTRAN/mydata/bugjson/
├── run_crawler.sh               # 运行脚本
├── manage_crawler_service.sh    # 管理工具
├── crawler_env.example          # 环境变量示例
└── multi_source_crawler.py      # 爬虫主程序

/var/log/bug-crawler/
├── crawler_YYYYMMDD_HHMMSS.log  # 历史日志
└── latest.log                   # 最新日志链接
```

## 🔧 高级配置

### 1. 设置GitHub Token（推荐）

GitHub API有频率限制：
- 未认证: 60次/小时
- 已认证: 5000次/小时

**设置方法：**

```bash
# 复制环境变量模板
cp crawler_env.example crawler_env

# 编辑配置文件
nano crawler_env

# 在文件中设置：
GITHUB_TOKEN=ghp_your_token_here

# 修改服务配置以使用环境文件
nano /etc/systemd/system/bug-crawler.service

# 添加以下行（在[Service]部分）：
EnvironmentFile=/root/QTRAN/mydata/bugjson/crawler_env

# 重新加载并重启
systemctl daemon-reload
systemctl restart bug-crawler.timer
```

**获取GitHub Token：**
1. 访问: https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 选择权限: `public_repo`, `read:org`
4. 生成并复制token

### 2. 修改运行频率

编辑定时器配置：

```bash
nano /etc/systemd/system/bug-crawler.timer
```

**常用配置示例：**

```ini
# 每天一次（凌晨2点）
OnCalendar=*-*-* 02:00:00

# 每12小时（上午0点和中午12点）
OnCalendar=*-*-* 00,12:00:00

# 每周日凌晨运行
OnCalendar=Sun *-*-* 02:00:00

# 每月1号运行
OnCalendar=*-*-01 02:00:00

# 固定间隔：每6小时运行
OnUnitActiveSec=6h
```

修改后重新加载：

```bash
systemctl daemon-reload
systemctl restart bug-crawler.timer
```

### 3. 查看下次运行时间

```bash
systemctl list-timers bug-crawler.timer
```

### 4. 实时查看日志

```bash
# systemd日志（实时）
journalctl -u bug-crawler.service -f

# 文件日志（实时）
tail -f /var/log/bug-crawler/latest.log
```

### 5. 手动运行（用于测试）

```bash
# 方法1: 使用管理脚本
./manage_crawler_service.sh run

# 方法2: 直接运行
systemctl start bug-crawler.service

# 方法3: 手动执行脚本
bash /root/QTRAN/mydata/bugjson/run_crawler.sh
```

## 📊 监控和维护

### 查看服务健康状态

```bash
# 详细状态
systemctl status bug-crawler.service
systemctl status bug-crawler.timer

# 最近的运行记录
journalctl -u bug-crawler.service --since "1 week ago"

# 检查失败记录
journalctl -u bug-crawler.service -p err
```

### 日志管理

- 日志自动保留30天
- 每次运行创建新日志文件
- `latest.log` 始终指向最新日志

**手动清理日志：**

```bash
# 清理30天前的日志
find /var/log/bug-crawler -name "crawler_*.log" -mtime +30 -delete

# 查看日志大小
du -sh /var/log/bug-crawler/
```

## 🐛 故障排查

### 服务未运行

```bash
# 检查服务状态
systemctl status bug-crawler.timer

# 如果未启动，手动启动
systemctl start bug-crawler.timer

# 检查是否启用开机自启
systemctl is-enabled bug-crawler.timer
```

### 执行失败

```bash
# 查看错误日志
journalctl -u bug-crawler.service -n 100 --no-pager

# 检查脚本权限
ls -l /root/QTRAN/mydata/bugjson/run_crawler.sh

# 手动运行测试
bash -x /root/QTRAN/mydata/bugjson/run_crawler.sh
```

### API限制问题

如果看到 "API rate limit exceeded" 错误：
1. 设置 GitHub Token（见上方说明）
2. 减少运行频率
3. 添加更长的随机延迟

### Python环境问题

如果使用虚拟环境，修改 `run_crawler.sh`：

```bash
# 取消注释并修改虚拟环境路径
source /root/QTRAN/venv/bin/activate
```

## 🔄 升级和更新

### 更新爬虫代码

```bash
# 修改爬虫代码后，无需重启服务
# 代码会在下次定时运行时自动使用

# 如果想立即测试新代码
./manage_crawler_service.sh run
```

### 更新服务配置

```bash
# 修改服务配置文件后
nano /etc/systemd/system/bug-crawler.service
# 或
nano /etc/systemd/system/bug-crawler.timer

# 重新加载配置
systemctl daemon-reload

# 重启服务
systemctl restart bug-crawler.timer
```

## 📈 性能优化

### 资源限制调整

编辑 `/etc/systemd/system/bug-crawler.service`:

```ini
[Service]
# CPU限制（50% = 单核的一半）
CPUQuota=50%

# 内存限制
MemoryLimit=1G

# 超时时间（秒）
TimeoutStartSec=3600
```

### 并发爬取

修改 `multi_source_crawler.py` 中的并发参数以提高速度（注意API限制）。

## 📚 相关命令速查

```bash
# 启动/停止/重启
systemctl start bug-crawler.service
systemctl stop bug-crawler.service
systemctl restart bug-crawler.service

# 定时器控制
systemctl start bug-crawler.timer
systemctl stop bug-crawler.timer
systemctl restart bug-crawler.timer

# 启用/禁用开机自启
systemctl enable bug-crawler.timer
systemctl disable bug-crawler.timer

# 查看日志
journalctl -u bug-crawler.service
journalctl -u bug-crawler.service -f         # 实时
journalctl -u bug-crawler.service -n 50      # 最近50行
journalctl -u bug-crawler.service --since today

# 查看定时器列表
systemctl list-timers
systemctl list-timers --all
```

## ✅ 验证安装

检查服务是否正常工作：

```bash
# 1. 检查服务状态
./manage_crawler_service.sh status

# 2. 查看下次运行时间
systemctl list-timers bug-crawler.timer

# 3. 立即运行一次测试
./manage_crawler_service.sh run

# 4. 查看运行日志
./manage_crawler_service.sh logs

# 5. 检查数据是否更新
ls -lh /root/QTRAN/mydata/bugjson/bugs_new.json
```

## 🆘 支持

如有问题，请检查：
1. 服务日志: `./manage_crawler_service.sh logs`
2. 系统日志: `journalctl -u bug-crawler.service`
3. 文件日志: `/var/log/bug-crawler/latest.log`

---

**最后更新**: 2025-10-31

