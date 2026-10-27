# Codex 接入操作说明（root 私钥直连）

- 生成：2026-10-22（Asia/Shanghai）　编制：WorkBuddy　对象：Codex
- 前提：owner 已选择「直接交 root 私钥」方式授权
- **本文件不含私钥、口令、令牌正文**。私钥由 owner 在本地从源文件复制，经安全渠道交给 Codex。
- 本说明只覆盖**服务器系统层 + 数据库层**；**阿里云控制台层不在其中**，见第八节。

---

## 一、接入参数

| 项 | 值 |
|---|---|
| 主机 | `39.104.201.10`（阿里云 ECS） |
| 端口 | `22`（TCP） |
| 用户 | `root` |
| 认证 | ed25519 **公钥认证**（服务器 `PasswordAuthentication no`，**不支持密码登录**） |
| 客户端 | 任意 OpenSSH 客户端 |

## 二、主机公钥指纹（首次连接必须核对，防中间人）

- ED25519：`SHA256:Fl32wXdN3R83/iIk6sGHWZ7OKBRs106guxvocHWfDWQ`
- RSA(3072)：`SHA256:aJBh1eoaAF8LfibmEbiZ+12BWcb7m3y0GY4VEQz+EC8`

> 指纹不符立即停止连接，**不要**自动接受新指纹、不要反复试密钥。
> 该指纹已经过 `ssh-keyscan` 与 owner 本机 `known_hosts` 双向比对，结果为 MATCH（见同目录《脱敏只读证据.txt》证据 2）。

## 三、私钥获取与权限（关键）

- owner 本机源路径：`C:\Users\33847\WorkBuddy\2026-10-15-20-06-39\deploy\keys\site_ed25519`
- 由 owner 复制文件内容后交 Codex；WorkBuddy 不得在聊天或共享区输出正文。
- **Linux / macOS 使用前必须执行**：`chmod 600 <私钥文件>`。
  该文件在 owner 本机权限为 `644`，Windows 下可用，但 OpenSSH 在 Linux/macOS 上会因
  `UNPROTECTED PRIVATE KEY FILE` **直接拒绝使用**。
- 建议 Codex 侧存放：`~/.ssh/cf_root_ed25519`

## 四、连接命令

```bash
# 连通性验证
ssh -i ~/.ssh/cf_root_ed25519 -o ConnectTimeout=10 root@39.104.201.10 "hostname; mysql --version; systemctl is-active mysql"

# 交互式
ssh -i ~/.ssh/cf_root_ed25519 -o ConnectTimeout=10 root@39.104.201.10
```

## 五、数据库访问（两种方式）

**方式 A — 已在服务器上（root shell 内）**
```bash
mysql -u root            # auth_socket 认证，无需口令
mysql -u root -e "SHOW DATABASES;"
```
> 角色口令存放于 `/etc/cf-mcp/env`（权限 600，root 可读）：`CF_ADMIN_PASS` / `CF_APP_PASS` / `CF_BACKUP_PASS` / `CF_READ_PASS`。**不要把口令写进共享区或聊天。**

**方式 B — 从本地经隧道（不需要 shell 亦可）**
```bash
ssh -N -L 13306:127.0.0.1:3306 -i ~/.ssh/cf_root_ed25519 root@39.104.201.10
# 另开终端
mysql -h 127.0.0.1 -P 13306 -u cf_admin -p
```

## 六、红线与执行纪律（必须遵守）

- **未获指派不得自行施工**：当前看板无指定给 Codex 的「执行中」施工任务。
- 本次及后续无明确指派时：不建业务表（等指挥方合并版 `init.sql`）、不导入 DDL、不 DROP 现有库表、不改账号或口令、不安装依赖、不重启服务、不调整网络/安全组、不迁移数据、不新增账号或密钥。
- 严格串行：不并行施工、不启动子 agent、不向其他 AI 派活；不修改任务看板与任务书。
- 重试纪律：未知错误重试间隔 ≥30 秒、同一问题最多 3 次，先做只读排查；仍失败则报原始错误与已试方案。
- 不把口令、私钥、令牌写入共享区或聊天；共享区只记配置项名称与获取方式。
- 如实报告：没做的写「未做+原因」，失败贴错误原文，不把旧结论当实测通过，不美化输出。

## 七、服务器现状要点（2026-10-22 实测，供接入后核对）

- Ubuntu 24.04.5 LTS，内核 `6.8.0-139-generic`；MySQL `8.0.46-0ubuntu0.24.04.4`，服务 `active`
- 监听：`127.0.0.1:3306`、`127.0.0.1:33060`；**8000 无监听，无 MCP 服务**
- 库：`cf_workbench`（**0 张表**）、`new_project`（0 张表）+ 系统库
- 账号：`cf_admin`/`cf_read`/`cf_app`/`cf_backup`/`proj_admin`/`root`/`debian-sys-maint`，**全部 localhost，无 `%` 账号**
- 参数：`innodb_buffer_pool_size=512M`、`max_connections=100`、`bind_address=127.0.0.1`
- 时区：`system_time_zone=CST`、`time_zone=SYSTEM`（**非 UTC**；应用侧要 UTC 须显式 `SET time_zone='+00:00'`）；`sql_mode` 含 `STRICT_TRANS_TABLES`
- 内存：total 1.7Gi，available 约 831Mi；swap 1.0Gi（未用）
- 遗留：`proj_admin@localhost` 仍持 `new_project.*` 的 `ALL PRIVILEGES`（待 owner 裁定，未清理）

## 八、三层权限说明（重要，避免误判授权范围）

| 层 | 本私钥是否覆盖 | 说明 |
|---|---|---|
| ① 数据库层 | ✅ 覆盖 | root 可直连 MySQL，也可读 `/etc/cf-mcp/env` 取得角色口令 |
| ② 服务器系统层 | ✅ 覆盖 | 装包、改配置、重启服务、建账号等均可 |
| ③ **阿里云控制台层** | ❌ **不覆盖** | 安全组、ECS 规格/快照、RAM 等**只能**通过阿里云控制台或 API 操作。需 owner 创建 RAM 子账号并授予 AccessKey 才能给到；建议只给 `AliyunECSReadOnlyAccess` + 安全组相关权限，**不要给 AdministratorAccess** |

## 九、安全建议

1. root 私钥等同服务器最高权限，**不要粘贴到群聊、代码仓库、网页表单或任何第三方日志**。
2. **使用完毕后请通知 owner 轮换**：作废旧公钥、生成新密钥、更新 `authorized_keys`（WorkBuddy 可代执行，需 owner 明确授权）。
3. 若后续只需数据库操作，建议改用更低权限路径：`tun_admin` 隧道账号 + `cf_admin` 口令（无 shell、仅转发 3306），风险显著低于 root。
4. 接入后建议先跑一次只读自检（`hostname` / `mysql --version` / `systemctl is-active mysql`），确认连通与身份正确再开展任何工作。
