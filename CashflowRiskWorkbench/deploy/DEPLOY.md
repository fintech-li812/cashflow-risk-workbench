# 现金流风险工作台 — 服务器部署说明

服务器：`39.104.201.10`（阿里云 ECS，Ubuntu 24.04.5，2 vCPU / 1.7 GB / 40 GB）
域名：`https://jdjrkj.online`（复用原有 Let's Encrypt 证书，有效期至 2027-01-14）

## 对外入口

| 用途 | 地址 |
|---|---|
| 工作台页面 | https://jdjrkj.online/ |
| HTTP 接口 | https://jdjrkj.online/api/* |
| MCP（给千问 / 远程 Agent） | https://jdjrkj.online/mcp |

## 进程与端口

| 服务 | systemd 单元 | 监听 | 说明 |
|---|---|---|---|
| 页面 + API | `cf-workbench` | 127.0.0.1:8000 | 只绑回环，由 nginx 终止 TLS |
| MCP over HTTP | `cf-mcp-http` | 127.0.0.1:8123 | 同上，路径 `/mcp` |
| 网关 | `nginx` | 0.0.0.0:80/443 | 80 强制跳 443 |

常用命令：

```bash
systemctl status cf-workbench cf-mcp-http
systemctl restart cf-workbench
journalctl -u cf-workbench -n 50 --no-pager
nginx -t && systemctl reload nginx
```

## 目录

```
/opt/cashflow/
├── mcp-server/program_v1/     # 计算引擎（Python，未改一行算法）
│   ├── src/                   # 六个模块 + public_server.py + notify.py
│   ├── demo_eight/            # 八表演示的证据包（含 approved_files 哈希）
│   ├── fixtures/              # 受信任历史结果（SHA256 校验）
│   └── inputs/                # 两张合成输入 xlsx + 注册表
├── data/                      # 八表工作簿（引擎从项目根 data/ 读取）
├── web/                       # 前端单页
├── deploy/                    # .env、systemd 单元、nginx 配置、验证脚本
└── venv/                      # Python 3.12 虚拟环境
```

## 数据库（复用服务器已装的 MySQL 8.0.46）

- 库：`cfqa_workbench`（**隔离演示库**，故意用 `cfqa_` 前缀）
- 表：`mfg_cashflow_runs_v1`（建表语句取自 `service.py` 的 DDL，不手抄）
- 应用账号：`cf_app`，**只授予 SELECT / INSERT**，只有 `@127.0.0.1` 和 `@localhost` 两个来源
- 管理账号：`cfadmin`（口令在 `/root/.cfadmin.pw`，权限 600，仅应急用）

### 为什么是 cfqa_ 而不是生产库

`agent_guard.py` 第 39 行规定：`program_calculation`（程序计算）的结果只有开着
`allow_fixture` 才允许保存；而 `config.validate()` 又规定 `allow_fixture` 只允许出现在
`cfqa_` 前缀的隔离库。**这是有意的安全设计：合成计算结果禁止写入生产库。**
要进生产库，结果必须由千问表格产出（`CF_QWEN_BOUND` 那条链路）。

## 密钥位置（都不在仓库里）

| 内容 | 位置 | 权限 |
|---|---|---|
| 应用与数据库配置 | `/opt/cashflow/deploy/.env` | 600，属主 cfrun |
| MySQL 管理口令 | `/root/.cfadmin.pw` | 600 |
| 服务器 SSH 口令 | 仅本地 `deploy/.sshpw`（已 gitignore） | — |

## 旧站点备份

替换前的静态站点与 nginx 配置存放在 `/root/backup-网站-20261027/`：

```
nginx/jdjrkj.online          原站点配置（含 /api/site/ -> 127.0.0.1:4010）
html/index.html              原站点首页
affairs/api.py               原 /opt/affairs/api.py
```

`/opt/affairs`（事务备忘录，纯 JSON 文件存储）服务本身**仍在运行**，数据文件
`/var/www/data/affairs.json` 未被触碰；但它原来的公网入口 `/api/site/` 随旧 nginx
配置一起下线了。要恢复，把备份里那段 location 加回去即可。

## 验收

```bash
# 全闭环：计算 -> 保存 -> 精确回查（四项核对）
set -a; . /opt/cashflow/deploy/.env; set +a
/opt/cashflow/venv/bin/python /opt/cashflow/deploy/verify_closed_loop.py
```

预期输出：期末 177000.00、差异 0.00、`committed`、四项核对全部通过。

## 已知缺口（如实记录，未含糊）

1. **开放访问，没有登录**。任何拿到网址的人都能打开页面、点保存（CSRF token 是嵌在页面里的，只防跨站伪造，不是身份认证）。要收紧，在 nginx 加一段 `auth_basic` 即可。
2. **推送通道未配置**。`DINGTALK_WEBHOOK` / `WECOM_WEBHOOK` 为空，`/api/notify` 会如实返回 `not_configured`，不假装成功。
3. **存的是合成数据**，`data_type=SYNTHETIC`，不代表任何真实企业口径。
4. **千问能否直接连这个 `/mcp` 尚未验证**——服务器侧握手已通，千问侧的连接器是否接受 HTTP URL 需拿它的产品实测。
5. 证书是原来那张，**没有为子域名扩展**；如需 `cf.jdjrkj.online` 要先加 DNS 记录再签新证书。
