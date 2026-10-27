# AI 财务风险管控工作台：千问办公 × MySQL MCP 对接协议

> 文档版本：1.1（候选，WB-ENG-001 产出，未经 Codex 验收不得生效）
> 日期：2026-10-22
> 配套：`千问办公_MySQL_MCP工具定义_v1.1.json`、`sql/init_v1.1.sql`
> 状态：接口设计稿候选，尚未部署、连接千问或执行数据库迁移。
> 变更依据：`docs/规格裁决_20261021.md`（A1—A7）、`docs/规格裁决_20261022.md`（D8—D13）；
> 相对 v1.0 的变更点在各节以【v1.1】标注。

## 一、项目依据与版本说明

本协议依据《AI财务风险管控工作台完整方案_v7.md》《行业参数模板_相对指标版_v8.md》以及两份规格裁决编写。

已对齐的业务方向：核心计算、阈值判定、参数修正和压力测试在千问工作台完成；MCP 提供存储、查询及证据接口；MySQL 保存审计、反馈、行业模板、例外审批、压力测试、到账验证及三层模型日志记录。

v8 相对指标口径：记录月均经营性流出 M、现金缓冲 C、黄灯系数 K黄、红灯系数 K红以及公式版本；禁止把旧版固定金额阈值写死进 MCP。金额使用元（【v1.1】裁决 D12：MCP 边界与库内一律元，十进制字符串；万元只允许存在于千问表格与看板展示层，接入层显式换算并留 unit 痕迹）。模板来源中的经验参数与经核验的公开基准必须分开标记。

## 二、系统边界

```text
千问表格完成计算/判定（Q、D、FUSE、压力测试场景）
    ↓ Agent 或定时任务发起工具调用
MCP 客户端 → HTTPS /mcp → MCP Server → MySQL
    ↑ 工具返回存储凭据/查询结果
千问更新审计状态；通知通过已有连接器另行执行
```

MCP 不重新计算红黄绿、不自动批准例外、不代替银行确认到账、不直接付款。MySQL 的 COUNT、SUM 等留痕统计可在服务端执行，但不得把这些统计解释为新的财务风险决策。

【v1.1】唯一受控例外（裁决 A1/D11）：`rf_predict` 在 MCP 侧执行随机森林**推理**（模型离线训练，服务端只推理），返回概率 P 并留痕；P 不直接产生红黄绿，融合判定 FUSE(Q,D,P) 永远在千问表格内完成。MCP 不设 `quality_check`、`deada_score`、`fuse`、`run_stress_test` 四个计算型工具——Q/D/压力场景计算均在表格完成，结果经存储类工具留痕。

表格公式不能直接写 `=log_to_mysql()`。必须由 Agent 或定时任务读取结果后调用工具。千问是否支持自定义 MCP、传输方式、认证方式、定时执行与结果写回，均需现场验证。

【v1.1】部署拓扑（裁决 D14）：MySQL 只绑 `127.0.0.1:3306`，MCP Server 只绑 `127.0.0.1:8000`；人与千问连接器的访问均走 SSH 隧道（`ssh -L`），3306/8000 不对公网开放。Nginx 反代 + Bearer 令牌方案暂缓，留作将来外部演示备选。

## 三、传输与初始化

### 3.1 标准协议

- 消息编码：UTF-8 JSON-RPC 2.0。
- 远程接入首选 Streamable HTTP，统一入口为 `https://<实际域名>/mcp`（本阶段经 SSH 隧道为 `http://127.0.0.1:18000/mcp`）。
- 协议版本由初始化协商；本文件以 `2025-06-18` 为示例基线，不宣称它是最新版，也不代表千问已支持。
- 服务端须实现 `initialize`、`notifications/initialized`、`tools/list`、`tools/call`，并支持 `ping`。
- 推荐使用 MCP SDK 承担协议层。普通 FastAPI REST 路由可以保留为内部接口，但仅实现 `/mcp/log_to_mysql` 等路径不构成 MCP Server。

初始化请求示例：

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"finance-workbench-client","version":"1.0.0"}}}
```

初始化响应示例：

```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18","capabilities":{"tools":{"listChanged":false}},"serverInfo":{"name":"finance-risk-mysql","version":"1.1.0"}}}
```

客户端确认：

```json
{"jsonrpc":"2.0","method":"notifications/initialized"}
```

随后请求 `tools/list`，返回配套 JSON 的 `tools` 数组（【v1.1】14 个工具）。附件是工具定义，不是可直接导入千问的连接器配置，也不是可运行服务。

### 3.2 HTTP 约定

POST 请求携带 `Content-Type: application/json` 和 `Accept: application/json, text/event-stream`。初始化后按协商携带 `MCP-Protocol-Version`；如服务端签发 `Mcp-Session-Id`，后续请求必须携带。鉴权在初始化及后续调用中均生效。

通知被接受时返回 HTTP 202、无响应体。GET `/mcp` 提供 SSE 或返回 405；两者按服务器能力实现。网关保留必要请求头，若使用 SSE 则关闭对应响应缓冲。

### 3.3 身份与权限

远程接入采用客户端与网关实际支持、符合所选 MCP 授权规范的认证方案；完整 OAuth 对接与千问支持情况需联调确认。受控演示环境如采用预发令牌，必须标注为受限接入方案，不宣称已完成标准 OAuth 授权。

企业 ID、操作者 ID 和角色从已认证主体解析，不能信任模型传入的同名字段。单企业演示可绑定固定企业配置。不同企业必须使用不同授权范围，所有 SQL 均带服务端解析的企业条件。校验 Origin；本地服务只监听回环地址；MySQL 不对公网暴露。

## 四、通用数据契约

| 字段 | 类型 | 规则 |
|---|---|---|
| request_id | string | 写请求必填，1～128 字符；同一业务事件重试保持不变 |
| source_ref | string | 写请求必填；可定位表格、行、任务或报告的引用 |
| occurred_at | string | RFC3339，必须带时区；数据库统一转 UTC |
| rule_id / rule_version | string | 风控事件必填，精确标识规则与版本 |
| currency | string | 本阶段固定 CNY；其他币种需扩展协议 |
| amount 等金额 | string | 十进制字符串，单位元，例如 "125000.00"；最多两位小数，服务端 Decimal 解析（【v1.1】D12） |
| risk_level | enum | 【v1.1】green / yellow / red / unknown（D10：unknown 对应展示层"待复核/待校验"，二词已合并） |
| tracking_status | enum | resolved / observing / deteriorated；不能由风险颜色直接推导 |
| verification_status | enum | pending / verified / rejected |
| template_version | string | 模板版本，不允许用"最新版"替代历史版本号 |
| created_at | string | 由服务端写入的 UTC 时间，不使用模型自报时间（【v1.1】D21：DDL 默认值为 `DEFAULT (UTC_TIMESTAMP(6))`，会话时区不影响落库值；连接层仍须 `SET time_zone='+00:00'` 作纵深防御） |

【v1.1】`log_to_mysql.event_type` 枚举扩为 24 值（裁决 A2.2：v8 模块六 20 值 ∪ 协议 4 值）：

```text
daily_check quality_check deada_score rf_predict risk_assessment approval
exception config_change assumption_analysis industry_compare param_adjust feedback
onboarding root_cause dynamic_threshold stress_test exception_review audit_triggered
payment_verified da_coefficients_updated risk_warning tracking_changed
parameter_changed task_result
```

条件必填：`event_type ∈ {risk_warning, risk_assessment}` 时必须同时提供 `rule_id` + `rule_version` + `risk_level`。

服务器拒绝超限字符串、NaN、Infinity、不合法金额及无时区时间；单请求上限建议 256 KB，payload 上限建议 64 KB。以上是项目限额设计，不是 MCP 标准强制限额。

查询区间统一为 `[start_at, end_at)`，最大 366 天；分页默认 50 条、最多 200 条。游标必须绑定企业、查询条件与排序，不允许跨企业复用。查询无数据返回空数组或 found=false，不伪造零风险结论。

### 4.1 幂等和事务

以 `(tenant_id, tool_name, request_id)` 为唯一键。对语义参数做规范化 JSON 后计算 SHA-256；同键同参数返回原结果，标记 deduplicated=true；同键不同参数返回 IDEMPOTENCY_CONFLICT。

业务写入和幂等凭据在同一事务提交。连接中断后不得假定写入失败，先以相同 request_id 查询或重试。并发重复由唯一约束兜底，不采用"先查再插"作为唯一防护。

【v1.1】三层模型日志表（quality_log / deada_score_log / rf_predict_log）采用第二套行级幂等（裁决 D9）：唯一键 `(tenant_id, company_id, run_id, record_key)` + `payload_sha256`，服务端对规范化业务输入、输出、数据快照和版本计算 SHA-256（不含 created_at、request_id、重试次数等易变传输字段），同键同哈希返回既有 log_id，异哈希冲突不得覆盖。分工：`mcp_request_ledger` 管跨工具请求幂等；`record_key` 管同一 run 内逻辑行唯一。

## 五、工具定义与业务规则

工具的精确输入 JSON Schema 见配套 `千问办公_MySQL_MCP工具定义_v1.1.json`。所有工具禁止接收任意 SQL、数据库名或表名；全部工具 `additionalProperties:false`。

【v1.1】工具总数 14（裁决 A1/D11）：

| 工具名 | 用途 | 权限 | 目标表 |
|---|---|---|---|
| log_to_mysql | 追加工作台审计事件 | audit:write | audit_log |
| query_rule_stats | 按规则/版本/风险等级统计事件 | audit:read | audit_log |
| query_audit_by_event | 按 event_type 精确查询审计记录 | audit:read | audit_log |
| log_feedback | 保存预测与实际反馈 | feedback:write | feedback_log |
| query_feedback_stats | 按准确性标签汇总反馈 | feedback:read | feedback_log |
| save_param_template | 保存行业模板新版本草稿 | template:write | param_template |
| load_param_template | 读取指定版本或已发布最新模板 | template:read | param_template |
| log_exception | 留存已有审批凭据的例外事件 | exception:write | exception_log |
| query_exception_stats | 查询例外笔数和金额 | exception:read | exception_log |
| log_stress_test | 保存千问已计算的压力测试结果 | stress:write | stress_test_log |
| verify_payment | 提交证据并查询可信到账验证结果 | payment:verify | payment_verify_log |
| rf_predict | 【唯一计算工具】随机森林推理返回 P | model:infer | rf_predict_log |
| load_da_coefficients | 读取 DEA-DA 权重系数（供表格 SUMPRODUCT） | model:read | da_coefficient |
| save_da_coefficients | 写入离线求解的 DEA-DA 权重 | model:write | da_coefficient |

### 5.1 审计 log_to_mysql

`event_type` 允许【v1.1】§四列出的 24 值。payload 保存结果快照，不接受密码、完整银行卡号或整份银行流水。风控告警快照包含 M、C、K黄、K红、动态阈值开关、样本月份数、公式版本以及来源引用。服务器校验格式，不重新进行业务判定。

M 为零或无完整月份时，工作台必须标注不可判定或口径异常（risk_level=unknown），不能把空值补成零后自动报绿。C 的来源必须说明是否已包含该笔到账，避免"现金余额 + 已含在余额中的到账"重复计入。

### 5.2 规则统计 query_rule_stats

按 rule_id、rule_version、risk_level 精确字段查询，不能使用 payload LIKE 模糊匹配。返回 counts、窗口起止、总事件数、截点时间。这里统计的是预警事件，不等于正确率；正确率需要有对应反馈。

### 5.2a 【v1.1 新增】事件查询 query_audit_by_event

按 event_type（24 枚举之一）+ 时间区间 `[start_at, end_at)` 精确查询审计记录，可选 rule_id/rule_version/risk_level 过滤；返回活跃版本（排除被 supersedes_id 替代的记录）。不使用 payload LIKE。

### 5.3 反馈 log_feedback / query_feedback_stats

反馈必须引用已有 audit_id 或 forecast_id，并带 metric_code、预测区间、actual_source_ref。预测值与实际值只按同币种同单位存储；误差、准确性标签由工作台按指定评估口径生成，附 evaluation_version。缺乏实际数据时不得生成"准确"标签。

> **R-01 修订**：`predicted_value` / `actual_value` 由"无条件必填"改为**按 accuracy_label 条件必填**：
> - `accuracy_label=accurate` 或 `inaccurate`：两者必填，且必须来自真实观察窗口内的真实实际值；
> - `accuracy_label=pending`：可省略或显式 `null`，落库为 SQL NULL。
>
> **禁止以 0 或任何占位值代填"尚未产生实际值"**——那会把"未到实际期"写成"已对照"，污染准确率分母。
> Schema 层只做"accurate/inaccurate 必填"的静态约束；"有值就必须落在有效观察窗口内"由服务端校验。
> 按 Codex 处置意见，此处**不额外增设**"pending 一律不得携带 actual_value"的限制。

查询默认返回各标签数量，不擅自计算通用"准确率"；只有分母、成熟观察期和缺失处理均明确时，工作台才能计算评价指标。

### 5.4 模板 save_param_template / load_param_template

模板保存后默认 draft；发布动作通过可信管理流程执行，本阶段不向模型暴露发布权限。相同企业、行业、版本号不得覆盖；历史事件始终引用当时版本。

params 至少声明 schema_version、base_metric、yellow_coefficient、red_coefficient、approval_ratios、provenance、effective_from。要求 base_metric=monthly_operating_outflow；系数使用有限十进制字符串并满足黄灯系数大于红灯系数且红灯系数非负。provenance 区分经验建议、企业批准和已核验外部来源，外部出处未经核验不得标记 verified。

读取必须返回 matched_version、publication_status、来源与有效期。未找到模板返回 found=false，由千问进入人工配置；禁止默默套用其他行业模板。跨企业共享仅能使用另行批准的脱敏公共模板库，不直接读取其他企业参数。

### 5.5 例外 log_exception / query_exception_stats

必填部门、金额、理由和 approval_ref。服务器从可信审批系统或已登记审批凭据中核实批准状态、审批人和授权范围，不能把模型提交的 approver 名字当作批准证明（输入不接收 approver 字段）。凭据无法核实时返回 APPROVAL_UNVERIFIED，不记录为已批准例外。

本工具只留痕，不执行付款、放行或审批。查询返回例外笔数、例外总额；例外率须另有同范围审批总笔数作为分母，缺少分母返回 null 并说明。原方案 trigger_audit_check 涉及任务系统写入，待真实任务连接器和权限明确后单独接入；本阶段不虚构已创建审计任务。

### 5.6 压力测试 log_stress_test

scenario 为【v1.1】五值（裁决 A5）：`receivable_shock`（回款）、`financing_shock`（融资）、`cost_shock`（成本）、`dual_shock`（回款+融资双冲击）、`combined_shock`（全项联合）。保存 scenario_version、input_snapshot、result_snapshot 和风险等级，不在 MCP 内跑压力模型。每个场景具有独立 request_id，均带同一个 run_id 供整批回溯。只完成部分场景时不能声明整批测试成功（进度视图按 5 场景核对）。

### 5.7 到账 verify_payment

输入 payment_id、method、evidence_ref（【v1.1】输入不接收 status——状态由服务端返回，修复验收报告违规项 1）。method 为 bank_api 或 manual_review；企业、金额、收款账户和流水日期必须从可信来源核对，不能由模型提交 status=verified。

银行连接器未接入时返回 pending、reason=BANK_ADAPTER_UNAVAILABLE。人工复核须有已认证复核人的记录；仅上传截图仍为 pending。部分到账、重复流水、币种不同、金额不符或证据不足均不得直接 verified。凭据可以存对象存储引用及摘要，不向模型返回完整账户信息。

返回 verification_status、verified_amount、currency、evidence_ref、verified_at、review_ref；未通过时 verified_amount 为 "0.00"。只有工作台按其计算口径确认验证通过且尚未计入余额，才能更新有效缓冲。

### 5.8 【v1.1 新增】模型推理 rf_predict

输入 request_id、source_ref、occurred_at、eval_date、features（有序数值数组）、feature_names（与 features 等长的有序名称）、feature_schema_version、model_version，可选 run_id 关联同批评估。

服务端职责：校验 model_version 已登记、feature_schema_version 与模型匹配、features 与 feature_names 等长且维度符合该 schema 版本（【v1.1】D13：不在库层硬卡 30 维）；加载对应模型推理；把 P、模型版本、推理库版本与输入快照写入 rf_predict_log（execution_status='success' 时统计量必填，失败/skip/数据不足时必须 NULL，不补 0）。

返回 fraud_probability（十进制字符串，[0,1]）、probability_target（训练标签定义，如实记 ST/风险，不写"舞弊"）、model_version、inference_ms。P 是修正因子，不产生红黄绿；模型缺失或版本未知时明确返回不可用错误，不伪造分数。

### 5.9 【v1.1 新增】系数存取 load_da_coefficients / save_da_coefficients

load：必填 industry_key + coefficient_version（必须精确版本，不允许"最新版"），可选 io_role 过滤；返回该版本全部权重行（indicator_code、indicator_name、io_role、direction、weight、returns_to_scale、solved_at、solver_ref）。版本不存在返回 found=false，不替换行业或版本。

save：由离线求解脚本调用（MCP 不求解）。必填 request_id、source_ref、occurred_at、industry_key、coefficient_version、coefficients（整批权重行数组）、solved_at、solver_ref。整批同一事务写入，部分失败整体回滚；同 (industry_key, coefficient_version, indicator_code) 已存在时不得覆盖，返回冲突。

## 六、调用与返回示例

下列均为虚构演示数据。

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "tools/call",
  "params": {
    "name": "log_to_mysql",
    "arguments": {
      "request_id": "demo-20261021-warning-001",
      "source_ref": "qwen-sheet://demo/risk/row-18",
      "occurred_at": "2026-10-21T09:00:00+08:00",
      "event_type": "risk_warning",
      "rule_id": "cash_buffer_relative",
      "rule_version": "8.0",
      "risk_level": "yellow",
      "payload": {
        "currency": "CNY",
        "M": "1000000.00",
        "C": "1200000.00",
        "K_yellow": "1.5",
        "K_red": "1.0",
        "history_months": 8,
        "dynamic_threshold_enabled": false,
        "formula_version": "cash-buffer-v8-demo"
      }
    }
  }
}
```

业务结果对象统一包含 ok、code、message、request_id、server_time、data。查询 request_id 由服务端产生；写请求回显业务 request_id。工具成功返回：

```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "result": {
    "content": [{"type":"text","text":"{\"ok\":true,\"code\":\"OK\",\"message\":\"审计事件已存储\",\"request_id\":\"demo-20261021-warning-001\",\"server_time\":\"2026-10-21T01:00:01Z\",\"data\":{\"audit_id\":\"1024\",\"deduplicated\":false}}"}],
    "structuredContent": {
      "ok": true,
      "code": "OK",
      "message": "审计事件已存储",
      "request_id": "demo-20261021-warning-001",
      "server_time": "2026-10-21T01:00:01Z",
      "data": {"audit_id":"1024","deduplicated":false}
    },
    "isError": false
  }
}
```

兼容文本消费者时 content.text 为相同业务对象的 JSON 字符串。服务端仅在数据库事务提交成功后报告已存储；这不代表通知已发送、风险已解除或审批已完成。

> **R-02 修订**：`audit_id` 是 `audit_log.id` 的回显，为 DB 自增 `BIGINT UNSIGNED`，
> 接口以**十进制数字字符串**传输（如 `"1024"`）。旧示例 `A-demo-001` 这类业务串已作废：
> 它在 Schema 层不再被接受（`^[0-9]{1,20}$`），写入 BIGINT 列也会在严格模式下失败。
> 服务端仍须另行校验 BIGINT UNSIGNED 数值范围与真实同租户关联——pattern 只保证形态，不保证范围。

## 七、错误、重试和本地兜底

| 情形 | 表达方式 | 调用方处理 |
|---|---|---|
| HTTP 身份认证失败 | HTTP 401/403 | 修复凭据或权限，不盲目重试 |
| JSON-RPC 报文无效/方法未知 | 标准 -32600/-32601 等错误 | 修正协议实现 |
| 工具名未知或参数不合法 | JSON-RPC -32602 | 修正名称或输入 |
| 企业范围不符 | 工具错误 FORBIDDEN | 停止调用，核对授权 |
| 同幂等键不同内容 | 工具错误 IDEMPOTENCY_CONFLICT | 人工核对原记录，不覆盖 |
| 审批未核实 | 工具错误 APPROVAL_UNVERIFIED | 补充可信凭据 |
| 数据库连接/提交失败 | 工具错误 DB_UNAVAILABLE | 原键排队补传 |
| 缺少银行/人工证据 | 正常业务结果 pending | 保持待验证，不计入有效到账 |
| 【v1.1】模型/特征版本未知 | 工具错误 MODEL_UNAVAILABLE | 核对 model_version 与 feature_schema_version |

业务执行失败使用 result.isError=true，content 与 structuredContent 返回同一错误对象。错误信息必须脱敏，不返回密码、连接串或完整 SQL。结构化 ok=false 与 isError=true 保持一致；pending 属于已正常执行但证据未满足，不属于工具执行异常。

遵守用户项目规则：未知问题每次重试至少间隔 30 秒，本方案最多 3 次；每次先做有信息量的只读排查。超过次数停止，报告错误原文（剔除密钥）与已尝试方法。写入重试沿用原 request_id。

MCP 不可用时，千问本地审计表记录 pending_sync、request_id、工具名、待提交参数和失败原因；这不等于 MySQL 已写入。恢复后按时间串行补传，收到提交成功凭据才改为 synced。未落地可靠队列前不得宣称具有自动断网补传能力。

## 八、MySQL 落库约束

【v1.1】库名与排序规则统一 `cf_workbench` + `utf8mb4_0900_ai_ci`（裁决 D8；弃用 audit_db 与 utf8mb4_bin——同库混排序规则会在跨表 JOIN 文本列时报 illegal mix of collations）。

【v1.1】11 张表（裁决 A2.3：协议 6 业务表 + v8 三层日志 3 张 + da_coefficient + mcp_request_ledger）：

| 表 | 核心业务字段 |
|---|---|
| audit_log | event_type、rule_id、rule_version、risk_level、payload(JSON) |
| feedback_log | audit_id/forecast_id、metric_code、predicted_value、actual_value、accuracy_label、evaluation_version、actual_source_ref |
| param_template | industry_key、template_version、publication_status、params(JSON)、provenance(JSON)、effective_from |
| exception_log | dept、amount、currency、reason、approval_ref、trusted_approver_id |
| stress_test_log | run_id、scenario（5值）、scenario_version、input_snapshot(JSON)、result_snapshot(JSON)、risk_level |
| payment_verify_log | payment_id、method、verification_status、verified_amount、currency、evidence_ref、review_ref |
| quality_log | company_id、run_id、record_key、payload_sha256、execution_status、benford_chi2、myer_index(+myer_scale)、quality_score、company_quality_score(+aggregation_version)（裁决 D9 采纳任务二结构） |
| deada_score_log | company_id、run_id、record_key、payload_sha256、execution_status、input_weights、output_weights、discriminant_score、threshold、is_risk（同上） |
| rf_predict_log | company_id、run_id、record_key、payload_sha256、execution_status、features+feature_names（等长，D13 不硬卡 30 维）、fraud_probability+probability_target、model_version（同上） |
| da_coefficient | industry_key、coefficient_version、indicator_code、io_role、direction、weight DECIMAL(18,10)、solver_ref |
| mcp_request_ledger | tenant_id、tool_name、request_id、payload_hash、result_json |

业务表共同字段：id、tenant_id、request_id、source_ref、occurred_at、created_at、actor_id、supersedes_id（裁决 A2.3；三层模型日志表另含 company_id/run_id/record_key/payload_sha256/execution_status）。金额使用 DECIMAL(20,2)（单位元），UTC 时间使用 DATETIME(6)（默认值 `DEFAULT (UTC_TIMESTAMP(6))`，D21），结构化内容用 JSON，字符集 utf8mb4 + utf8mb4_0900_ai_ci，存储引擎 InnoDB。

灯色枚举库内一律 `green / yellow / red / unknown`（D10）；中文（红灯/黄灯/绿灯/待复核）只存在于展示层。

索引至少包含：audit_log(tenant_id, rule_id, occurred_at)、exception_log(tenant_id, dept, occurred_at)、payment_verify_log(tenant_id, payment_id, occurred_at)。模板唯一键为 (tenant_id, industry_key, template_version)。审批事件通过业务审批唯一键防止换 request_id 重复记账；银行流水通过可信流水唯一键防止重复核销。三张模型日志表行级唯一键为 (tenant_id, company_id, run_id, record_key)（D9）。

业务账号仅赋必要 SELECT/INSERT，不能 DROP、ALTER、DELETE；建表迁移和模板发布使用独立管理身份（cf_admin）。追加记录纠错通过 supersedes_id 指向原记录，查询统计排除被替代版本且替代链判定限定同一 tenant_id，避免跨租户误判与重复计数。数据库备份使用独立备份账号（cf_backup），不复用受限业务账号。

【v1.1】账号与初始化分离（任务书第 3 条）：init_v1.1.sql 只建表与视图，不含 CREATE USER / GRANT / 口令。cf_admin 建视图所需的 CREATE VIEW、SHOW VIEW 权限变更以单独候选文件提出，经批准后由部署任务执行。

【v1.1】company_id 与 tenant_id 的语义关系未裁决（验收报告 C4）：三张模型日志表保留 company_id（队友被采纳结构的固有部分），其余 8 张表【不】预先扩散该列；语义裁决前列为部署阻塞项，详见交付包《未决项.md》U-01。

SQL 值使用驱动参数绑定；聚合维度与排序字段来自代码白名单。不得把模型给出的列名直接拼接 SQL。数据库口令只来自环境变量或密钥管理，不写入文档、客户端配置或日志。

## 九、千问接入与联调顺序

1. 在千问当前版本查看是否有自定义 MCP 配置入口，记录实际支持的传输、认证和协议版本；不要把 v7 的菜单路径当作已验证事实。
2. 先用 MCP 测试客户端验证初始化、工具发现、工具调用及认证拒绝，再接千问。数据库采用独立演示库。
3. 本阶段千问连接器经 SSH 隧道访问：`ssh -N -L 18000:127.0.0.1:8000 <user>@<服务器>`，连接器填 `http://127.0.0.1:18000/mcp`（D14）。将来若千问支持且需公网接入，再启用 HTTPS `/mcp` + 匹配认证；不要用改 URL 的方式假装兼容。
4. 首次只开放 log_to_mysql 和 query_rule_stats，使用标有 demo 的虚构数据完成写入、查询、重复提交三步。
5. 再开放反馈、模板、事件查询、系数存取和压力测试工具；随后接入 rf_predict（先验证模型与特征版本绑定）；最后接入审批凭据及银行/人工复核证据。
6. 在千问中核对"待同步/已留痕/待验证"等状态。每次业务调用确认数据库记录与工具凭据一致。

连接信息填写清单（本阶段）：服务名称 finance-risk-mysql；地址 http://127.0.0.1:18000/mcp（SSH 隧道）；传输 Streamable HTTP（须实测）；认证以实际支持方案为准。此清单不等于特定千问版本可直接导入的配置 JSON。

## 十、Agent 调用约束（可放入工作台提示词）

> 使用工作台计算结果调用 MCP，禁止自行编造财务金额、风险等级、审批记录或到账验证结果。写请求均提供稳定 request_id、来源和时间。收到数据库提交成功凭据后才称"已留痕"；pending_sync 应明确显示待同步。verify_payment 返回 pending 或 rejected 时，保持待验证/退回状态，不把金额计入有效缓冲。模板保存成功仅表示草稿已保存，不能声称已发布。例外留痕不等于付款放行。rf_predict 返回的概率只是修正因子，红黄绿只由表格 FUSE 决定；模型不可用时要如实报告而非猜测分数。工具查询无数据时如实说明。失败按项目节奏串行排查和重试，不密集重复调用。

## 十一、验收清单

| 编号 | 场景 | 通过标准 |
|---|---|---|
| 01 | initialize / initialized / tools/list | 成功协商并发现【v1.1】14 个工具 |
| 02 | 写一笔演示告警 | 数据库仅新增一条，返回可查询 audit_id |
| 03 | 同键同内容重试 | 不新增记录，deduplicated=true |
| 04 | 同键不同内容 | 明确冲突，原记录不变 |
| 05 | 跨企业请求 | 拒绝且不泄露目标记录 |
| 06 | 超限/非法金额/无时区时间 | 入库前拒绝 |
| 07 | 数据库断连 | 不报告成功，进入可见待同步状态 |
| 08 | 补传后查询 | 与原事件一致，不重复计数 |
| 09 | 查询精确规则和版本 | 不混入相似名称或其他版本 |
| 10 | 模板版本不存在 | found=false，不替换行业 |
| 11 | 上传凭证但无可信复核 | pending，verified_amount="0.00" |
| 12 | 模型声称已批准/已到账 | 无可信凭据不能转为批准/verified |
| 13 | 历史不足 12 个月的告警 | 记录真实月份数及静态相对阈值快照 |
| 14 | 查询无反馈样本 | 返回空统计，不生成准确率 |
| 15 | 通知失败但审计成功 | 分别显示两项状态，不混称全流程成功 |
| 16 | 【v1.1 新增】rf_predict 推理留痕 | 返回 P∈[0,1] 且 rf_predict_log 落一行（含 model_version/特征版本/输入快照）；未知模型版本明确报 MODEL_UNAVAILABLE；P 不产生红黄绿 |
| 17 | 【v1.1 新增】系数存取 | save 整批写入可 load 精确版本取回；同版本重复写返回冲突不覆盖；不存在版本 found=false |

全部验收项当前均为待执行。本协议与工具 JSON 通过文件层面检查，不构成已通过联调的证据。

## 十二、协议参考

- [MCP 工具发现、调用与返回结构（2025-06-18）](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
- [MCP Streamable HTTP 传输（2025-06-18）](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)

协议格式来自上述标准；业务字段、权限名、幂等策略和验收规则是本项目约定。千问客户端能力仍需实测。

## 十三、【v1.1 新增】版本变更记录

| 版本 | 日期 | 变更 | 依据 |
|---|---|---|---|
| 1.0 | 2026-10-21 | 初稿，10 工具 / 4 event_type / 7 表口径 | — |
| 1.1 | 2026-10-22 | 工具 10→14（+query_audit_by_event、rf_predict、load_da_coefficients、save_da_coefficients）；event_type 4→24；risk_level 增 unknown；risk_assessment 纳入条件必填；scenario 4→5；金额一律元；库名 cf_workbench + utf8mb4_0900_ai_ci；表 7→11（采纳任务二三表结构）；UTC 默认表达式；SSH 隧道拓扑；验收 01 改 14 工具并新增 16/17 两条 | A1/A2.1/A2.2/A2.3/A5、D8/D9/D10/D11/D12/D13/D14/D21 |
