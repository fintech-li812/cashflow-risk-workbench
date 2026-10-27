# 文件说明：mcp_smoke_test.py

- 仓库路径：CashflowRiskWorkbench/docs/外包交付/mcp_smoke_test.py
- 查看文件：[打开原文件](../CashflowRiskWorkbench/docs/%E5%A4%96%E5%8C%85%E4%BA%A4%E4%BB%98/mcp_smoke_test.py)
- 归属：设计、规则或计划文档；注意历史口径与最新用户决定
- 大小：59854字节
- 导出SHA256：8e44064a1dc073dc22e3822e89265b61c1c992749456bc2d3288a5b9f192c1ba

## 内容与作用

模块说明：mcp_smoke_test.py — CashflowRiskWorkbench MCP Server 独立验收测试客户端（外包任务 02）。

用途
    对指定的 MCP Server（Streamable HTTP 传输，JSON-RPC 2.0 over HTTP POST）执行 15 项
    验收用例（A01–A12 自动判定 + M01–M04 人工核对清单），输出 Markdown 结构化报告。
    本脚本只做「打协议、验行为、出报告」：不实现服务端逻辑、不连数据库、不 mock 服务器。

用法
    python mcp_smoke_test.py --base-url &quot;$MCP_BASE_URL&quot; --run-tag demo-01
    MCP_BASE_URL=&lt;你的 MCP 入口&gt; MCP_TOKEN=&lt;你的令牌&gt; python mcp_smoke_test.py

    脚本内不含任何默认地址/令牌：地址与令牌只能来自命令行参数或环境变量。

主要函数：\`emit\`, \`now_cst\`, \`rfc3339\`, \`window\`, \`truncate\`, \`fingerprint\`, \`walk\`, \`collect_values\`, \`contains_token\`, \`keys_of\`, \`placeholder\`, \`fill_required\`, \`pick_key\`, \`safe_headers\`, \`parse_payload\`

主要类：\`Unreachable\`, \`NetworkExhausted\`, \`McpClient\`, \`Runner\`

命令行选项：--base-url, --token, --run-tag, --timeout；运行前先读所属README。

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
