# CashflowRiskWorkbench · 数据库/隧道访问指南（给团队成员）

> 本项目的 MySQL 与 MCP **不对公网开放**，所有人都必须走 **SSH 隧道** 访问。  
> 你不需要服务器 IP 的白名单，也不需要直连 3306/8000——只要拿到属于你角色的 **SSH 私钥** 和 **MySQL 角色密码**（向 owner 索取），就能从任意网络连上。
>
> ⚠️ 私钥文件权限必须是 600：`chmod 600 tun_xxx_key`，否则 ssh 会拒绝使用。

---

## 一、你能拿到的东西（按角色）

| 你的角色          | SSH 隧道账号     | 能转发的目标           | 连上后用的 MySQL 账号 | 权限            |
| ------------- | ------------ | ---------------- | -------------- | ------------- |
| 包A / 牛马Y（管理员） | `tun_admin`  | `127.0.0.1:3306` | `cf_admin`     | 读写+建表改表等      |
| 牛马X / 包B（只读）  | `tun_read`   | `127.0.0.1:3306` | `cf_read`      | 仅 SELECT      |
| 应用机（非人）       | `tun_app`    | `127.0.0.1:3306` | `cf_app`       | SELECT/INSERT |
| 备份机（非人）       | `tun_backup` | `127.0.0.1:3306` | `cf_backup`    | 备份相关          |
| 千问办公（连 MCP）   | `tun_mcp`    | `127.0.0.1:8000` | （不连 MySQL）     | 连 MCP Server  |

> 公钥指纹（用于确认 owner 给你的私钥无误，可选核对）：
>
> - `tun_admin`  `AAAAC3NzaC1lZDI1NTE5AAAAIBusBsigsrp7073g94RdFu9+5iX/1HBaAkVf4xT0Oq/N`
> - `tun_read`   `AAAAC3NzaC1lZDI1NTE5AAAAIGYvW5BYg7FIevDf9zIZKOmKu8ZkSY1hL8PgomZVTl+x`
> - `tun_app`    `AAAAC3NzaC1lZDI1NTE5AAAAIDlRJ4Smq6uhTRYQZwAZg/zgf3ktwCsPWRZX+Gdq6Vn8`
> - `tun_backup` `AAAAC3NzaC1lZDI1NTE5AAAAIDYtIAGCATeD6184Lwvcn+NLIZG8d0XsWeZJbGV2jwOM`
> - `tun_mcp`    `AAAAC3NzaC1lZDI1NTE5AAAAIBUmE7zL9QaWe58JaoYA5iYx24f8tScDqY87bm80BzZp`

---

## 二、使用步骤

**1. 把 owner 给你的私钥存为 `tun_你的角色_key`，并设权限**

```bash
chmod 600 tun_你的角色_key
```

**2. 开隧道（终端常开即可）**

```bash
# 管理员 / 只读 / 应用 / 备份 都是这条，只是账号和私钥不同：
ssh -N -L 13306:127.0.0.1:3306 -i tun_你的角色_key tun_你的角色@39.104.201.10

# 千问办公连 MCP 用这条（转发 8000）：
ssh -N -L 18000:127.0.0.1:8000 -i tun_mcp_key tun_mcp@39.104.201.10
```

**3. 连数据库（隧道开着时，另开终端）**

```bash
mysql -h 127.0.0.1 -P 13306 -u cf_你的角色 -p
# 输入 owner 给你的对应 MySQL 密码
```

**4. 千问办公 MCP 连接器地址**

```
http://127.0.0.1:18000/mcp
```

（隧道开着时填这个；暂不启用 Nginx/HTTPS/Bearer 那一档。）

---

## 三、让隧道常驻（断线自愈，推荐）

手点隧道一关，留痕就写不进库，所以建议用 `autossh` + systemd user service。  
示例（管理员，其余角色替换账号/私钥/本地端口即可）：

```ini
# ~/.config/systemd/user/cf-tunnel-admin.service
[Unit]
Description=CF Workbench SSH tunnel (admin)
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/autossh -M 0 -o "ServerAliveInterval=30" -o "ServerAliveCountMax=3" \
  -N -L 13306:127.0.0.1:3306 -i %h/.ssh/tun_你的角色_key tun_你的角色@39.104.201.10
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now cf-tunnel-admin.service
systemctl --user status  cf-tunnel-admin.service
```

---

## 四、安全须知

- 私钥**只在你本机**，不要上传群聊/仓库；丢了立即让 owner 作废并重发。
- 你**只能转发上表规定的端口**，尝试转发其它端口（如 22）会被服务器拒绝——这是设计内的限制，不是故障。
- 你**拿不到服务器 shell**（账号被限制为仅转发），也看不到别人的数据。
- 数据库当前是空库 `cf_workbench`，业务表由指挥方统一建，请勿自行建表/改表。
