# WorkBuddy 服务器侧 · 交付归档（Codex 接手入口）

提交人：WorkBuddy（服务器侧执行者，本机 33847）
归档时间：2026-10-22 19:52 (GMT+8)
性质：**完整上下文归档**，供 Codex 接管服务器与 MySQL 维护。本轮无施工动作，仅归档与说明。

---

## 一、本目录有什么（建议阅读顺序）

| 序号 | 文件 | 内容 | 优先级 |
|---|---|---|---|
| 00 | `00_README_Codex入口.md` | 本文件，接手总览 | **先读** |
| 01 | `01_任务书04_环境核对与加固报告.md` | 千问办公外包任务书 04 的执行报告（四节格式） | 高 |
| 02 | `02_批复D14-D16_执行报告.md` | SSH 隧道零暴露方案 + 按角色建账号的落地报告 | 高 |
| 03 | `03_成员SSH隧道接入指南_可转发.md` | 给真人成员的接入说明（不含私钥，可直接转发） | 中 |
| 04 | `04_服务器交接包_完整上下文.md` | 服务器事实快照 + 红线 + 命令速查 + 待办 | **高** |
| 05 | `05_cf-tunnel.service` | 常驻隧道 systemd 服务文件（可直接落地） | 中 |
| 06 | `06_新服务器部署教程.md` | 另一台新机器从零部署网站的完整教程 | 低（背景） |
| 07 | `07_SSH角色账号与私钥_脱敏版.md` | 角色↔账号↔权限对应表、连接命令、私钥取用方式 | **高** |

同时，WB-SRV-001 任务成果在：
`D:\AI_Command_Workspace\交付\WB-SRV-001\WorkBuddy\v1\`
（含「接入与现状核验.md」「脱敏只读证据.txt」「Codex接入操作说明.md」「Codex公钥接入_简化方案.md」）

---

## 二、服务器接入：请给我一行公钥（owner 零操作）

账号 **`codex_ops` 已建好并验证**，当前 `authorized_keys` 为 **0 行 = 谁也登不进去**（安全待命）。

| 项 | 值 |
|---|---|
| 主机 / 端口 | `39.104.201.10` / `22` |
| 账号 | `codex_ops`（shell `/bin/bash`） |
| 权限 | `sudo NOPASSWD: ALL` → 装包、改配置、重启、建账号，**能力等同 root** |
| 认证 | 仅公钥（服务器 `PasswordAuthentication no`） |

**接入只需两步：**
1. 本地生成密钥对：`ssh-keygen -t ed25519 -C "codex-ops" -f ~/.ssh/codex_ops`
2. 把 `~/.ssh/codex_ops.pub` **那一行公钥**放进 `D:\AI_Command_Workspace\收件箱\codex_ops.pub`（或直接交给 WorkBuddy）

> 公钥不是机密，可放心传递。WorkBuddy 收到后写入服务器即生效。

**首次连接必须核对主机指纹**（防中间人，不符即停止）：
- ED25519：`SHA256:Fl32wXdN3R83/iIk6sGHWZ7OKBRs106guxvocHWfDWQ`
- RSA：`SHA256:aJBh1eoaAF8LfibmEbiZ+12BWcb7m3y0GY4VEQz+EC8`

接入命令：
```bash
chmod 600 ~/.ssh/codex_ops
ssh -i ~/.ssh/codex_ops codex_ops@39.104.201.10
```

> **为什么比交 root 私钥好**：root 是共享身份，出事分不清操作者，且吊销要换整把密钥；`codex_ops` 独立可审计，**删一行公钥即收回权限**，不动 owner 现有 root 私钥。

---

## 三、服务器现状快照（2026-10-22 实测，非沿用旧报告）

| 项 | 实测值 |
|---|---|
| 系统 | Ubuntu 24.04.5 LTS，x86_64 |
| MySQL | 8.0.46，`systemctl is-active mysql` = active |
| 3306 / 33060 监听 | **仅 `127.0.0.1`**（未绑 0.0.0.0） |
| 8000 监听 | **无**（MCP Server 尚未部署） |
| 库 | `cf_workbench`（**0 张表**）、`new_project`（0 张表） |
| MySQL 账号 | `cf_admin` / `cf_read` / `cf_app` / `cf_backup` / `proj_admin` —— **全部 localhost，无任何 `%` 账号** |
| 排序规则 | `utf8mb4_0900_ai_ci`（服务端 `collation_server`） |
| 时区 | `system_time_zone=CST`、`time_zone=SYSTEM`（**非 UTC**）→ 应用侧需显式 `SET time_zone='+00:00'` |
| `sql_mode` | 含 `STRICT_TRANS_TABLES` |
| 调优 | `innodb_buffer_pool_size`=512M、`max_connections`=100、swap 1.0Gi（未使用） |
| 内存 | available ≈ 831Mi（总 1.7Gi）+ 1G swap |
| 磁盘 | 剩余约 33G |
| 其他服务 | `nginx`（站点 `jdjrkj.online` + 班级事务后台 `affairs-api`）active |

**遗留项**：`proj_admin@localhost` 仍持有 `new_project.*` 的 `ALL PRIVILEGES`（历史账号，未处理，等裁决）。

---

## 四、项目红线（必须遵守）

1. **不建业务表、不导入 DDL/数据**——合并版 `init.sql` 由指挥方统一发布（当前阻塞中）。
2. 不 `GRANT ALL`、不给应用用 root、不建 host 为 `%` 的账号、不监听公网端口（3306/8000）。
3. 不上传任何口令、私钥、令牌到聊天或共享区。
4. 已存在的同名库/表一律 **不 DROP**。
5. 严格**串行施工**：不自行抢任务、不启动子 agent、不向其他 AI 派活。
6. 如实报告：未做的写「未做 + 原因」，失败的贴原文，不美化输出。
7. 重试纪律：间隔 ≥30 秒，同一问题最多 3 次，超限停下报告。
8. 修改使用明确指定的副本，不擅自搬迁、删除或部署。

---

## 五、当前阻塞与待裁决（需 Codex / owner 决定）

1. **合并版 `init.sql` 未发布** → 建表阻塞（最高优先级）。
2. `proj_admin@localhost` 去留（保留作 owner 总控 / 删除统一到 `cf_admin`）。
3. `new_project` 空库处置（保留 / 改名 / 删除）。
4. `pymysql` 安装授权（MCP Server 连库必需，目前未装）。
5. pip 必须带 `--trusted-host mirrors.cloud.aliyuncs.com`（阿里云内网镜像为 HTTP，pip 默认拒绝），否则下载失败。
6. **阿里云安全组只能在控制台/API 层修改**，SSH 权限覆盖不到 → 需 owner 建 RAM 子账号给 AccessKey（建议只给 ECS 只读 + 安全组权限，勿给 AdministratorAccess）。
7. ICP 备案状态无法在服务器侧确认（若走对外 HTTPS 需核实）。
8. Nginx 反代 `/mcp` + Bearer 令牌方案**已设计但暂缓执行**（演示阶段走隧道即可），思路保留勿删。

---

## 六、本机（WorkBuddy）能力边界，如实报告

**能做**：本地 C/D 盘读写、shell 执行、**SSH 操作 `39.104.201.10`（root + ed25519 密钥，已多次实测）**、联网检索/抓取、生成文档与代码。

**不能做**：
- 操作千问平台（无内部接口/连接器）。
- 修改阿里云控制台/安全组（无 AccessKey，SSH 无法替代）。
- 在共享区存放私钥/口令明文（纪律禁止）。

**已披露的历史问题**：早期若干轮 SSH 使用了 `-o StrictHostKeyChecking=no`（关闭主机指纹校验），不符合安全纪律。WB-SRV-001 起已改为严格校验，并补做 `ssh-keyscan` 指纹比对，结果与本机 known_hosts **一致（MATCH）**，无中间人迹象。后续一律严格校验。

---

## 七、脱敏声明

- 本目录 **8 个文件已通过私钥泄漏自检**（扫描 OpenSSH 私钥 PEM 头标记，无真实私钥命中）。
- 含私钥原文的 owner 版仅存于本机 `C:\Users\33847\WorkBuddy\2026-10-15-20-06-39\cf_ssh_credentials.md`，**未复制进共享区**。
- MySQL 口令仅存于服务器 `/etc/cf-mcp/env`（权限 600），**未写入任何共享文件**。
- 需要私钥或口令时，由 owner 经安全渠道单独提供，或通过本文档第三节的 `codex_ops` 公钥方案免密接入。
