# WorkBuddy 服务器侧执行者 登记 v1

> 保存路径：D:\AI_Command_Workspace\项目登记\WorkBuddy_服务器侧执行者_33847_登记_v1.md
> 对应看板任务：REG-001（各AI身份与存量任务登记）。本轮**仅登记，不施工**。
> 本文件不含任何口令、密钥、令牌明文；仅记录配置项名称与获取方式。

- **AI名称与平台**：
  WorkBuddy（CodeBuddy）Agent，运行在用户 Windows 本机的桌面会话中。
  本机会话工作区：`C:\Users\33847\WorkBuddy\2026-10-15-20-06-39`
  建议称呼（供看板引用）：**WorkBuddy-服务器侧执行者**

- **当前日期时间与时区**：
  2026-10-22 19:23:50 +0800（Asia/Shanghai）

- **能否实际读取 D:\AI_Command_Workspace**：
  **能。** 已实际读取到全文的 4 个文件：
  `总控入口.md`、`AGENTS.md`、`任务看板.md`、`项目登记\登记模板.md`

- **能否实际写入本目录（仅在自己登记文件中验证）**：
  **能。** 本文件即为写入验证；写入后将回读确认内容一致。

- **是否已阅读 总控入口.md / AGENTS.md / 任务看板.md**：
  **是**（三个入口均已读，另加读登记模板）。
  已知要点：Codex 为协调与验收负责人、用户保留最终决定权；严格串行（并发上限 1，当前无活动施工任务）；其他 AI 不覆盖/不修改指令目录与总看板，只向自己的交付目录与登记文件新增；登记和只读查阅不算施工；无活动任务时只登记报告、等待指派。

- **可操作载体（只报告实际能力）**：
  - 本地文件系统：**能**。C 盘、D 盘可读写（对桌面/下载等个人目录的删除、批量改名、清理等破坏性操作受安全策略约束，需用户确认后才执行）。
  - 本地 shell：**能**。可执行 Bash / PowerShell 命令。
  - 服务器：**能**。可用 ed25519 私钥经 SSH 以 root 登录 `39.104.201.10`（阿里云 ECS，Ubuntu 24.04.5），本会话内已多次实测执行并回传输出。
  - 联网检索 / 网页抓取：**能**。
  - 千问平台：**不能**。我没有千问办公的内部接口或连接器，无法读写其表格、也无法触发其能力；因此 CF-002（千问平台最小能力实测）一类任务**我无法承担**，需指派给千问办公侧。
  - 浏览器：本机存在浏览器自动化技能可调用，但**本轮未实测**，故不声称可用。

- **当前项目路径或平台标识**：
  - 本机会话工作区：`C:\Users\33847\WorkBuddy\2026-10-15-20-06-39`
  - 项目主目录：`D:\CashflowRiskWorkbench`（**本轮尚未读取、未搬迁、未改动**）
  - 服务器：`39.104.201.10`（阿里云 ECS，Ubuntu 24.04.5，MySQL 8.0.46）

- **原来接到的任务、来源、状态**：
  - 来源：① 用户直接指派；② 千问办公下发的《外包任务书 04》；③ 《批复 D14-D16》。
  - 任务：服务器侧 MySQL 环境核对与加固、SSH 隧道零暴露、按角色建账号（**明确不含建业务表**）。
  - 状态：**已完成并停在最近安全边界，等待 init.sql**。
  - 已完成事实（均为服务器实测，非推断）：
    - MySQL 8.0.46，`active`；调优 `innodb_buffer_pool_size=512M`、`max_connections=100`，另建 1G swap；`bind_address=127.0.0.1`。
    - 库 `cf_workbench`（utf8mb4 / `utf8mb4_0900_ai_ci`），**当前 0 张表**。
    - 四个 MySQL 角色账号 `cf_admin` / `cf_read` / `cf_app` / `cf_backup`，**全部 localhost，无任何 `%` 账号，无 GRANT ALL，非 root**。
    - 五个受限 SSH 隧道账号 `tun_admin` / `tun_read` / `tun_app` / `tun_backup`（permitopen `127.0.0.1:3306`）与 `tun_mcp`（permitopen `127.0.0.1:8000`），shell 均为 `/usr/sbin/nologin`，仅端口转发，已实测越权转发被拒、shell 被拒。
    - 3306 / 33060 **仅绑 127.0.0.1**；**未建任何业务表、未 DROP 任何库表、未开放 3306/8000 公网**。
  - 凭据存放（**仅记名称与获取方式，不含明文**）：MySQL 角色口令存服务器 `/etc/cf-mcp/env`（权限 600）；隧道私钥存 `/etc/cf-mcp/ssh_keys/*_key`（权限 600）；历史遗留 `/root/.mysql_credentials`（600）。

- **最近已经修改的文件、是否有未完成写入**：
  - 服务器端最后写入：`/etc/cf-mcp/ssh_keys/*`（5 组密钥，600）、各 `tun_*` 的 `~/.ssh/authorized_keys`（含 permitopen 限制）、`/etc/cf-mcp/env`（追加 cf_read 条目）。
  - 本地新增交付物（均在 `C:\Users\33847\WorkBuddy\2026-10-15-20-06-39\` 下）：
    `cf_mysql_report.md`、`cf_批复执行报告_D14-D16.md`、`cf-tunnel.service`、
    `cf_ssh_credentials.md`（owner 专用，含私钥）、`cf_ssh_队友交付.md`、`cf_服务器交接包_给GPT.md`
  - **当前无进行中的文件写入，也无进行中的数据库事务**；已停在安全边界（下一动作为执行建表，须先拿到 init.sql）。

- **当前阻塞或需要授权的范围**：
  1. **合并版 init.sql 尚未发布** → 建表阻塞。按红线我不自行建业务表。
  2. **待裁定事项**：`proj_admin@localhost` 去留、`new_project` 空库处置（保留/改名/删除，当前未 DROP）、`pymysql` 安装授权、ICP 备案状态确认。
  3. **阿里云安全组**：只能在控制台/API 修改，服务器侧无权操作；需用户操作，或明确授予 AccessKey 授权（当前 3306/8000 未放行，且 bind 层已保证公网连不上）。
  4. **千问平台能力**：我无操作能力，相关实测类任务需指派给千问办公侧。
  5. 服务器 root 私钥属高敏感凭证，任何对外/对第三方 AI 的交付需用户明确授权，并建议事后轮换。

- **等待指派时已保存的成果路径**：
  - 本地：`C:\Users\33847\WorkBuddy\2026-10-15-20-06-39\` 下 6 个交付文件（见上）。
  - 服务器：`/etc/cf-mcp/env`、`/etc/cf-mcp/ssh_keys/`、`/etc/mysql/mysql.conf.d/zz-tuning.cnf`、`/tmp/cf-mysql-info.txt`（只读采集快照）。
  - 项目主目录 `D:\CashflowRiskWorkbench`：**未改动**。

- **遵守声明**：
  本轮仅完成登记，**未启动任何业务施工**；未自行抢任务、未向其他 AI 派活、未启动子 agent；未修改总看板与指令目录；本文件不含口令/密钥/令牌明文；未执行部署、未对外发送、未搬迁或删除任何现有项目文件。

---

## 追加：WB-SRV-001（Codex 指派，2026-10-22 19:36 起）

- 任务：《WB-SRV-001 服务器与MySQL只读接入交接 v1》，指派 Codex、验收 Codex。范围：**仅只读核验与非敏感报告**。
- 已交付（只在我的交付目录新增，未改看板/任务书）：
  - `D:\AI_Command_Workspace\交付\WB-SRV-001\WorkBuddy\v1\接入与现状核验.md`
  - `D:\AI_Command_Workspace\交付\WB-SRV-001\WorkBuddy\v1\脱敏只读证据.txt`
- 状态：**等待 Codex 验收**。本轮严格只读——未建表、未改账号口令、未装依赖、未重启服务、未调网络、未新增账号或密钥、未迁移数据。
- 接入入口：用户 `root`、端口 22、ed25519 公钥认证；私钥本机路径 `C:\Users\33847\WorkBuddy\2026-10-15-20-06-39\deploy\keys\site_ed25519`（**正文不导出、不复制进共享区**），指纹 `SHA256:POqJ0H7PVmG5DCRTc5QhWx/9ooHc0xzV9qeUcPib2fs`。
- 主机指纹（供首次连接校验）：ED25519 `SHA256:Fl32wXdN3R83/iIk6sGHWZ7OKBRs106guxvocHWfDWQ`；RSA `SHA256:aJBh1eoaAF8LfibmEbiZ+12BWcb7m3y0GY4VEQz+EC8`。本轮经 `ssh-keyscan` 与本机 `known_hosts` 比对，**MATCH**；并已改用严格主机校验（此前若干轮曾使用 `StrictHostKeyChecking=no`，已在报告中如实披露并改正）。
- 实测要点：`cf_workbench` **0 张表**；`cf_read` 仅 SELECT；buffer_pool 512M / max_conn 100 / swap 1G 均生效；`time_zone=SYSTEM`（CST，非 UTC，应用侧须显式 `SET time_zone='+00:00'`）；8000 未监听、无 MCP 服务；`proj_admin` 遗留仍在（持 `new_project`.* 的 ALL）。
- **接入缺口（供 Codex 判断）**：直连必须持有私钥正文，只能由 owner 经安全渠道提供或在 owner 本机执行；替代方案为授权建受限 SSH 账号，或复用 `tun_admin` + `cf_admin` 做库层维护（不能做系统级运维）。

---

## 追加：WB-ENG-001 统一数据库与工具契约（2026-10-22 20:00 起，已交付暂停）

- 任务：后端主力队列第 1 包；按 CMD-002 流程，交付后暂停 → Codex 冻结 → DeepSeek 独立审核（DS-AUD-001）→ Codex 确认。审核通过前不启动 WB-ENG-002。
- 交付目录：`D:\AI_Command_Workspace\交付\WB-ENG-001\WorkBuddy\v1\`，含：
  - `candidate/sql/init_v1.1.sql`（11 表裸 CREATE + 结构预检 + 10 视图；不含 GRANT/口令）
  - `candidate/sql/grants_admin_view_候选.sql`（cf_admin 缺 CREATE VIEW/SHOW VIEW 的最小权限变更候选，**未批准未执行**）
  - `candidate/docs/千问办公_MySQL_MCP工具定义_v1.1.json`（14 工具 Schema）
  - `candidate/docs/千问办公_MySQL_MCP对接协议_v1.1.md`
  - `tools/validate_contract.py` + `tools/requirements.txt`（jsonschema 4.26.0，隔离 venv）
  - `test-output/validate_output.txt`（实测输出：66 PASS / 0 FAIL / 1 SKIP / 2 BLOCKED）
  - `README.md` / `改动清单.md` / `测试报告.md` / `未决项.md` / `SHA256SUMS.txt`
- 完整性：Codex《交付完整性检查_v1.md》所列 4 件缺件已全部补齐（改动清单/测试报告/未决项在核对时点之后完成，SHA256SUMS.txt 于 20:21 生成）。
- 纪律遵守：源项目 `D:\CashflowRiskWorkbench` 全程只读未改；未连接服务器、未执行任何 DDL；未建业务表；未启动子 agent；未启动下一包。
- 部署阻塞（交付中已列明）：U-01 company_id/tenant_id 语义未裁决；U-06 cf_admin 视图权限候选待批准；U-07 真实 MySQL 执行留 WB-ENG-006。
- 当前无进行中写入或事务。

## 追加：WB-FIN-001 财务公式与计算口径梳理（2026-10-22 20:32 起，已交付暂停）

- 触发：用户指派"优先把财务计算理清楚，后端下一包先别开工"；Codex 已发《WB-FIN-001_财务公式与计算口径梳理_v1.md》。
- 交付目录：`D:\AI_Command_Workspace\交付\WB-FIN-001\WorkBuddy\v1\`，含：财务公式与口径总表.md（25 条公式 F-01—F-25）、待确认问题.md（P-01—P-14）、手算与边界用例.csv（57 行，与脚本同源）、verify_financial_formulas.py（仅标准库 decimal，离线）、校验结果.txt、README.md、SHA256SUMS.txt。
- 实测结果：**57 项 PASS 46 / FAIL 0 / BLOCKED 11**（BLOCKED 均为规则未批准或无定义，未判为通过）。CSV↔脚本交叉核对 `CSV_CROSSCHECK: OK`。
- 状态分布：已批准 13 条 / 批准+待确认 9 条 / 完全待裁决 3 条（1.45、Myer、13 周）；**全部千问表格公式标"待平台验证"，不声称千问已能运行**。
- 新登记缺陷：D-01（v8 §4.3 健康度报告样例与自身公式三处不符）、D-02（看板 f.buffer 硬编码）、D-03（看板 13 周序列与同页 M=500 不勾稽）。
- 高危待业务确认（直接改灯）：P-01 刚性支出无定义、P-09 已验证到账是否已含现金余额（重复计入会使红灯变绿灯）、P-10 Q 求和粒度与 D 归一化口径两套写法并存。
- 纪律遵守：源项目 `D:\CashflowRiskWorkbench` 全程只读未改；**未连接服务器、未建表、未改配置、未改原始表格**；未启动子 agent；未启动 WB-ENG-002；交付内不含口令/密钥/令牌。
- 当前无进行中写入或事务；等待 DeepSeek 独立审核结论。

## 2026-10-23 追加 · WB-AGENT-003（当前唯一施工任务）

- **接单**：入口 `D:\AI_Command_Workspace\333.md`，用户转发"读333"后回执开工。只做制造业 Agent 外围工程（非算法），接替 WB-MFG-001 中不依赖主算法的部分；旧现金流公式/输入部分保留待合并。
- **交付**：`D:\AI_Command_Workspace\交付\WB-AGENT-003\WorkBuddy\v1\`（24 文件）。A 四类内部能力接口、B 请求流程与守卫、C 保存回执与精确回查、D 提示词 v3 + 千问配置操作单、E 独立测试、F 三队友接口映射。继承 CX-AGENT-002 冻结内容**未改一个字节**（diff 一致）。
- **实测**：`python run_tests.py` → 44 项全通过、退出码 0（23 继承 + 21 新增）；输出 `test-output/selftest_v1.txt`。
- **三项状态**：离线通过 44 ／ 真实千问平台执行 **0** ／ 服务器部署 **未做过**。综合写"离线准备完成，平台/部署阻塞"，**不写全链路已跑通**。
- **阻塞 U1—U9**：平台绑定（读表/公式/MCP 存储/精确回查）、真实 MySQL 闭环、主算法、真实制造业数据、MEM-IMPORT-002、平台 V1—V4 验收——均需 X 或队友，详见交付内 `docs/未实现清单.md`。
- **已停下**，等 DeepSeek（DS-AUD-AGENT-003）审核与 X 检查；返工在 v2 另存，不覆盖 v1；最终放行由 Codex 登记。
- 本轮未连服务器、未改配置、未建表、未部署、未 git push、未复制密钥到共享区；未改原 xlsx；D8 保持待核；未启动子 agent。

### 追加：WB-ENG-001 v2 / WB-FIN-001 v2 返工（2026-10-23 19:05）
- **WB-ENG-001 v2**：`交付\WB-ENG-001\WorkBuddy\v2\`（13 文件）。修 R-01（log_feedback 金额条件必填、可空）、R-02（audit_id 十进制数字串 + 协议示例改 1024）、R-04（v_template_published_latest 同租户 NOT EXISTS + 并列确定性）、R-06—R-12 七项；R-10 删 CREATE DATABASE 并新增 U-08；R-03/R-05 **保持待裁决未自行定案**。实测 85 项 = **PASS 82 / FAIL 0 / SKIP 1 / BLOCKED 2**，退出码 0。
- **WB-FIN-001 v2**：`交付\WB-FIN-001\WorkBuddy\v2\`（8 文件）。修 P1（六条千问公式列加空值守卫 + C56—C62 空白单元格对照用例）、P2-1—P2-5、P3 八组；新增 P-15；状态改三态。实测 74 项 = **PASS 68 / FAIL 0 / BLOCKED 6**，CSV 交叉核对 OK。
- **两包 v1 均完整保留**（ENG 12 文件 / FIN 7 文件），未覆盖。
- **提交**：`D:\AI_Command_Workspace\445_提交Codex审核_WB-ENG-001与WB-FIN-001_v2.md` —— 用户授权"交 Codex 直接审核；不通过请 Codex 直接修改；修改完直接入库"。
- **入库前置待 Codex 裁决**：① cf_admin 缺 CREATE VIEW/SHOW VIEW（建议先批候选授权，不用 root）；② cf_workbench 已存在且 collation 正确（U-08 已满足）；③ R-03/R-05 未裁决不阻塞建表但需知悉。
- **当前状态：等 Codex 审核结论**。未执行任何 DDL、未建表、未部署、未改 xlsx、未连千问；交付无凭据。

### 追加：MEM-EVIDENCE-001 v1 候选（2026-10-24 19:25）
- **接单**：用户 2026-10-24 口头指派"从最难、能独立完成、完全没做的任务开始"。核查看板后选定 MEM-EVIDENCE-001（进阶第二档，可靠结果存储与故障恢复）；MEM-CALC-001 因看板注明"待合并、不重复并行施工"未动。看板"执行中"登记待 X 转达 Codex（交付内 Q1）。
- **交付**：`D:/AI_Command_Workspace/交付/MEM-EVIDENCE-001/WorkBuddy/v1/`（366 文件）。SQLite WAL 事务证据存储 + save/get/history/verify-store/selftest CLI；四元幂等键、确定性 record_id、非 success 分流诊断表、故障注入（commit 前/后）、busy_timeout 不无限重试、路径越界拒绝、SQL 参数化、输出脱敏。
- **实测**：tests/run_tests.py 30 用例 **PASS 30 / FAIL 0**，退出码 0；selftest 11 项全过；/tmp 解压副本照 README 复现 PASSED；发包 24 源件哈希复核一致。前两轮失败证据（runner bug、夹具勾稽、并发建库竞争）如实保留 test-output/。
- **未做**：未连服务器/MySQL/千问、未部署、未 git push、未改源件与他人交付；生产认证未接线（trust_boundary.md 如实声明检测边界）。
- **已停下**，待 X 检查 → DeepSeek 独审 → Codex 登记；返工升 v2 不覆盖 v1。
