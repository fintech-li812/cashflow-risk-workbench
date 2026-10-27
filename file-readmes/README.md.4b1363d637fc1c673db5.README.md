# 文件说明：README.md

- 仓库路径：AI_Command_Workspace/验收/CX-TOOL-BIND-001/Codex开发自测/v1/ZIP解压复现/README.md
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/CX-TOOL-BIND-001/Codex%E5%BC%80%E5%8F%91%E8%87%AA%E6%B5%8B/v1/ZIP%E8%A7%A3%E5%8E%8B%E5%A4%8D%E7%8E%B0/README.md)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：3916字节
- 导出SHA256：b7aa929522044a7e38b99eaf414f8a331ef426fdb8f3ccf3f548bb4260167d7c

## 内容与作用

标题/章节：MCP工具调用前契约检查（离线候选，待独审）；适用位置；检查范围；复现；明确限制；时间格式与历史对照补充；完整自测与审阅

内容开头：本工具不执行MCP调用，只对调用方传入的工具描述符和参数做完整JSON Schema检查。输出prepared仅表示本地参数检查通过；不表示平台已绑定、调用成功、数据库提交或获准发布。 Agent现有build_save_payload生成参数后，由适配器取得真实tools/list描述符，再调用prepare。这里尚未接入该适配器，不修改既有Agent原交付。当前没有实际平台tools/list证据，所有测试为显式合成fixture。 调用方必须从可信会话提供approved_name、expected_context的tenant_id/company_id/period/source_revision/run_id、expected_request_id，以及六个字段在参数中的JSON

## 打开与使用

文本/代码编辑器；HTML按所属说明预览。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
