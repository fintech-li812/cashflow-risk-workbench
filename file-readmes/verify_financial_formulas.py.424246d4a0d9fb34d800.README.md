# 文件说明：verify_financial_formulas.py

- 仓库路径：AI_Command_Workspace/交付/WB-FIN-001/WorkBuddy/v2/verify_financial_formulas.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E4%BA%A4%E4%BB%98/WB-FIN-001/WorkBuddy/v2/verify_financial_formulas.py)
- 归属：交付或存档材料；包/文档不等于发布或验收通过
- 大小：57846字节
- 导出SHA256：4db30e582cbdf4e38df451dd0781f0f25e22dde5e30effdf1a2648026d9afb30

## 内容与作用

模块说明：WB-FIN-001 · 财务公式离线校验脚本（WorkBuddy v1）

用途
   用 Python 标准库 decimal 复算《财务公式与口径总表.md》中&quot;已批准/已定稿&quot;的公式，
   对手算用例做本地离线核对。

严格边界（请勿越界使用本脚本的输出）
   1. 本脚本只做**离线算术复核**，不连接服务器、不读写任何生产凭据、不打开或修改
      D:\CashflowRiskWorkbench 下的 xlsx / HTML / SQL / 源文档。
   2. 本脚本通过 ≠ 千问办公表格已能运行。所有&quot;千问表格公式&quot;在总表中一律标注
      &quot;待平台验证&quot;，平台函数（AVERAGE / SUMIF / PERCENTILE / INDEX-MATCH 等）
      可用性由平台侧实测确认，本脚本不证明。
   3. 未批准的参数（1.45、K 来源、刚性支出定义、Myer 是否停用、13 周分配口径等）
      在本脚本中只做&quot;差异展示&quot;或标记 BL

主要函数：\`d\`, \`r2\`, \`r4\`, \`f01_monthly_outflow\`, \`f02_business_scale\`, \`f08_ratio\`, \`f09_static_lamp\`, \`f05_time_buffer\`, \`f05b_time_lamp\`, \`f06_financing_buffer\`, \`f07_operating_buffer\`, \`f13_quality_score\`, \`f16_deada_score\`, \`f18_fuse\`, \`f19_merge\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
