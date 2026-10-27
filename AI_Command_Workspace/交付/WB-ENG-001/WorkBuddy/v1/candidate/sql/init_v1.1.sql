-- =============================================================================
-- CashflowRiskWorkbench · 数据库地基
-- 文件：sql/init_v1.1.sql（候选，WB-ENG-001 产出，未经 Codex 验收不得在服务器执行）
-- 依据：docs/千问办公_MySQL_MCP对接协议.md §八；
--       docs/规格裁决_20261021.md（A1-A7，尤其 A2.3 公共列、A5 场景枚举）；
--       docs/规格裁决_20261022.md（D8 库名/排序规则、D9 采纳队友任务二三表结构、
--       D10 灯色英文枚举、D12 金额单位元、D13 删除 30 维硬卡、D21 UTC 默认值）；
--       docs/外包交付/队友提交_任务一二三_v2.0.0/任务二_MySQL三张日志表建表.sql（被采纳方）。
-- 版本：1.1  生成日期：2026-10-22
--
-- 与 v1.0 的行为差异（重要）：
--   * 表一律裸 CREATE TABLE（无 IF NOT EXISTS）：同名表已存在时报错停止（ERROR 1050），
--     绝不静默跳过不匹配结构。首次部署=全建成功；二次执行=预检段列出现状后，
--     首个 CREATE 报错停止，由部署者按《部署手册》结构比对流程处理。
--   * 视图用 CREATE OR REPLACE：视图定义允许随版本演进重建。
--   * 不含任何 CREATE USER / GRANT / 口令：账号已存在（cf_admin/cf_app/cf_backup/cf_read），
--     初始化只建表与视图；cf_admin 缺 CREATE VIEW/SHOW VIEW 的最小权限变更候选见
--     grants_admin_view_候选.sql（待批准，不在本文件执行）。
--   * created_at 默认值由 CURRENT_TIMESTAMP(6) 改为 (UTC_TIMESTAMP(6))（裁决 D21）：
--     会话时区无论是否 +00:00，落库一律 UTC。连接层仍须 SET time_zone='+00:00'。
--
-- 口径约定（全库统一，请勿在表内另立）
--   1. 金额一律 DECIMAL(20,2)，单位为「元」（裁决 D12）。源表以「万元」计列者必须在
--      seed 阶段 ×10000 换算，禁止把万元数值直接入库。
--   2. 时间一律 DATETIME(6)，存 UTC。occurred_at 由入参 RFC3339 带时区值转换而来；
--      created_at 一律由服务端写入，不采用模型自报时间（协议 §四）。
--   3. 结构化内容用 JSON 列；写入前用 json.dumps，禁止 Python repr 字符串（协议 §四）。
--   4. 枚举类字段一律用 VARCHAR + 注释白名单（或 CHECK 白名单），不用 ENUM：
--      业务账号无 ALTER 权限，ENUM 取值变更会需要 DDL（协议 §八 权限约束）。
--   5. 追加式记录。纠错不原地改写，而是新增一行并用 supersedes_id 指向被替代行；
--      活跃视图排除被替代版本，且子查询同时限定同一 tenant_id，防跨租户误判与重复计数。
--   6. 不设外键：审计类表按 tenant_id 逻辑隔离（协议 §八）。
--   7. 灯色词表库内一律 green / yellow / red / unknown（裁决 D10）；
--      中文（红灯/黄灯/绿灯/待复核）只存在于展示层。
--
-- 执行：mysql --default-character-set=utf8mb4 -u cf_admin -p < sql/init_v1.1.sql
--       不使用 --force；DDL 隐式提交，不能依靠 ROLLBACK 撤回整个部署。
-- 待验：本文件【未】在真实 MySQL 8.x 实例上执行过（WB-ENG-001 纪律禁止服务器 DDL），
--       仅通过静态解析与契约映射校验；真实执行属后续部署任务（见交付包 测试报告.md）。
-- =============================================================================

SET NAMES utf8mb4;
SET SESSION time_zone = '+00:00';
SET SESSION sql_mode = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ZERO_DATE,NO_ZERO_IN_DATE,NO_ENGINE_SUBSTITUTION';

CREATE DATABASE IF NOT EXISTS cf_workbench
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE cf_workbench;

-- =============================================================================
-- 结构预检（只读输出，不改数据）
--   [1] 库字符集/排序规则：若不是 utf8mb4_0900_ai_ci，部署者须先
--       ALTER DATABASE cf_workbench CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
--   [2] 已存在的同名表：本脚本期望 0 行。非空则继续执行必然在首个 CREATE 报错停止——
--       这是有意行为：禁止静默跳过不匹配结构。
--   [3] 已存在的同名视图：将被 CREATE OR REPLACE 重建，列出供知情。
-- =============================================================================
SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME
  FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = 'cf_workbench';

SELECT table_name AS existing_table,
       'WARN: 已存在，裸 CREATE TABLE 将报错停止（ERROR 1050）' AS action
  FROM information_schema.tables
 WHERE table_schema = 'cf_workbench'
   AND table_name IN ('mcp_request_ledger','audit_log','feedback_log','param_template',
                      'exception_log','stress_test_log','payment_verify_log','quality_log',
                      'deada_score_log','rf_predict_log','da_coefficient')
 ORDER BY table_name;

SELECT table_name AS existing_view,
       'INFO: 将被 CREATE OR REPLACE 重建' AS action
  FROM information_schema.views
 WHERE table_schema = 'cf_workbench'
   AND table_name IN ('v_record_active','v_rule_stats','v_feedback_label_counts',
                      'v_exception_stats','v_stress_run_progress','v_verified_payment_sum',
                      'v_template_published_latest','v_quality_active','v_deada_active','v_rf_active')
 ORDER BY table_name;

-- -----------------------------------------------------------------------------
-- 1. mcp_request_ledger —— 幂等账本（与业务写入同事务提交）
--    唯一键 (tenant_id, tool_name, request_id) 是全部写请求的防重底线。
--    账本结构特殊：无业务发生时刻概念，不携带 occurred_at/source_ref/actor_id/
--    supersedes_id（裁决 A2.3 公共列针对 10 张业务表；账本例外已在 未决项.md 登记）。
-- -----------------------------------------------------------------------------
CREATE TABLE mcp_request_ledger (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tenant_id      VARCHAR(64)   NOT NULL,
  tool_name      VARCHAR(64)   NOT NULL COMMENT '14 个工具名之一',
  request_id     VARCHAR(128)  NOT NULL COMMENT '客户端稳定业务幂等键',
  payload_hash   CHAR(64)      CHARACTER SET ascii COLLATE ascii_bin NOT NULL COMMENT '语义参数规范化 JSON 的 SHA-256',
  result_json    JSON          NOT NULL COMMENT '原样回放给重试方的业务结果',
  created_at     DATETIME(6)   NOT NULL DEFAULT (UTC_TIMESTAMP(6)) COMMENT '服务端写入 UTC（D21）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_ledger_key (tenant_id, tool_name, request_id),
  KEY idx_ledger_time (tenant_id, created_at),
  CONSTRAINT ck_ledger_hash CHECK (payload_hash REGEXP '^[0-9a-f]{64}$')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='写请求幂等凭据；同键同哈希回放，同键异哈希返回 IDEMPOTENCY_CONFLICT';

-- -----------------------------------------------------------------------------
-- 2. audit_log —— 工作台审计事件（含三层模型的 Q/D 结果留痕）
--    event_type 白名单 24 值（v8 模块六 20 + 协议 4，裁决 A2.2）。
--    event_type ∈ {risk_warning, risk_assessment} 时 rule_id/rule_version/risk_level 必填
--    （工具层强制；DB 以 CHECK 兜底）。
-- -----------------------------------------------------------------------------
CREATE TABLE audit_log (
  id             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tenant_id      VARCHAR(64)   NOT NULL,
  request_id     VARCHAR(128)  NOT NULL,
  source_ref     VARCHAR(128)  NOT NULL COMMENT '表格/行/任务/报告的可定位引用',
  occurred_at    DATETIME(6)   NOT NULL COMMENT '事件发生时间 UTC',
  created_at     DATETIME(6)   NOT NULL DEFAULT (UTC_TIMESTAMP(6)) COMMENT '服务端写入 UTC（D21）',
  actor_id       VARCHAR(128)  NOT NULL COMMENT '从已认证主体解析，不采信模型传入',
  supersedes_id  BIGINT UNSIGNED NULL COMMENT '纠错：指向被本行替代的原记录',
  event_type     VARCHAR(32)   NOT NULL COMMENT '白名单24：daily_check quality_check deada_score rf_predict risk_assessment approval exception config_change assumption_analysis industry_compare param_adjust feedback onboarding root_cause dynamic_threshold stress_test exception_review audit_triggered payment_verified da_coefficients_updated risk_warning tracking_changed parameter_changed task_result',
  rule_id        VARCHAR(128)  NULL,
  rule_version   VARCHAR(128)  NULL,
  risk_level     VARCHAR(10)   NULL COMMENT 'green / yellow / red / unknown（不可判定；D10）',
  payload        JSON          NOT NULL COMMENT '结果快照；禁含密码、完整卡号、整份流水',
  PRIMARY KEY (id),
  UNIQUE KEY uk_audit_req (tenant_id, request_id),
  KEY idx_audit_rule (tenant_id, rule_id, rule_version, occurred_at),
  KEY idx_audit_event (tenant_id, event_type, occurred_at),
  KEY idx_audit_supersedes (supersedes_id),
  CONSTRAINT ck_audit_event_type CHECK (event_type IN (
    'daily_check','quality_check','deada_score','rf_predict','risk_assessment','approval',
    'exception','config_change','assumption_analysis','industry_compare','param_adjust',
    'feedback','onboarding','root_cause','dynamic_threshold','stress_test','exception_review',
    'audit_triggered','payment_verified','da_coefficients_updated','risk_warning',
    'tracking_changed','parameter_changed','task_result')),
  CONSTRAINT ck_audit_risk_level CHECK (risk_level IS NULL OR risk_level IN ('green','yellow','red','unknown')),
  CONSTRAINT ck_audit_risk_event CHECK (
    event_type NOT IN ('risk_warning','risk_assessment')
    OR (rule_id IS NOT NULL AND rule_version IS NOT NULL AND risk_level IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='审计留痕。MCP 只存储，不做风险判定';

-- -----------------------------------------------------------------------------
-- 3. feedback_log —— 预测与实际的对照反馈
--    audit_id 与 forecast_id 至少一个（工具层校验 + DB CHECK 兜底）。
--    accuracy_label 由工作台按 evaluation_version 口径生成，缺实际数据不得填 accurate。
-- -----------------------------------------------------------------------------
CREATE TABLE feedback_log (
  id                 BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tenant_id          VARCHAR(64)   NOT NULL,
  request_id         VARCHAR(128)  NOT NULL,
  source_ref         VARCHAR(128)  NOT NULL,
  occurred_at        DATETIME(6)   NOT NULL,
  created_at         DATETIME(6)   NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
  actor_id           VARCHAR(128)  NOT NULL,
  supersedes_id      BIGINT UNSIGNED NULL,
  audit_id           BIGINT UNSIGNED NULL COMMENT '关联 audit_log.id',
  forecast_id        VARCHAR(128)  NULL COMMENT '预测体外键（工作台侧 ID）',
  metric_code        VARCHAR(128)  NOT NULL,
  predicted_value    DECIMAL(20,2) NULL COMMENT '单位元（D12）',
  actual_value       DECIMAL(20,2) NULL COMMENT '单位元（D12）',
  currency           CHAR(3)       NOT NULL DEFAULT 'CNY',
  accuracy_label     VARCHAR(16)   NOT NULL COMMENT 'accurate / inaccurate / pending',
  evaluation_version VARCHAR(128)  NOT NULL,
  actual_source_ref  VARCHAR(128)  NOT NULL,
  forecast_start_at  DATETIME(6)   NOT NULL,
  forecast_end_at    DATETIME(6)   NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_feedback_req (tenant_id, request_id),
  KEY idx_feedback_metric (tenant_id, metric_code, evaluation_version, occurred_at),
  KEY idx_feedback_audit (tenant_id, audit_id),
  KEY idx_feedback_forecast (tenant_id, forecast_id),
  KEY idx_feedback_supersedes (supersedes_id),
  CONSTRAINT ck_feedback_ref CHECK (audit_id IS NOT NULL OR forecast_id IS NOT NULL),
  CONSTRAINT ck_feedback_label CHECK (accuracy_label IN ('accurate','inaccurate','pending'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='预警准确度反馈';

-- -----------------------------------------------------------------------------
-- 4. param_template —— 行业参数模板（v8 相对指标版）
--    写入即 draft；发布由可信管理流程执行，不向模型暴露发布权。
--    params 必含 schema_version base_metric yellow_coefficient red_coefficient
--    approval_ratios provenance effective_from；base_metric 固定 monthly_operating_outflow。
-- -----------------------------------------------------------------------------
CREATE TABLE param_template (
  id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tenant_id           VARCHAR(64)   NOT NULL,
  request_id          VARCHAR(128)  NOT NULL,
  source_ref          VARCHAR(128)  NOT NULL,
  occurred_at         DATETIME(6)   NOT NULL,
  created_at          DATETIME(6)   NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
  actor_id            VARCHAR(128)  NOT NULL,
  supersedes_id       BIGINT UNSIGNED NULL,
  industry_key        VARCHAR(128)  NOT NULL COMMENT '制造/零售/建筑/科技服务 的行业代码',
  template_version    VARCHAR(128)  NOT NULL COMMENT '不可覆盖历史版本',
  publication_status  VARCHAR(16)   NOT NULL DEFAULT 'draft' COMMENT 'draft / published / retired',
  params              JSON          NOT NULL,
  provenance          JSON          NOT NULL COMMENT '经验建议 / 企业批准 / 已核验外部来源，三者分标',
  effective_from      DATETIME(6)   NOT NULL,
  published_at        DATETIME(6)   NULL COMMENT '仅由管理身份写入',
  published_by        VARCHAR(128)  NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_tpl_ver (tenant_id, industry_key, template_version),
  UNIQUE KEY uk_tpl_req (tenant_id, request_id),
  KEY idx_tpl_published (tenant_id, industry_key, publication_status, effective_from),
  KEY idx_tpl_supersedes (supersedes_id),
  CONSTRAINT ck_tpl_status CHECK (publication_status IN ('draft','published','retired')),
  CONSTRAINT ck_tpl_publish CHECK (
    (published_at IS NULL AND published_by IS NULL)
    OR (published_at IS NOT NULL AND published_by IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='行业参数模板。历史事件始终引用当时版本';

-- -----------------------------------------------------------------------------
-- 5. exception_log —— 例外放行留痕（不产生审批、不执行付款）
--    trusted_approver_id 由服务端从可信审批系统核实后写入；核实时返回
--    APPROVAL_UNVERIFIED 且不落库为已批准。
-- -----------------------------------------------------------------------------
CREATE TABLE exception_log (
  id                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tenant_id            VARCHAR(64)   NOT NULL,
  request_id           VARCHAR(128)  NOT NULL,
  source_ref           VARCHAR(128)  NOT NULL,
  occurred_at          DATETIME(6)   NOT NULL,
  created_at           DATETIME(6)   NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
  actor_id             VARCHAR(128)  NOT NULL,
  supersedes_id        BIGINT UNSIGNED NULL,
  dept                 VARCHAR(128)  NOT NULL,
  amount               DECIMAL(20,2) NOT NULL COMMENT '单位元（D12）',
  currency             CHAR(3)       NOT NULL DEFAULT 'CNY',
  reason               TEXT          NOT NULL COMMENT '入参上限 4000 字符',
  approval_ref         VARCHAR(128)  NOT NULL COMMENT '可信审批凭据引用',
  approval_status      VARCHAR(16)   NOT NULL COMMENT 'verified / unverified',
  trusted_approver_id  VARCHAR(128)  NULL COMMENT '服务端解析，不采信模型提交的 approver 姓名',
  PRIMARY KEY (id),
  UNIQUE KEY uk_exc_req (tenant_id, request_id),
  UNIQUE KEY uk_exc_approval (tenant_id, approval_ref),
  KEY idx_exc_dept (tenant_id, dept, occurred_at),
  KEY idx_exc_supersedes (supersedes_id),
  CONSTRAINT ck_exc_approval_status CHECK (approval_status IN ('verified','unverified')),
  CONSTRAINT ck_exc_approver CHECK (
    approval_status <> 'verified'
    OR (trusted_approver_id IS NOT NULL AND CHAR_LENGTH(TRIM(trusted_approver_id)) > 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='例外放行台账，季度回溯的统计源';

-- -----------------------------------------------------------------------------
-- 6. stress_test_log —— 压力测试结果（场景由工作台计算，MCP 只存）
--    scenario 白名单 5 值（裁决 A5）：receivable_shock 回款 / financing_shock 融资
--    / cost_shock 成本 / dual_shock 回款+融资 / combined_shock 全项联合。
--    注意：uk_stress_run_scenario(tenant_id,run_id,scenario) 唯一键与"同 run 同场景
--    追加式纠错"存在张力（纠错新行会撞唯一键）——已登记 未决项.md U-02，
--    未批准前不改唯一键。
-- -----------------------------------------------------------------------------
CREATE TABLE stress_test_log (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tenant_id         VARCHAR(64)   NOT NULL,
  request_id        VARCHAR(128)  NOT NULL,
  source_ref        VARCHAR(128)  NOT NULL,
  occurred_at       DATETIME(6)   NOT NULL,
  created_at        DATETIME(6)   NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
  actor_id          VARCHAR(128)  NOT NULL,
  supersedes_id     BIGINT UNSIGNED NULL,
  run_id            VARCHAR(128)  NOT NULL COMMENT '整批压测 ID，五场景共用',
  scenario          VARCHAR(32)   NOT NULL,
  scenario_version  VARCHAR(128)  NOT NULL,
  input_snapshot    JSON          NOT NULL COMMENT 'M、K黄、K红、缺口口径等输入',
  result_snapshot   JSON          NOT NULL COMMENT '最坏缓冲、缓冲倍数、剩余天数',
  risk_level        VARCHAR(10)   NOT NULL COMMENT 'green / yellow / red / unknown（D10）',
  PRIMARY KEY (id),
  UNIQUE KEY uk_stress_req (tenant_id, request_id),
  UNIQUE KEY uk_stress_run_scenario (tenant_id, run_id, scenario),
  KEY idx_stress_run (tenant_id, run_id),
  KEY idx_stress_supersedes (supersedes_id),
  CONSTRAINT ck_stress_scenario CHECK (scenario IN (
    'receivable_shock','financing_shock','cost_shock','dual_shock','combined_shock')),
  CONSTRAINT ck_stress_level CHECK (risk_level IN ('green','yellow','red','unknown'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='常态化压力测试结果';

-- -----------------------------------------------------------------------------
-- 7. payment_verify_log —— 到账验证（模型不得自证 verified）
--    银行连接器未接入时固定 verification_status='pending' + reason='BANK_ADAPTER_UNAVAILABLE'。
--    未通过时 verified_amount 写 0.00，不写 NULL，便于汇总直接求和。
--    uk_pay_txn 用可信流水唯一键防重复核销；pending 阶段该列为 NULL（允许多行）。
-- -----------------------------------------------------------------------------
CREATE TABLE payment_verify_log (
  id                   BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tenant_id            VARCHAR(64)   NOT NULL,
  request_id           VARCHAR(128)  NOT NULL,
  source_ref           VARCHAR(128)  NOT NULL,
  occurred_at          DATETIME(6)   NOT NULL,
  created_at           DATETIME(6)   NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
  actor_id             VARCHAR(128)  NOT NULL,
  supersedes_id        BIGINT UNSIGNED NULL,
  payment_id           VARCHAR(128)  NOT NULL,
  method               VARCHAR(16)   NOT NULL COMMENT 'bank_api / manual_review',
  verification_status  VARCHAR(16)   NOT NULL COMMENT 'pending / verified / rejected',
  verified_amount      DECIMAL(20,2) NOT NULL DEFAULT 0.00 COMMENT '单位元（D12）',
  currency             CHAR(3)       NOT NULL DEFAULT 'CNY',
  evidence_ref         VARCHAR(128)  NOT NULL COMMENT '对象存储引用或摘要，不回传完整账户',
  review_ref           VARCHAR(128)  NULL COMMENT '已认证复核人记录引用',
  reason               VARCHAR(64)   NULL COMMENT '如 BANK_ADAPTER_UNAVAILABLE',
  bank_txn_ref         VARCHAR(128)  NULL COMMENT '可信银行流水唯一键',
  verified_at          DATETIME(6)   NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_pay_req (tenant_id, request_id),
  UNIQUE KEY uk_pay_txn (tenant_id, bank_txn_ref),
  KEY idx_pay_payment (tenant_id, payment_id, occurred_at),
  KEY idx_pay_supersedes (supersedes_id),
  CONSTRAINT ck_pay_method CHECK (method IN ('bank_api','manual_review')),
  CONSTRAINT ck_pay_status CHECK (verification_status IN ('pending','verified','rejected')),
  CONSTRAINT ck_pay_verified CHECK (
    verification_status <> 'verified'
    OR (verified_at IS NOT NULL AND review_ref IS NOT NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='到账验证台账';

-- =============================================================================
-- 三层模型日志表（8/9/10）：采纳队友"任务二"v2.0.0 结构（裁决 D9），并施加
-- 以下已定裁决补丁：
--   D8  ：库 cf_workbench + 排序规则 utf8mb4_0900_ai_ci（payload_sha256 列保留
--         ascii/ascii_bin 列级声明——十六进制哈希与中文文本比较无关，不冲突）；
--   D9  ：补 supersedes_id；request_id VARCHAR(64) → VARCHAR(128)；
--   A2.3：补齐公共列 source_ref / occurred_at / actor_id；
--   D10 ：rf 的 risk_level 中文枚举 ('绿','黄','红') → ('green','yellow','red','unknown')；
--   D13 ：删除 ck_rf_success 中 JSON_LENGTH(features)=30 硬卡，保留 features 与
--         feature_names 等长约束（ck_rf_feature_pair），30 维由服务端按
--         feature_schema_version 校验；
--   D21 ：created_at 默认值改 (UTC_TIMESTAMP(6))。
-- 保留：company_id 与 tenant_id 并存（队友原结构）。company_id 与 tenant_id 的
-- 语义关系未裁决（验收报告 C4）——未批准前不向其余 8 张表扩散 company_id，
-- 已登记 未决项.md U-01（部署阻塞）。
-- =============================================================================

-- 8. quality_log —— 第一层数据质量门禁逐指标结果（表格算出，写来留痕）
CREATE TABLE quality_log (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tenant_id VARCHAR(64) NOT NULL,
  company_id VARCHAR(64) NOT NULL COMMENT '企业编号，不能拿同业批次号冒充',
  run_id VARCHAR(64) NOT NULL,
  request_id VARCHAR(128) NOT NULL,
  record_key VARCHAR(128) NOT NULL COMMENT '同次评估的指标逻辑键，重试保持不变',
  source_ref VARCHAR(128) NOT NULL COMMENT '可定位引用（A2.3 公共列）',
  occurred_at DATETIME(6) NOT NULL COMMENT '事件发生时间 UTC（A2.3 公共列）',
  actor_id VARCHAR(128) NOT NULL COMMENT '从已认证主体解析（A2.3 公共列）',
  supersedes_id BIGINT UNSIGNED DEFAULT NULL COMMENT '纠错：指向被本行替代的原记录（D9）',
  payload_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  execution_status VARCHAR(24) NOT NULL,
  check_date DATE NOT NULL COMMENT '业务评价日；与UTC落库时间区分',
  data_snapshot_id VARCHAR(128) NOT NULL,
  cohort_id VARCHAR(128) DEFAULT NULL COMMENT '同业/样本批次，与company_id分离',
  indicator_name VARCHAR(128) NOT NULL,
  sample_size INT UNSIGNED DEFAULT NULL,
  benford_chi2 DECIMAL(24,10) DEFAULT NULL,
  benford_factor TINYINT UNSIGNED DEFAULT NULL COMMENT '未运行为NULL，不能默认0',
  myer_index DECIMAL(24,10) DEFAULT NULL COMMENT '量纲由myer_scale及algorithm_version说明',
  myer_scale VARCHAR(64) DEFAULT NULL COMMENT '不得猜测0.20与20之间的转换关系',
  myer_factor TINYINT UNSIGNED DEFAULT NULL,
  quality_score DECIMAL(12,10) DEFAULT NULL COMMENT '指标级分数，不能直接当作公司Q',
  company_quality_score DECIMAL(12,10) DEFAULT NULL COMMENT '经批准聚合后公司Q；无聚合结果为NULL',
  aggregation_version VARCHAR(64) DEFAULT NULL,
  risk_flag TINYINT UNSIGNED DEFAULT NULL COMMENT '需复核线索，不是舞弊事实',
  algorithm_version VARCHAR(64) DEFAULT NULL,
  rule_version VARCHAR(64) NOT NULL,
  parameters JSON NOT NULL COMMENT '当次统计口径/阈值/量纲/样本筛选快照',
  input_snapshot JSON NOT NULL COMMENT '受控诊断输入或不可变证据引用',
  result_snapshot JSON DEFAULT NULL,
  error_code VARCHAR(64) DEFAULT NULL,
  error_message TEXT DEFAULT NULL,
  remark TEXT DEFAULT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT (UTC_TIMESTAMP(6)) COMMENT 'UTC（D21）；连接池必须设置time_zone=+00:00',
  PRIMARY KEY (id),
  UNIQUE KEY uq_quality_operation (tenant_id,company_id,run_id,record_key),
  KEY idx_quality_company_date (tenant_id,company_id,check_date),
  KEY idx_quality_run (tenant_id,company_id,run_id),
  KEY idx_quality_supersedes (supersedes_id),
  CONSTRAINT ck_quality_identity CHECK (CHAR_LENGTH(TRIM(tenant_id))>0 AND CHAR_LENGTH(TRIM(company_id))>0 AND CHAR_LENGTH(TRIM(run_id))>0 AND CHAR_LENGTH(TRIM(record_key))>0 AND CHAR_LENGTH(TRIM(request_id))>0),
  CONSTRAINT ck_quality_hash CHECK (payload_sha256 REGEXP '^[0-9a-f]{64}$'),
  CONSTRAINT ck_quality_status CHECK (execution_status IN ('success','skipped','insufficient_data','error')),
  CONSTRAINT ck_quality_numbers CHECK ((benford_chi2 IS NULL OR benford_chi2>=0) AND (myer_index IS NULL OR myer_index>=0)),
  CONSTRAINT ck_quality_flags CHECK ((benford_factor IS NULL OR benford_factor IN (0,1)) AND (myer_factor IS NULL OR myer_factor IN (0,1)) AND (risk_flag IS NULL OR risk_flag IN (0,1))),
  CONSTRAINT ck_quality_scores CHECK ((quality_score IS NULL OR quality_score BETWEEN 0 AND 1) AND (company_quality_score IS NULL OR company_quality_score BETWEEN 0 AND 1)),
  CONSTRAINT ck_quality_aggregate CHECK ((company_quality_score IS NULL AND aggregation_version IS NULL) OR (company_quality_score IS NOT NULL AND aggregation_version IS NOT NULL AND CHAR_LENGTH(TRIM(aggregation_version))>0)),
  CONSTRAINT ck_quality_success CHECK (execution_status<>'success' OR (sample_size IS NOT NULL AND sample_size>0 AND benford_chi2 IS NOT NULL AND benford_factor IS NOT NULL AND myer_index IS NOT NULL AND myer_scale IS NOT NULL AND CHAR_LENGTH(TRIM(myer_scale))>0 AND myer_factor IS NOT NULL AND quality_score IS NOT NULL AND risk_flag IS NOT NULL AND algorithm_version IS NOT NULL AND CHAR_LENGTH(TRIM(algorithm_version))>0 AND result_snapshot IS NOT NULL)),
  CONSTRAINT ck_quality_uncomputed CHECK (execution_status='success' OR (benford_chi2 IS NULL AND benford_factor IS NULL AND myer_index IS NULL AND myer_factor IS NULL AND quality_score IS NULL AND company_quality_score IS NULL AND risk_flag IS NULL)),
  CONSTRAINT ck_quality_error CHECK (execution_status<>'error' OR (error_code IS NOT NULL AND CHAR_LENGTH(TRIM(error_code))>0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='模型日志v2：指标质量诊断，聚合Q须另有版本';

-- 9. deada_score_log —— 第二层判别得分（权重稀疏，可解释性留证）
CREATE TABLE deada_score_log (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tenant_id VARCHAR(64) NOT NULL,
  company_id VARCHAR(64) NOT NULL,
  run_id VARCHAR(64) NOT NULL,
  request_id VARCHAR(128) NOT NULL,
  record_key VARCHAR(128) NOT NULL,
  source_ref VARCHAR(128) NOT NULL,
  occurred_at DATETIME(6) NOT NULL,
  actor_id VARCHAR(128) NOT NULL,
  supersedes_id BIGINT UNSIGNED DEFAULT NULL,
  payload_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  execution_status VARCHAR(24) NOT NULL,
  eval_date DATE NOT NULL,
  data_snapshot_id VARCHAR(128) NOT NULL,
  input_weights JSON DEFAULT NULL,
  output_weights JSON DEFAULT NULL,
  core_indicators JSON DEFAULT NULL COMMENT '实际模型输入指标映射，设计为7项；与特征清单核对',
  feature_schema JSON DEFAULT NULL COMMENT '有序特征名、单位和预处理清单',
  intercept DECIMAL(28,12) DEFAULT NULL COMMENT '如模型无截距，成功时显式写0，不能遗漏',
  discriminant_score DECIMAL(28,12) DEFAULT NULL,
  threshold DECIMAL(28,12) DEFAULT NULL COMMENT '当次模型临界值，不在日志层擅自写死',
  is_risk TINYINT UNSIGNED DEFAULT NULL COMMENT '仅D<threshold，未运行为NULL',
  model_version VARCHAR(64) DEFAULT NULL,
  preprocess_version VARCHAR(64) DEFAULT NULL,
  rule_version VARCHAR(64) NOT NULL,
  result_snapshot JSON DEFAULT NULL,
  error_code VARCHAR(64) DEFAULT NULL,
  error_message TEXT DEFAULT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
  PRIMARY KEY (id),
  UNIQUE KEY uq_deada_operation (tenant_id,company_id,run_id,record_key),
  KEY idx_deada_company_date (tenant_id,company_id,eval_date),
  KEY idx_deada_run (tenant_id,company_id,run_id),
  KEY idx_deada_supersedes (supersedes_id),
  CONSTRAINT ck_deada_identity CHECK (CHAR_LENGTH(TRIM(tenant_id))>0 AND CHAR_LENGTH(TRIM(company_id))>0 AND CHAR_LENGTH(TRIM(run_id))>0 AND CHAR_LENGTH(TRIM(record_key))>0 AND CHAR_LENGTH(TRIM(request_id))>0),
  CONSTRAINT ck_deada_hash CHECK (payload_sha256 REGEXP '^[0-9a-f]{64}$'),
  CONSTRAINT ck_deada_status CHECK (execution_status IN ('success','skipped','insufficient_data','error')),
  CONSTRAINT ck_deada_flag CHECK (is_risk IS NULL OR is_risk IN (0,1)),
  CONSTRAINT ck_deada_success CHECK (execution_status<>'success' OR (input_weights IS NOT NULL AND output_weights IS NOT NULL AND core_indicators IS NOT NULL AND feature_schema IS NOT NULL AND intercept IS NOT NULL AND discriminant_score IS NOT NULL AND threshold IS NOT NULL AND is_risk IS NOT NULL AND model_version IS NOT NULL AND CHAR_LENGTH(TRIM(model_version))>0 AND preprocess_version IS NOT NULL AND CHAR_LENGTH(TRIM(preprocess_version))>0 AND result_snapshot IS NOT NULL)),
  CONSTRAINT ck_deada_consistency CHECK (execution_status<>'success' OR is_risk=IF(discriminant_score<threshold,1,0)),
  CONSTRAINT ck_deada_uncomputed CHECK (execution_status='success' OR (discriminant_score IS NULL AND is_risk IS NULL)),
  CONSTRAINT ck_deada_error CHECK (execution_status<>'error' OR (error_code IS NOT NULL AND CHAR_LENGTH(TRIM(error_code))>0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='模型日志v2：DEA-DA输入权重及可复现分数';

-- 10. rf_predict_log —— 第三层异常样本概率推理留痕（唯一计算型工具的副作用记录）
--     训练标签为 ST/风险，与「舞弊」不等同（包 B 任务书 §9）；probability_target 必填，
--     model_version 与实际推理库版本一起记录（裁决 D22）。
CREATE TABLE rf_predict_log (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tenant_id VARCHAR(64) NOT NULL,
  company_id VARCHAR(64) NOT NULL,
  run_id VARCHAR(64) NOT NULL,
  request_id VARCHAR(128) NOT NULL,
  record_key VARCHAR(128) NOT NULL,
  source_ref VARCHAR(128) NOT NULL,
  occurred_at DATETIME(6) NOT NULL,
  actor_id VARCHAR(128) NOT NULL,
  supersedes_id BIGINT UNSIGNED DEFAULT NULL,
  payload_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  execution_status VARCHAR(24) NOT NULL,
  eval_date DATE NOT NULL,
  data_snapshot_id VARCHAR(128) NOT NULL,
  features JSON DEFAULT NULL,
  feature_names JSON DEFAULT NULL COMMENT '与特征值一一对应的有序名称',
  feature_schema_version VARCHAR(64) DEFAULT NULL,
  preprocess_version VARCHAR(64) DEFAULT NULL,
  fraud_probability DECIMAL(12,10) DEFAULT NULL COMMENT '保留旧列名；实际含义必须看probability_target，不能默认舞弊',
  probability_target VARCHAR(128) DEFAULT NULL COMMENT '训练标签定义与阳性类别，须经确认',
  risk_level VARCHAR(16) DEFAULT NULL COMMENT '可选审阅标签，不是最终融合灯；无批准规则时NULL',
  model_version VARCHAR(64) DEFAULT NULL,
  rule_version VARCHAR(64) NOT NULL,
  result_snapshot JSON DEFAULT NULL,
  error_code VARCHAR(64) DEFAULT NULL,
  error_message TEXT DEFAULT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
  PRIMARY KEY (id),
  UNIQUE KEY uq_rf_operation (tenant_id,company_id,run_id,record_key),
  KEY idx_rf_company_date (tenant_id,company_id,eval_date),
  KEY idx_rf_run (tenant_id,company_id,run_id),
  KEY idx_rf_supersedes (supersedes_id),
  CONSTRAINT ck_rf_identity CHECK (CHAR_LENGTH(TRIM(tenant_id))>0 AND CHAR_LENGTH(TRIM(company_id))>0 AND CHAR_LENGTH(TRIM(run_id))>0 AND CHAR_LENGTH(TRIM(record_key))>0 AND CHAR_LENGTH(TRIM(request_id))>0),
  CONSTRAINT ck_rf_hash CHECK (payload_sha256 REGEXP '^[0-9a-f]{64}$'),
  CONSTRAINT ck_rf_status CHECK (execution_status IN ('success','skipped','insufficient_data','error')),
  CONSTRAINT ck_rf_probability CHECK (fraud_probability IS NULL OR fraud_probability BETWEEN 0 AND 1),
  CONSTRAINT ck_rf_level CHECK (risk_level IS NULL OR risk_level IN ('green','yellow','red','unknown')),
  CONSTRAINT ck_rf_features CHECK ((features IS NULL OR JSON_TYPE(features)='ARRAY') AND (feature_names IS NULL OR JSON_TYPE(feature_names)='ARRAY')),
  CONSTRAINT ck_rf_feature_pair CHECK (features IS NULL OR feature_names IS NULL OR JSON_LENGTH(features)=JSON_LENGTH(feature_names)),
  CONSTRAINT ck_rf_success CHECK (execution_status<>'success' OR (features IS NOT NULL AND feature_names IS NOT NULL AND JSON_LENGTH(features)=JSON_LENGTH(feature_names) AND feature_schema_version IS NOT NULL AND CHAR_LENGTH(TRIM(feature_schema_version))>0 AND preprocess_version IS NOT NULL AND CHAR_LENGTH(TRIM(preprocess_version))>0 AND fraud_probability IS NOT NULL AND probability_target IS NOT NULL AND CHAR_LENGTH(TRIM(probability_target))>0 AND model_version IS NOT NULL AND CHAR_LENGTH(TRIM(model_version))>0 AND result_snapshot IS NOT NULL)),
  CONSTRAINT ck_rf_uncomputed CHECK (execution_status='success' OR (fraud_probability IS NULL AND risk_level IS NULL)),
  CONSTRAINT ck_rf_error CHECK (execution_status<>'error' OR (error_code IS NOT NULL AND CHAR_LENGTH(TRIM(error_code))>0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='模型日志v2：随机森林目标概率与有序特征（D13：不硬卡30维）';

-- -----------------------------------------------------------------------------
-- 11. da_coefficient —— DEA-DA 权重系数表（离线求解，MCP 只存取，不求解）
--     每行一个指标在某版本下的权重；千问表格用 SUMPRODUCT 按版本取权重算 D。
--     A2.3 公共列补齐：occurred_at / supersedes_id。
-- -----------------------------------------------------------------------------
CREATE TABLE da_coefficient (
  id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tenant_id        VARCHAR(64)    NOT NULL,
  request_id       VARCHAR(128)   NOT NULL,
  source_ref       VARCHAR(128)   NOT NULL COMMENT '离线求解脚本产物引用',
  occurred_at      DATETIME(6)    NOT NULL COMMENT '事件发生时间 UTC（A2.3 公共列）',
  created_at       DATETIME(6)    NOT NULL DEFAULT (UTC_TIMESTAMP(6)),
  actor_id         VARCHAR(128)   NOT NULL,
  supersedes_id    BIGINT UNSIGNED NULL COMMENT '纠错：指向被本行替代的原记录（D9/A2.3）',
  industry_key     VARCHAR(128)   NOT NULL,
  coefficient_version VARCHAR(128) NOT NULL,
  indicator_code   VARCHAR(64)    NOT NULL,
  indicator_name   VARCHAR(128)   NOT NULL,
  io_role          VARCHAR(8)     NOT NULL COMMENT 'input / output',
  direction        VARCHAR(8)     NOT NULL COMMENT 'positive / inverse（逆指标先取倒数）',
  weight           DECIMAL(18,10) NOT NULL,
  returns_to_scale VARCHAR(8)     NOT NULL DEFAULT 'VRS' COMMENT 'CRS / VRS（BCC）',
  solved_at        DATETIME(6)    NOT NULL,
  solver_ref       VARCHAR(255)   NOT NULL COMMENT '求解脚本版本与样本区间，可追溯',
  PRIMARY KEY (id),
  UNIQUE KEY uk_coef_row (tenant_id, industry_key, coefficient_version, indicator_code),
  UNIQUE KEY uk_coef_req (tenant_id, request_id),
  KEY idx_coef_supersedes (supersedes_id),
  CONSTRAINT ck_coef_io_role CHECK (io_role IN ('input','output')),
  CONSTRAINT ck_coef_direction CHECK (direction IN ('positive','inverse')),
  CONSTRAINT ck_coef_rts CHECK (returns_to_scale IN ('CRS','VRS'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
  COMMENT='判别权重，稀疏可解释';

-- =============================================================================
-- 视图（10 个）：统计口径统一从这里出，避免各工具各写一遍 SQL 造成口径漂移。
-- 纠错替代链查询一律同时限定同一 tenant_id（防跨租户误判与重复计数）。
-- 与原 v1.0 的差异：原文件注释声称"8 视图"但实际只定义 7 个（差异已登记
-- 改动清单.md）；v1.1 修正既有 7 个并新增三层日志活跃视图 3 个，共 10 个。
-- 聚合维度与排序字段必须由 app.py 白名单放行，禁止拼接模型给的列名（协议 §八）。
-- =============================================================================

-- [1] 审计活跃记录：排除被替代版本（同租户内判定），防重复计数
CREATE OR REPLACE VIEW v_record_active AS
SELECT a.* FROM audit_log a
WHERE NOT EXISTS (
  SELECT 1 FROM audit_log s
  WHERE s.supersedes_id = a.id AND s.tenant_id = a.tenant_id);

-- [2] 规则触发统计。注意：统计的是「预警事件数」，不等于准确率（协议 §5.2）
CREATE OR REPLACE VIEW v_rule_stats AS
SELECT tenant_id, rule_id, rule_version, risk_level,
       COUNT(*) AS event_count,
       MIN(occurred_at) AS first_at,
       MAX(occurred_at) AS last_at
FROM v_record_active
GROUP BY tenant_id, rule_id, rule_version, risk_level;

-- [3] 反馈按标签汇总。不在此计算通用准确率：分母、成熟观察期、缺失处理未定（协议 §5.3）
CREATE OR REPLACE VIEW v_feedback_label_counts AS
SELECT tenant_id, metric_code, evaluation_version, accuracy_label,
       COUNT(*) AS label_count
FROM feedback_log f
WHERE NOT EXISTS (
  SELECT 1 FROM feedback_log s
  WHERE s.supersedes_id = f.id AND s.tenant_id = f.tenant_id)
GROUP BY tenant_id, metric_code, evaluation_version, accuracy_label;

-- [4] 例外笔数与金额。例外率的分母需要同范围审批总笔数，缺失时上层必须返回 null（协议 §5.5）
CREATE OR REPLACE VIEW v_exception_stats AS
SELECT tenant_id, dept,
       COUNT(*)    AS exception_count,
       SUM(amount) AS exception_amount_sum,
       MIN(occurred_at) AS first_at,
       MAX(occurred_at) AS last_at
FROM exception_log e
WHERE NOT EXISTS (
  SELECT 1 FROM exception_log s
  WHERE s.supersedes_id = e.id AND s.tenant_id = e.tenant_id)
GROUP BY tenant_id, dept;

-- [5] 压测批次进度：scenarios_done < 5 时禁止对外声明整批成功（协议 §5.6；
--     裁决 A5 场景由 4 扩为 5，required 由 4 改 5）。
--     排除被替代版本：同 run+scenario 的纠错语义受唯一键限制（见 未决项.md U-02），
--     视图层仍防御性排除。
CREATE OR REPLACE VIEW v_stress_run_progress AS
SELECT tenant_id, run_id,
       COUNT(DISTINCT scenario) AS scenarios_done,
       5                        AS scenarios_required,
       COUNT(DISTINCT scenario) < 5 AS is_partial,
       MAX(created_at)          AS last_write_at
FROM stress_test_log t
WHERE NOT EXISTS (
  SELECT 1 FROM stress_test_log s
  WHERE s.supersedes_id = t.id AND s.tenant_id = t.tenant_id)
GROUP BY tenant_id, run_id;

-- [6] 已验证到账汇总（供三态跟踪核对「待验证不计入缓冲」）
CREATE OR REPLACE VIEW v_verified_payment_sum AS
SELECT tenant_id,
       SUM(verified_amount) AS verified_amount_sum,
       COUNT(*)             AS verified_count
FROM payment_verify_log p
WHERE verification_status = 'verified'
  AND NOT EXISTS (
    SELECT 1 FROM payment_verify_log s
    WHERE s.supersedes_id = p.id AND s.tenant_id = p.tenant_id)
GROUP BY tenant_id;

-- [7] 当前已发布的行业模板最新版本（load_param_template 省略版本号时的语义）
CREATE OR REPLACE VIEW v_template_published_latest AS
SELECT p.tenant_id, p.industry_key, p.template_version, p.params, p.provenance,
       p.effective_from, p.published_at
FROM param_template p
WHERE p.publication_status = 'published'
  AND p.effective_from = (
    SELECT MAX(p2.effective_from) FROM param_template p2
    WHERE p2.tenant_id = p.tenant_id AND p2.industry_key = p.industry_key
      AND p2.publication_status = 'published' AND p2.effective_from <= UTC_TIMESTAMP(6)
  );

-- [8] 质量门禁活跃记录（新增：三层日志表同样追加式纠错，须排除被替代版本）
CREATE OR REPLACE VIEW v_quality_active AS
SELECT q.* FROM quality_log q
WHERE NOT EXISTS (
  SELECT 1 FROM quality_log s
  WHERE s.supersedes_id = q.id AND s.tenant_id = q.tenant_id);

-- [9] DEA-DA 活跃记录（新增）
CREATE OR REPLACE VIEW v_deada_active AS
SELECT d.* FROM deada_score_log d
WHERE NOT EXISTS (
  SELECT 1 FROM deada_score_log s
  WHERE s.supersedes_id = d.id AND s.tenant_id = d.tenant_id);

-- [10] 随机森林推理活跃记录（新增）
CREATE OR REPLACE VIEW v_rf_active AS
SELECT r.* FROM rf_predict_log r
WHERE NOT EXISTS (
  SELECT 1 FROM rf_predict_log s
  WHERE s.supersedes_id = r.id AND s.tenant_id = r.tenant_id);

-- =============================================================================
-- 授权：本文件不含任何 CREATE USER / GRANT / FLUSH PRIVILEGES。
-- 账号 cf_admin / cf_app / cf_backup / cf_read 已存在（WB-SRV-001 实测），
-- 初始化表结构与账号创建/授权分离（任务书第 3 条）。
-- cf_admin 执行本脚本所需权限核对：SELECT/INSERT/UPDATE/CREATE/ALTER/DROP/INDEX/
-- REFERENCES 已具备；CREATE VIEW、SHOW VIEW 缺失 → 最小权限变更候选见
-- grants_admin_view_候选.sql（待 Codex 批准后由部署任务执行，本文件不执行）。
-- =============================================================================

-- =============================================================================
-- 落地后自检（手工执行，确认 11 表 + 10 视图齐全）
--   SHOW TABLES;                                   -- 期望 11 张表
--   SHOW FULL TABLES WHERE Table_type='VIEW';      -- 期望 10 个视图
--   SELECT @@character_set_database, @@collation_database;
--     -- 期望 utf8mb4 / utf8mb4_0900_ai_ci
--   SELECT table_name FROM information_schema.tables
--    WHERE table_schema='cf_workbench' AND table_type='BASE TABLE';  -- 11
-- =============================================================================
