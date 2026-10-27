# CashflowRiskWorkbench · SSH 隧道角色账号与私钥（脱敏版）

> **本文件为脱敏版**：按共享工作区纪律「不上传密码、密钥、令牌」，**私钥正文不进入共享区**。
> 含私钥原文的 owner 版仅存在于本机：
> `C:\Users\33847\WorkBuddy\2026-10-15-20-06-39\cf_ssh_credentials.md`
> 由 owner 经安全渠道按角色分发，**不得**复制进共享区、聊天、群聊或代码仓库。

---

## 一、角色 ↔ SSH 账号 ↔ MySQL 角色 对应表

| 用途 | SSH 隧道账号 | 允许转发目标（permitopen） | 对应 MySQL 角色 | 使用者 |
|---|---|---|---|---|
| 管理员 / 迁移发布 | `tun_admin` | `127.0.0.1:3306` | `cf_admin`（SELECT/INSERT/UPDATE/CREATE/ALTER/DROP/INDEX/REFERENCES） | 包A、牛马Y |
| 只读查询 | `tun_read` | `127.0.0.1:3306` | `cf_read`（仅 SELECT） | 牛马X、包B |
| 应用运行（非人） | `tun_app` | `127.0.0.1:3306` | `cf_app`（SELECT/INSERT） | 应用机 |
| 备份（非人） | `tun_backup` | `127.0.0.1:3306` | `cf_backup`（SELECT/LOCK TABLES/SHOW VIEW/TRIGGER + PROCESS ON \*.\*） | 备份机 |
| MCP 连接器（非人） | `tun_mcp` | `127.0.0.1:8000` | 不连 MySQL，连 MCP Server | 千问办公 |
| **运维接管（新增）** | `codex_ops` | 无限制（完整 shell + sudo） | 不直连 DB（走 root 或 cf_admin） | Codex |

安全属性：
- 所有 `tun_*` 账号 shell = `/usr/sbin/nologin`，`command="/usr/sbin/nologin"` 写死在 `authorized_keys`，**私钥泄露也拿不到服务器 shell**。
- 每个 `tun_*` 只能转发上表指定端口，越权转发由服务端 `permitopen` 拒绝。
- `codex_ops` 是完整 shell + `sudo NOPASSWD: ALL`，**权限等同 root，但独立身份、可审计、删一行公钥即可吊销**。

---

## 二、连接命令模板（发给成员时附上，私钥自行配对）

```bash
# 管理员（包A / 牛马Y）
ssh -N -L 13306:127.0.0.1:3306 -i <tun_admin私钥> tun_admin@39.104.201.10
mysql -h 127.0.0.1 -P 13306 -u cf_admin -p

# 只读（牛马X / 包B）
ssh -N -L 13306:127.0.0.1:3306 -i <tun_read私钥> tun_read@39.104.201.10
mysql -h 127.0.0.1 -P 13306 -u cf_read -p

# 应用机（部署脚本内）
ssh -N -L 13306:127.0.0.1:3306 -i <tun_app私钥> tun_app@39.104.201.10
# 应用连 127.0.0.1:13306，账号 cf_app

# 备份机
ssh -N -L 13306:127.0.0.1:3306 -i <tun_backup私钥> tun_backup@39.104.201.10
# 备份脚本连 127.0.0.1:13306，账号 cf_backup

# 千问办公连 MCP（转发 8000）
ssh -N -L 18000:127.0.0.1:8000 -i <tun_mcp私钥> tun_mcp@39.104.201.10
# MCP 连接器填：http://127.0.0.1:18000/mcp
```

> 本地端口（13306 / 18000）可自选，只要不与本机已用端口冲突。

---

## 三、私钥的存放与取用（owner 操作，不在共享区流转）

私钥存于服务器（权限 600，仅 root 可读）：

```bash
# 在服务器上查看某角色私钥（owner 通过 root SSH 执行）
ssh -i <root私钥> root@39.104.201.10 "cat /etc/cf-mcp/ssh_keys/tun_admin_key"
# 路径格式：/etc/cf-mcp/ssh_keys/<角色>_key   公钥同名 .pub
```

MySQL 角色口令（同样不进共享区）：

```bash
ssh -i <root私钥> root@39.104.201.10 "cat /etc/cf-mcp/env"
# 含 CF_ADMIN_PASS / CF_APP_PASS / CF_BACKUP_PASS / CF_READ_PASS
```

分发纪律：**一人一号一角色**，只发其本人角色对应的私钥与口令，不交叉发放。

---

## 四、常驻隧道（避免手点，断线自愈）

成员机器用 `autossh` + systemd user service，详见 `05_cf-tunnel.service`。
核心参数：`-M 0 -o ServerAliveInterval=30 -o ServerAliveCountMax=3`，`Restart=always`、`RestartSec=5`。
启用：`systemctl --user enable --now cf-tunnel-<角色>.service`。

> 隧道断 = 留痕写不进 DB，因此常驻自愈是硬性要求，不能靠手点。

---

## 五、已验证结论（服务器侧冒烟测试，2026-10-22）

- `tun_admin` / `tun_read` → 3306：读到 MySQL 握手字节，通道真实可达 ✅
- `tun_read` / `tun_mcp` → 22（越权）：被 `permitopen` 拒绝，读 0 字节 ✅
- 任意 `tun_*` 执行远程命令：被 `nologin` 拒绝（exit ≠ 0）✅
- `sshd -t` 语法校验通过；所有 `tun_*` shell = `/usr/sbin/nologin` ✅

> 测试方法说明：早期两轮用「本地监听端口是否接受连接」判定，属**误报**——本地监听恒接受，不触发服务端 `permitopen`。最终改为读取实际转发到的目标服务返回字节数，结论才成立。
