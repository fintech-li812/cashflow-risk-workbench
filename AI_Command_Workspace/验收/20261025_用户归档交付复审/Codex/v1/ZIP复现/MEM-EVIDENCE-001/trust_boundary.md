# 信任边界说明（trust_boundary.md）

版本：MEM-EVIDENCE-001 v1。**本包未接入任何生产认证**，本文如实说明"谁信任谁、信到什么程度"。

## 1. 各入口的信任归属

| 入口 | 由谁提供 | 信任等级 | 说明 |
|---|---|---|---|
| `--context <JSON>` | 调用方（当前为测试调用者） | **测试可信上下文** | 本包把它当作"已绑定身份"的来源，直接用于身份匹配与越权判定 |
| CLI 自填 `--tenant-id/--company-id` | 调用方 | **不信任** | 仅作一致性校验；与可信上下文不符即 SCOPE_DENIED（退出码 6） |
| `--input <结果JSON>` 中的身份字段 | 上游结果 | **不信任** | 必须逐字段与可信上下文相等，否则 VALIDATION_FAILED（退出码 3） |
| `origin` 字段 | 上游结果 | **不信任为安全凭据** | 标签本身不能证明真实来源；`qwen_sheet` 之外的 `offline_fixture` 只在显式 `--allow-fixture` 下接受 |
| `--store` 路径 | 调用方 | 半信任 | 必须落在 `--workdir` 内且后缀 `.sqlite3`，否则拒绝（退出码 2） |

## 2. 明确没有实现的能力

- **没有平台鉴权**：不由 WorkBuddy 绑定认证生成身份，不校验用户/令牌/权限。生产身份绑定由 WorkBuddy 平台侧实现，本包不得声称已实现平台鉴权。
- **没有传输/存储加密**：SQLite 文件明文存储，依赖文件系统权限。
- **没有防篡改保证**：payload_sha256 只能检出"未同步改写全部可信摘要"的改动。能重写整个库及全部摘要的攻击者不在防护范围内，本包不宣称不可篡改审计或完整密码学认证。
- **没有服务端证明**：`status=committed` 仅表示本地事务已提交，不等于千问/MySQL 已入库。

## 3. 跨身份负例为什么用"固定独立可信上下文"

任务要求跨身份负例不能只比较两个用户自填字符串。本包做法：

- 正式记录用 `fixtures/trusted_context.json`（fixture-tenant / fixture-company）创建；
- 负例改用**另一份独立固定的可信上下文文件** `fixtures/trusted_context_other.json`（other-tenant / other-company），
  用它调用 get/history，由存储层按 tenant+company 边界判定，得到 SCOPE_DENIED（退出码 6）且响应不含原记录内容；
- 另有一例在**同一份可信上下文**下额外自填 `--tenant-id other-tenant`，同样被判 SCOPE_DENIED。
两者语义不同：前者是"另一个可信身份来读"，后者是"同一可信身份下自填绕过"，都必须被拒。

## 4. 脱敏约定

- 日志与 JSON 输出只含：record_id、摘要前 12 位、身份 ID、状态、错误码、字段名。
- 不打印完整流水；history 默认只返回元数据，`--verbose` 才带金额。
- 错误信息不含绝对路径、不含凭据、不含他家记录内容。
- 交付包内不含任何口令、令牌、私钥或真实个人流水。
