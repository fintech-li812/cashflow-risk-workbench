# Codex 公钥接入 · 简化方案（owner 零本地操作）

- 生成：2026-10-22 19:49（Asia/Shanghai）　编制：WorkBuddy
- 目标：让 Codex 接入 `39.104.201.10`，**全程不需要 owner 复制/传递任何私钥**
- 原理：Codex 只需提供**公钥**（一行文本，非机密），WorkBuddy 负责装到服务器账号上

---

## 一、账号已就绪（等你提交公钥）

| 项 | 值 |
|---|---|
| 主机 | `39.104.201.10` |
| 端口 | `22` |
| 账号 | **`codex_ops`** |
| shell | `/bin/bash` |
| 权限 | `sudo` **NOPASSWD: ALL**（可执行 root 级操作：装包、改配置、重启服务、建账号等） |
| 当前状态 | `authorized_keys` **0 行 → 无人可登录**（安全待命） |
| 家目录 | `/home/codex_ops`，`.ssh` 权限 700、`authorized_keys` 权限 600、属主 `codex_ops` |

> 该账号是**独立身份**：操作可审计、可单独吊销，且不影响 owner 的 root 私钥。
> 能力上等同 root（sudo NOPASSWD），但比"共享 root 私钥"更安全——删除一行公钥即可立即收回权限。

---

## 二、Codex 只需做两步

**第 1 步 · 生成密钥对**（若已有 ed25519 公钥可直接复用）
```bash
ssh-keygen -t ed25519 -C "codex-ops" -f ~/.ssh/codex_ops
# 生成 ~/.ssh/codex_ops（私钥，自己留好）与 ~/.ssh/codex_ops.pub（公钥，提交给我）
```

**第 2 步 · 把公钥交给 WorkBuddy**（三选一，公钥非机密，可公开传递）
- **方式 A（推荐，owner 完全不用动手）**：把公钥内容写入共享区文件
  `D:\AI_Command_Workspace\收件箱\codex_ops.pub`
- **方式 B**：把公钥一行文本贴在回报里（形如 `ssh-ed25519 AAAAC3Nza... codex-ops`）
- **方式 C**：只给指纹不够——必须给完整公钥行，否则无法写入 `authorized_keys`

WorkBuddy 收到公钥后会立刻写入服务器并回报"可连接"，同时回传校验结果。

---

## 三、拿到"可连接"回复后的连接命令

```bash
ssh -i ~/.ssh/codex_ops -o ConnectTimeout=10 codex_ops@39.104.201.10
# 自检
ssh -i ~/.ssh/codex_ops codex_ops@39.104.201.10 "whoami; sudo -n true && echo SUDO_OK; mysql --version"
```

**首次连接必须核对主机指纹**（防中间人，不符立即停止、不自动接受）：
- ED25519：`SHA256:Fl32wXdN3R83/iIk6sGHWZ7OKBRs106guxvocHWfDWQ`
- RSA(3072)：`SHA256:aJBh1eoaAF8LfibmEbiZ+12BWcb7m3y0GY4VEQz+EC8`

---

## 四、权限边界（重要）

| 层 | 是否覆盖 |
|---|---|
| 服务器系统层（装包 / 改配置 / 重启 / 建账号） | ✅ 覆盖（sudo NOPASSWD） |
| 数据库层（MySQL root 或角色账号） | ✅ 覆盖（`sudo mysql -u root`；角色口令在 `/etc/cf-mcp/env`，600） |
| **阿里云控制台层（安全组 / ECS / RAM）** | ❌ **不覆盖** —— 需 owner 创建 RAM 子账号并授予 AccessKey |

## 五、吊销方式（owner 随时可让我执行）
1. 仅收回登录：删除 `/home/codex_ops/.ssh/authorized_keys` 中对应公钥行
2. 收回 sudo：删除 `/etc/sudoers.d/codex_ops`
3. 彻底删除账号：`userdel -r codex_ops`

## 六、红线（接入后必须遵守）
- 无明确指派不得自行施工；当前看板无指定给 Codex 的「执行中」任务。
- 不建业务表（等 `init.sql`）、不 DROP 库表、不改账号口令、不装依赖、不重启服务、不调安全组、不迁移数据。
- 严格串行，不并行、不派活、不启子 agent；不改看板与任务书。
- 重试间隔 ≥30 秒、同一问题最多 3 次。
- 不把口令/私钥写进共享区或聊天（**本方案下 owner 无需传递任何私钥**）。
- 如实报告：未做写「未做+原因」，失败贴原文。

## 七、若 Codex 无法生成密钥对
退回备选：由 WorkBuddy 生成密钥对，但此时**私钥需要传递给 Codex**——
按纪律我不能写入共享区或聊天，只能由 owner 在本地复制转交（这会重新引入 owner 操作）。
因此**强烈建议采用本公钥方案**。
