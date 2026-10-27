# SUMMARY — 2026-10-27 工作汇总

分支：`20261027`（从 `main` 新建，未强推）。本文件只描述**今天（2026-10-27）新增/修改**的部分；仓库中 `main` 分支原有的 D 盘归档快照（19:15 前的历史文件）不在本清单内。

代码主体位于 [`CashflowRiskWorkbench/`](CashflowRiskWorkbench/)。

---

## 一、今日完成清单

### 1. v8 三层风控引擎（新增）
| 文件 | 内容 |
|---|---|
| `mcp-server/program_v1/src/v8/industry.py` | 四行业模板（制造/建筑/零售/科技服务） |
| `.../v8/indicators.py` | 指标体系（逆指标前处理取负） |
| `.../v8/layers.py` | Q/D/P 三层：数据质量、DEA-DA 判别、缓冲与压力测试 |
| `.../v8/engine.py` | 引擎编排，输出等级与最劣情景 |
| `mcp-server/program_v1/src/v8_server.py` | HTTP 服务，端口 **8010** |
| `web/v8_工作台.html` | 前端工作台 |

算法均为纯 Python 自实现：Benford 首位 χ²（临界 20.09）、末位均匀 χ²（df=9，临界 16.92）、两阶段单纯形法 DEA-DA、CART 随机森林（60 棵 bootstrap）。

### 2. v8 六项落地（新增）
| 文件 | 内容 |
|---|---|
| `.../v8/db.py` | 统一数据访问层，建表幂等；MySQL 不可用时降级为 JSON 落盘 |
| `.../v8/scope.py` + `capability_switch.json` | 数据范围约束与能力开关 |
| `.../v8/tracking.py` | 应收三态（绿/黄/红）追踪与流转历史 |
| `.../v8/audit.py` | 变更前/后值留痕归档 |
| `.../v8/cleaning.py` | 清洗规则集，批次入库 |
| `src/public_server.py`、`src/notify.py` | 对外服务与通知出口 |
| `sql/v8_schema.sql` | 5 张表 DDL（risk_log / audit_log / tracking / clean_batch / clean_item） |

### 3. v10 四层编排（前端 ⇄ 千问中枢 ⇄ MCP 工具层）（新增）
`qwen-integration/orchestrator/`：`protocol.py`、`mcp_client.py`、`planner.py`、`qwen_adapter.py`、`taskhub.py`、`gateway.py`、`__init__.py`
- 网关端口 **8100**，HTTP + SSE；事件流 `task.created → plan.ready → step.started → step.done → agent.message → task.done`，支持运行中热调 `params`。
- `web/v10_工作台.html` 前端；`qwen-integration/verify_v10.py` 验证；`deploy/v10/` 提供 Dockerfile / docker-compose / nginx 配置（nginx 需 `proxy_buffering off` 才能保证 SSE 流式）。

### 4. 责任机制 v11（新增）
| 文件 | 内容 |
|---|---|
| `sql/v8_accountability_schema.sql` | 5 张表（owner_matrix / matter / review / confirm / urge）+ 默认责任矩阵种子数据 |
| `.../v8/owners.py` | 风险分级 × 责任人矩阵 |
| `.../v8/matter.py` | 事项状态机 `SUBMITTED → ASSIGNED → IN_REVIEW → PENDING_CONFIRM → CONFIRMED / REJECTED / URGING / ESCALATED` |
| `.../v8/dingtalk.py` | 钉钉确认书通道（**未配置凭据时一律 dry-run，`message_id` 为 `dryrun-*`，绝不伪造送达**） |
| `.../v8/workflow.py` | 超时催办、驳回重流转 |
| `src/v8_mcp_server.py` | MCP 工具总数 **21**（其中 `acc.*` 9 个） |
| `src/v8_acc_server.py` | 端口 **8020**，含 `/dingtalk/confirm` 在线确认页 |
| `docs/责任机制设计_v11.md` | 设计说明 |

默认矩阵：高→财务总监 8h（替补风控经理，升级总经理）；中→风控经理 24h；低→财务主管 48h。

### 5. 单文件 MCP Server（新增，可直接粘贴到千问办公）
- `qwen-integration/mcp_frontend_server.py` — **零第三方依赖**，工具：`frontend.dispatch`（统一入口，按 action 路由）、`workbench.risk_assess`、`workbench.ledger_query`；统一返回 `{ok, code, action, data, error, meta}`；错误码 4000/4001/4002/4003/4100/4101/5000。
- `mcp_frontend_server.config.json`（stdio 启动配置）、`test_mcp_frontend.py`（进程内驱动，不 spawn 子进程）。
- 业务实现集中在 `biz_risk_assess` / `biz_ledger_query` / `ACTION_SCHEMAS` / `ACTION_ROUTER` 四处 TODO。

### 6. 部署与存储闭环（新增/修改）
`deploy/`：`serve.py`（端口 **8000**，加载 `deploy/.env`）、`env.template`、`setup_storage.py`、`verify_closed_loop.py`、`server_bootstrap.sh`、`mysqld-standalone.cnf`、`.gitignore`、`v10/*`。
本机独立 MySQL 8.4 实例：**127.0.0.1:3307**，库 `cfqa_workbench`，应用账号 `cf_app`。

### 7. 千问办公接入配置（新增）
`qwen-integration/README.md`、`connector-stdio.json`、`connector-http.json`、`mcp_stdio.py`、`skills/mfg-program-workbench/SKILL.md`。

### 8. 今日文档（新增/修改）
`docs/架构设计_千问中枢_v9_20261027.md`、`docs/架构设计_前端_千问中枢_MCP_v10.md`、`docs/第一版交付_千问中枢_v1_20261027.md`、`docs/现状核对_MCP服务已建成_20261027.md`、`docs/责任机制设计_v11.md`、`docs/v8_完整方案.md`（改）。

### 9. 仓库治理
- 根 `.gitignore` 补充：`.mysqldata/`、`*.ibd/ibt/dblwr`、`binlog.*`、`*.zip`、`outbox/runtime/`、`*.log`、编辑器与系统文件。
- 删除 6 个已过期的 `outbox/*.zip` 构建产物。

---

## 二、验证结果（本次推送前实测）

| 脚本 | 结果 |
|---|---|
| `qwen-integration/verify_v10.py` | PASS 20 / FAIL 0 |
| `qwen-integration/verify_accountability.py` | 全部通过 |
| `qwen-integration/verify_acc_http.py` | 全部通过 |
| `qwen-integration/test_mcp_frontend.py` | 全部通过 |

服务端口实测在监听：3307（MySQL）、8000（工作台）、8010（v8）、8020（责任机制）、8100（v10 网关）。

> 说明：验证过程中发现当前 Python 解释器未安装 `PyMySQL`（已在 `requirements.lock.txt` 中声明），导致数据库断言一度降级为 JSON 回退并失败。按声明安装 `PyMySQL==1.1.2` 后全部通过。**这不是代码回归，而是运行环境缺依赖**，部署到新机器时必须先 `pip install -r requirements.lock.txt`。

---

## 三、当前进度

- ✅ 金额计算与风险判定：由自有服务器上的确定性程序产出，数据落在自有 MySQL。
- ✅ 八表合成演示闭环：期初 100000 / 流入 185000 / 流出 108000 / 净额 77000 / 期末 177000 / **差异 0**。
- ✅ v8 引擎 + 六项落地、v10 四层编排、责任机制 v11、单文件 MCP 均已落地并通过脚本验证。

## 四、遗留问题与事实边界（不要对外声称已完成）

1. **千问办公尚未真正接入**：前端目前经 8100 网关通信；未配置 `QWEN_API_BASE/KEY` 时 `planner` 走的是 `local-planner` 兜底，**不是千问在编排**。
2. **千问远程回调我们的 MCP 未验证**：stdio 模式已验证；`MCP_TRANSPORT=http` 的远程调用待真机验证。
3. **钉钉确认书为 dry-run**：未配置 `DINGTALK_WEBHOOK/SECRET` 时接口如实返回 `not_configured`，`message_id` 为 `dryrun-*`；**没有真实送达，不得声称已推送到人**。
4. **部署参数全部是占位**：`CF_DB_HOST/PORT/USER/PASSWORD/NAME`（生产库名不得 `cfqa_` 前缀）、`CF_MCP_TOKEN`、`MCP_TRANSPORT`、`QWEN_API_BASE/KEY`、`DINGTALK_*`、`CF_CONFIRM_BASE`、域名与 Nginx 配置，均集中在 `v8/db.py`、`gateway.py`、`mcp_frontend_server.py` 的 TODO 块，替换前不具备生产条件。
5. **本机口令曾出现在本次会话输出中**（`deploy/.env` 内 `CF_DB_PASSWORD`），仅存在于本机未入仓，建议轮换。
6. 归档仓库中的 `file-readmes/`、`AI_Command_Workspace/` 为历史归档，与今日工作无关，未改动。

---

## 五、下一步可执行方案（按优先级）

**P0 — 让链路真实可用**
1. 在一台自有服务器部署 MySQL，创建非 root 应用账号与生产库名（不得 `cfqa_` 前缀），替换 `v8/db.py` TODO 块的 `CF_DB_*`。
2. `pip install -r mcp-server/program_v1/requirements.lock.txt`，执行 `sql/v8_schema.sql` 与 `sql/v8_accountability_schema.sql` 建表。
3. 设置 `CF_MCP_TOKEN`，把 `MCP_TRANSPORT` 从 `stdio` 切到 `http`，验证千问办公能远程 `tools/list` + `tools/call`。

**P1 — 接通千问中枢**
4. 配置 `QWEN_API_BASE/QWEN_API_KEY`，把 `planner` 从 `local-planner` 切到真实千问编排，再用 `verify_v10.py` 复跑一遍事件流。
5. 用 `deploy/v10/nginx-v10.conf` 反代 8100，确认 `proxy_buffering off` 生效、SSE 不断流。

**P2 — 责任机制上线**
6. 填入 `DINGTALK_WEBHOOK/DINGTALK_SECRET` 与 `CF_CONFIRM_BASE`，把钉钉确认书从 dry-run 转为真实发送，验证 `message_id` 不再是 `dryrun-*`。
7. 按真实组织架构替换 `owner_matrix` 种子数据（现为演示用的张伟/李娜/王强/陈静）。

**P3 — 收敛与交付**
8. 把 `20261027` 分支合入 `main`（本分支未强推，可安全走 PR）。
9. 视需要把仓库从 public 转为 private —— 当前为公开，代码内含内部业务逻辑与演示责任人姓名（已确认无密钥明文）。
10. 清理归档仓库中的 `file-readmes/`、`AI_Command_Workspace/` 历史目录，或移入 `archive/`，减少仓库噪音。
