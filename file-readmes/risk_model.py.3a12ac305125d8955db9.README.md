# 文件说明：risk_model.py

- 仓库路径：CashflowRiskWorkbench/model/现金流风控_v2/risk_model.py
- 查看文件：[打开原文件](../CashflowRiskWorkbench/model/%E7%8E%B0%E9%87%91%E6%B5%81%E9%A3%8E%E6%8E%A7_v2/risk_model.py)
- 归属：项目源文件或配套资料
- 大小：15273字节
- 导出SHA256：e22172c57cc2de81524c97ffc3f786e13c69822c0717ceeb0ca4529513d65056

## 内容与作用

模块说明：Cash-flow risk reference implementation v2; probabilities are scenario estimates.

No network calls, no notifications, no financial transactions. Money uses one
explicit unit throughout. Historical errors must be actual minus as-of forecast.

主要函数：\`number\`, \`array\`, \`first_digit\`, \`last_digit\`, \`legacy_scores\`, \`legacy_fuse\`, \`benford_test\`, \`bh_adjust\`, \`fit_monotone_margin_lp\`, \`calibrated_path_lower_bound\`, \`_integer\`, \`cashflow_risk\`, \`main\`

命令行选项：--output；运行前先读所属README。

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
