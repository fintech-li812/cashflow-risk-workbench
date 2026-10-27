# 文件说明：05_cf-tunnel.service

- 仓库路径：AI_Command_Workspace/交付/WorkBuddy_历史归档/v1/05_cf-tunnel.service
- 查看文件：[打开原文件](../AI_Command_Workspace/%E4%BA%A4%E4%BB%98/WorkBuddy_%E5%8E%86%E5%8F%B2%E5%BD%92%E6%A1%A3/v1/05_cf-tunnel.service)
- 归属：交付或存档材料；包/文档不等于发布或验收通过
- 大小：1949字节
- 导出SHA256：5d4180c37a14bc86e71894e2385042602cd880ca8ba0060be96a41aa8b5698c8

## 内容与作用

标题/章节：CashflowRiskWorkbench 常驻 SSH 隧道（systemd user service）；作用：从“笔记本/应用机/备份机”发起，把本机端口转发到服务器 localhost 的服务；13306 -&gt; 服务器 127.0.0.1:3306 (MySQL)；18000 -&gt; 服务器 127.0.0.1:8000 (MCP Server，尚未部署也不影响建隧道)；设计：autossh 负责断线自愈；systemd --user 负责开机/登录自启。；部署步骤（在“隧道发起方机器”上，不是服务器上）：；mkdir -p ~/.config/systemd/user

启动/服务/运维相关内容；先核实本机路径、权限和目标，切勿直接批量执行。

## 打开与使用

文本/代码编辑器；HTML按所属说明预览。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
