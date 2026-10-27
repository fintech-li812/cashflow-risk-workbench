# 接口映射

依据：333.md F 项；规则/制造业Agent周边工程统一接口_v1.md。
本包只做**非算法外围**，与三个队友包按统一接口衔接；队友正式包到货后**串行替换适配**。

## 一、本包四类内部能力 ↔ 统一接口工件

| 本包内部能力（不是对外 MCP 工具名） | 读取/写入的工件 | 关键字段 | 当前绑定状态 |
|---|---|---|---|
| `read_snapshot` | `mfg-import.v1`（manifest/inventory/records/issues） | `workbook_ref` `sheet` `range` `snapshot_ref` `source_revision` | **未绑定**，返回 unavailable + 人工取证步骤 |
| `read_calculated_result` | `mfg-agent-result.v1` | 五字段 + `calculation_version` `origin` `unit` `coverage` `source` `amounts` | **未绑定**，算法未就绪返回 unavailable，不产生金额 |
| `save_result` | `mfg-evidence.v1`（kind=receipt） | 五字段 + `request_id` `payload_sha256` `record_id` `stored_at` `status` | **未绑定**，需实际工具 inputSchema |
| `query_saved_result` | `mfg-evidence.v1` 回查 | `request_id` + `payload_sha256` | **未绑定**，无精确回查能力时报阻塞 |

## 二、与三队友包的衔接点

| 队友包 | 本包依赖它的什么 | 本包提供给它的什么 | 当前处理 |
|---|---|---|---|
| **MEM-IMPORT-002**（导入） | `source_revision` 计算规则、records 的单元格级来源、issues 分类 | `read_snapshot` 消费其 manifest/inventory | 未到货；本包用**自己明确标识的合成夹具**自测，不等待 |
| **MEM-EVIDENCE-001**（存储） | 真实存储回执 `record_id`、按 `request_id` 精确回查能力 | `save_result` / `query_saved_result` 的调用形状与幂等约定 | 未到货；本包提供 `MemoryEvidenceStore` 作**本地参考实现**（进程内，非数据库） |
| **MEM-QA-001**（验收） | 独立预期与验收断言 | 本包 44 项自测输出、六项红线用例 | 未到货；本包已按 333.md 的六项打回项各写专项用例 |

替换方式：队友包到货后，只需实现 `Backend` 的四个方法（或替换 `MemoryEvidenceStore`），
`RequestFlow` 与守卫链路**不需改动**。这是本包刻意留出的适配缝。

## 三、字段映射表（结果 → 保存载荷）

严格按实际工具 `inputSchema` 逐字段映射；未取得真实 schema 时返回 unavailable，不预设字段名提交。

| 保存载荷字段 | 来源 |
|---|---|
| `tenant_id` `company_id` `period` `source_revision` `run_id` | binding 五字段 |
| `request_id` | 本次逻辑保存标识（重试沿用同一个） |
| `schema_version` `industry` `status` `origin` `unit` `coverage` `calculation_version` `source` `amounts` | 结果对象同名字段 |

映射表常量在 `candidate/persistence.py: FIELD_MAPPING`，实际字段名以平台 `tools/list` 为准。

## 四、状态闭集对照（避免混用）

| 本包状态 | 含义 | 不是什么 |
|---|---|---|
| `unavailable` | 能力未绑定/未就绪 | 不是 gate_ 结果、不是风险灯 |
| `pending` | 提交已发出但未取得确定回执 | **不是成功**，也不是失败 |
| `conflict` | 同 `request_id` 载荷不同 | 不覆盖旧记录 |
| `not_found` | 该 request_id 无记录 | 不等于保存失败 |
| `committed` | 已取得确定回执 | 仅指本地/已绑定存储，不声称 MySQL 已入库 |

结果侧 `success/missing_inputs/formula_error/unavailable` 沿用继承的 `agent_guard` 闭集，
本包未新增状态值。

## 五、明确不做的衔接

- 不新增生产 `event_type`，不新增 SQL 列，不新增 gate_ 词表
- 不代替 MEM-EVIDENCE-001 实现真实 MySQL 存储
- 不代替算法队友实现现金流计算
