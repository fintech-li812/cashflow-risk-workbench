# 返工通知 · WB-ENG-001 v1 → v2（DS-AUD-001 审核结论）

- 发起：DeepSeek Harness（独立审核员）
- 日期：2026-10-22 20:40（Asia/Shanghai）
- 状态：**审核意见，待 Codex 确认打回后生效**。DeepSeek 无派单权，不直接指挥作者；本文件由用户/Codex 转交。
- 审核对象：`D:\AI_Command_Workspace\交付\WB-ENG-001\WorkBuddy\v1`（12 份文件，SHAlist 见 `候选SHA256.csv`）
- 审核报告：`D:\AI_Command_Workspace\交付\DS-AUD-001\DeepSeek_Harness\v1\审核报告.md`

## 一、结论

打回。无 P0/P1；3 项作者必改（P2），2 项必须等 Codex 裁决后再动（R-03/R-05），7 项 P3 建议同批修。

先说明：本通知不改变任何业务口径。company_id 语义、K 阈值、Myer、1.45、FUSE、刚性支出、单位倍数一律不在此列，作者也不得借返工顺手改。

## 二、必改项（请直接修，修完逐条回执）

### R-01 log_feedback 与"pending 无实际值"冲突

- 现状：JSON `log_feedback.required` 同时强制 `predicted_value`、`actual_value`（`千问办公_MySQL_MCP工具定义_v1.1.json:304-317`，属性定义 `:368-377`）；DDL 两列可空（`init_v1.1.sql:155-156`）；协议规定缺乏实际数据时只能标 pending（协议 `:157`）。
- 实测：省略 `actual_value` → `'actual_value' is a required property`；显式 null 也被拒。
- 要求：二选一并写清：
  - A（推荐）：两金额移出 required，类型改 `["string","null"]`；服务端规则写进协议——`accurate`/`inaccurate` 必须有 actual_value，`pending` 必须无 actual_value（或 null）。
  - B：保留必填，明确 pending 反馈不得走本工具，并同步改协议与 DDL 语义（不得让调用方填 0 冒充）。
- 通过标准：pending 省略 actual_value 合法；accurate 缺 actual_value 被服务端拒绝；协议、Schema、DDL 三处说法一致。

### R-02 audit_id 类型不一致

- 现状：Schema 为自由字符串、maxLength 128、无 pattern（JSON `:402-407`）；DDL 为 `BIGINT UNSIGNED`（`init_v1.1.sql:152`，对应 `audit_log.id` `:107`）；协议示例返回 `"A-demo-001"`（协议 `:242`/`:249`）。
- 实测：`"A-demo-001"` 通过 Schema，但入不了 BIGINT。
- 要求：统一一种 ID 形态。若以 `audit_log.id` 为关联键：Schema 加 pattern `^[0-9]{1,20}$`，协议示例改成真实数字形态；若坚持业务串：DDL 改 VARCHAR 并说明与自增 id 的映射。三处必须一致。
- 通过标准：协议示例可直接回填 log_feedback；非数字 audit_id 被 Schema 拒绝。

### R-04 v_template_published_latest 未排除被替代版本

- 现状：视图只按 `publication_status='published'` + `MAX(effective_from)`（`init_v1.1.sql:588-598`），没有其余 8 个视图那样的 `NOT EXISTS(... supersedes_id ... AND s.tenant_id=...)`；同 `effective_from` 时返回多行。
- 影响：模板纠错后，省略版本号读取可能取到被替代的旧参数，或返回 2 行无法唯一确定。
- 要求：补同租户 `NOT EXISTS` 排除被替代行；对 `effective_from` 并列给出确定规则（例如 `ORDER BY p.id DESC LIMIT 1`，或新增 active 标记）；在 `validate_contract.py` 增加一条能覆盖"没有 NOT EXISTS 的视图"的断言。
- 通过标准：构造"旧行被替代""两版同 effective_from"两例，视图均只返回 1 行且为新行。

## 三、先不要动，等 Codex 书面裁决（R-03 / R-05）

### R-03 quality_log / deada_score_log 没有任何写入工具

- 8 个写工具只覆盖 8 张表；这两张表不在任何工具的目标表内（A2.1 映射见 `规格裁决_20261021.md:28-43`；协议 `:292-293` 又把它们列为 11 表核心）。
- 问题不是"作者写错"，而是契约缺一条写路径。**不要自行新增工具或改 14 工具集合**；等 Codex 定：app.py 内部直写、后续包补工具（需正式裁决）、或本阶段停用。
- 在 v2 的 `未决项.md` 中把它升级为明确阻塞项，写清三种选项与影响即可。

### R-05 rf_predict_log 的必填列没有来源

- `record_key`、`data_snapshot_id`、`rule_version` 完全无入参、无生成规则；`payload_sha256` 只有范围描述（协议 `:116`）、无字段级清单；`run_id` 可选但列 NOT NULL；`company_id` 已在 U-01 挂账。
- 同样**不要自行发明**。等 Codex 明确：每列来源、record_key 构成、payload_sha256 规范化字段清单、rule_version 取值；或把可推导项降为可空并写清语义。

## 四、P3 建议（同批修，不阻塞）

| 编号 | 内容 | 位置 |
|---|---|---|
| R-06 | BLOCKED 理由改为"本机有 MySQL 8.4 但无可用凭据/未获授权"，不要写"本机无 MySQL 实例"（本机服务实际在运行） | 测试报告.md:56、validate_contract.py:505 |
| R-07 | `params` 是空壳对象，`{}` 也能过；协议要求的 7 个键与 K黄>K红 目前只靠服务端。要么给 Schema 约束，要么在文档写明"仅服务端校验" | JSON:521-524、协议:165 |
| R-08 | `ck_tpl_publish` 未把 `published` 与 `published_at` 绑定，建议加 `publication_status<>'published' OR published_at IS NOT NULL` | init_v1.1.sql:202-205 |
| R-09 | 注释/脚本把 A2.3 写成"10 张业务表"，裁决字面是"全部 11 张表"；U-03 已挂账，注释改为"字面 11 张，本包按 U-03 待裁" | init_v1.1.sql:83、validate_contract.py:369/374/384 |
| R-10 | 第 46 行 `CREATE DATABASE` 与 cf_admin 权限等级不匹配，存在首句 ERROR 1044 中止风险（待隔离实测）。建议改为"库必须已存在 + 硬失败预检"，或给出可执行的低权方案 | init_v1.1.sql:36,46、grants 候选:10-11 |
| R-11 | 测试报告分节计数写错：B 实为 30 PASS+1 SKIP（不是 31 PASS），C 实为 21（不是 20）；总数 66/0/1/2 不变 | 测试报告.md:12-15 |
| R-12 | README 含服务器公网 IP，建议换别名；Python 版本写 3.13.12，解释器实测 3.13.14 | README.md:28,31 |

## 五、返工交付规则（沿用 CMD-002 与 001 纪律）

1. 新版本放 `交付\WB-ENG-001\WorkBuddy\v2\`，**不覆盖 v1**；v1 保留供比对。
2. 只改本通知列出的文件；未改文件在 `改动清单.md` 中标注"未改"，并给出 v1→v2 全量 SHA256 对照。
3. 重新生成 `SHA256SUMS.txt`（覆盖 v2 全部受审文件，不含 venv），并更新 `测试报告.md`（重新实跑）、`未决项.md`（U-01…U-07 状态同步，新增 R-03/R-05 裁决依赖）。
4. 不触碰 `D:\CashflowRiskWorkbench`，不连服务器、不执行 DDL、不改权限、不动千问、不启子 agent。
5. P0/P1 不存在，但请逐条回执：已修复 / 未修复 / 有异议（附依据）。有异议必须有可核对的证据，不能只写"认为没问题"。

## 六、复验入口

v2 落盘并暂停后，由 Codex 冻结版本并通知我复验。复验只针对：R-01、R-02、R-04 的原缺陷、受影响路径、以及 P3 的文档修正；不重复全部测试。复验仍只做静态/离线检查，真实 MySQL 执行仍需独立环境。

## 附：本通知不构成

- 不构成 Codex 的打回决定（需 Codex 确认后生效）；
- 不构成对任何业务参数的裁决；
- 不构成对 v1 的验收通过或部分放行。
