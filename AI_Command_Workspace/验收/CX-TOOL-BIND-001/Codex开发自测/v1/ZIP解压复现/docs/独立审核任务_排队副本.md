# DS-AUD-TOOL-BIND-001 独立审核任务（待X唤醒，串行）

审核对象：交付/CX-TOOL-BIND-001/Codex/v1。开发者Codex；不得由其自签独审。此任务排在既有QA v2、Agent修复v1、发布检查v1独审之后；由Codex看板明确交接后执行，文件本身不会唤醒你。

1. 独立验证manifest、SHA、ZIP内容；在副本重跑61方法和6变异，不能只看开发日志。
2. 自造schema绕过反例：allOf/if/then、oneOf、additionalProperties、嵌套本地引用/失效引用、外部$ref及动态引用、混合方言、自定义vocabulary/format；确保未发生网络检索。
3. 逐一篡改tenant/company/period/source_revision/run_id/request_id，确认阻断且不泄露原值。检查不能通过配置或参数自证可信身份的合入边界说明。
4. 验证严格JSON重复键/NaN/1e999/资源限制、date-time日历和时区边界、错误摘要脱敏、深复制和摘要稳定性。特别检查标准库时间子集是否被误称完整RFC3339。
5. 检查prepared是工具本地状态，没有加入Agent业务闭集，不生成receipt或committed；无数据库/HTTP/MCP传输路径。
6. 独立指出未做的工作：未自动合入Agent、没有真实tools/list、未认证、未验证公式/来源/保存；14候选schema兼容不能代替上线。
7. 已知限制：恶意正则/递归schema没有进程硬超时；只允许已审查描述符。评估该边界对本地候选是否可接受，未处理的上线风险必须列出。

输出：验收/DS-AUD-TOOL-BIND-001/DeepSeek/v1/审核报告.md，结论通过/打回/阻塞；每项问题编号、严重性、绝对文件路径与行号、最小输入、实测/预期、原因、修改意见、复测标准。代码冻结，不覆盖开发原件。所有结果统一交X检查。
