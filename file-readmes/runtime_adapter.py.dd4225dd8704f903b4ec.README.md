# 文件说明：runtime_adapter.py

- 仓库路径：AI_Command_Workspace/验收/CX-TOOL-BIND-001/Codex开发自测/v1/ZIP解压复现/reference-agent/runtime_adapter.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/CX-TOOL-BIND-001/Codex%E5%BC%80%E5%8F%91%E8%87%AA%E6%B5%8B/v1/ZIP%E8%A7%A3%E5%8E%8B%E5%A4%8D%E7%8E%B0/reference-agent/runtime_adapter.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：14138字节
- 导出SHA256：4159d501467098a919ab19bdb3a25c0e870bfc6c6677d393772ed4e8fe96e87d

## 内容与作用

模块说明：WB-AGENT-003 运行适配层：四类内部能力接口（不是对外 MCP 工具名）。

范围依据：333.md A 项；接口口径依据：规则/制造业Agent周边工程统一接口_v1.md。

本模块只做三件事：
  1. 定义 read_snapshot / read_calculated_result / save_result / query_saved_result
     四类内部能力的调用形状与返回状态；
  2. 在未绑定真实千问读表 / 表格公式 / 存储工具时，返回结构化 unavailable
     与缺项清单，并给出人工导入证据流程；
  3. 提供显式测试夹具通道，且生产模式下禁用。

本模块不做：不实现算法、不计算金额、不连接服务器、不读写生产库、
不伪造任何平台 API 或网页端点、不把合成夹具当作真实结果。

主要函数：\`canonical_json\`, \`canonical_sha256\`, \`unavailable\`, \`read_snapshot\`, \`read_calculated_result\`, \`save_result\`, \`receipt_problem\`, \`query_saved_result\`

主要类：\`Binding\`, \`Outcome\`, \`Backend\`, \`UnboundBackend\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
