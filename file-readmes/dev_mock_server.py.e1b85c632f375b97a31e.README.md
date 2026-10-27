# 文件说明：dev_mock_server.py

- 仓库路径：CashflowRiskWorkbench/mcp-server/dev_mock_server.py
- 查看文件：[打开原文件](../CashflowRiskWorkbench/mcp-server/dev_mock_server.py)
- 归属：程序实现/启动或接口支持
- 大小：15063字节
- 导出SHA256：ae3fceef30e211b56c43f0b15d5f5adf6faafaf40319f98faad6cec7f73a3917

## 内容与作用

模块说明：dev_mock_server.py — 发包方自备的 MCP 靶机（不属外包交付物）

用途：仅用于验收 mcp_smoke_test.py 的判定逻辑是否正确，不接真实 MySQL。
两种模式（环境变量 STRICT_PROPS）：
  1（默认）严格：按工具 JSON Schema 校验 required + additionalProperties:false
  0 宽松  ：忽略未声明字段，只校验业务规则
端口由 --port 指定。状态仅存内存，进程退出即消失。

主要函数：\`envelope\`, \`validate\`, \`dispatch\`

主要类：\`H\`

命令行选项：--port；运行前先读所属README。

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
