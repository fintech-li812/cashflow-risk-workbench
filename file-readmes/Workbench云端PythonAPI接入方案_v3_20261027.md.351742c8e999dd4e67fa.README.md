# 文件说明：Workbench云端PythonAPI接入方案_v3_20261027.md

- 仓库路径：CashflowRiskWorkbench/docs/Workbench云端PythonAPI接入方案_v3_20261027.md
- 查看文件：[打开原文件](../CashflowRiskWorkbench/docs/Workbench%E4%BA%91%E7%AB%AFPythonAPI%E6%8E%A5%E5%85%A5%E6%96%B9%E6%A1%88_v3_20261027.md)
- 归属：设计、规则或计划文档；注意历史口径与最新用户决定
- 大小：6311字节
- 导出SHA256：16a13c636f3d15d080880259573d2e344bfa0bab9961e9d76db54e08a8510f2c

## 内容与作用

标题/章节：Workbench 云端接入推荐方案 v3；推荐架构：千问动态前端 + Node接口层 + 阿里云Python API + MySQL；部署位置；用户工作流；Python API契约草案；身份、存储与幂等；AI工作流

内容开头：日期：2026-10-27。用户要求设计：千问云端网页不能直接运行现有Python引擎，如何交付一个可公开访问的整体Workbench。 本轮为方案，不代表云端接口已部署、端口已开放或生产已发布。 浏览器只访问一个*.qwenwork.host网址。千问Pages动态网站的Node服务端接同源/api请求，再通过HTTPS调用阿里云上的Python API。Python API调用现有计算与证据模块、生成结果和报告，MySQL仅由云端应用访问。

## 打开与使用

文本/代码编辑器；HTML按所属说明预览。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
