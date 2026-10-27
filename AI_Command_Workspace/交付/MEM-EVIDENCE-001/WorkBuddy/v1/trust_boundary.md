# trust_boundary.md（MEM-EVIDENCE-001 候选 v1）

## 信任入口在哪

本模块的 `get`/`history`/`save` 接受的 `tenant_id`/`company_id`/`period`/`source_revision`/`run_id`
来自调用者提供的 **context 文件**。在候选阶段，这个 context 是**测试信任入口**：
runner 与 selftest 使用 `fixtures/context_trusted.json`（合成）作为"可信调用上下文"。

**CLI 自填 tenant/company 不是认证。** 跨身份负例（TC-14）的语义是：在"调用方已被某个
可信上下文绑定"的前提下，模块防止用别的身份字符串混查；测试中用独立的可信上下文夹具
（context_other_tenant.json）扮演另一个身份，而不是比较两个用户自填字符串。

## 生产身份绑定由谁做

平台运行时（千问 Agent 适配层）应由认证/绑定层生成可信五字段，本模块只负责
"payload 五字段必须与可信 context 逐项一致"。该绑定**未实现、未接线**：
本候选不能声称已实现平台鉴权或租户隔离的生产级保证。

## 篡改检测的边界（如实声明）

verify-store 能检出：
- 直接改 payload_json（哈希不符，TC-20）
- 改索引列身份字段（record_id 关联与 payload 一致性不符，TC-21）
- 改 record_id / request_id / stored_at 等关联字段（重算关联不符）
- success payload 的勾稽破坏（重跑校验失败）

**不能抵御**：能重写整个数据库文件**并且**同时重算所有 payload_sha256、record_id 的攻击者
——普通哈希不是密码学认证，本模块不提供也不宣传"不可篡改审计日志"。
要抵御该类攻击需要外部可信锚（如定期把清单哈希外发到独立系统），属后续部署议题，本包不做。

## 其他边界

- record_id 是本地确定性 ID，不是 MySQL 主键；`committed` 仅指本地 SQLite 原子提交完成。
- 数据库文件只在调用者指定的测试工作目录创建；不读写项目库、桌面、密钥目录。
- 日志/错误输出脱敏：不含完整流水、金额明细、凭据。
- 本包不连接网络、不连生产库、不做财务计算，无任何对外发送能力。
