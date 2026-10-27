# 文件说明：dump_golden.py

- 仓库路径：CashflowRiskWorkbench/migration/dump_golden.py
- 查看文件：[打开原文件](../CashflowRiskWorkbench/migration/dump_golden.py)
- 归属：测试预期/基准；不是本次执行结果
- 大小：3587字节
- 导出SHA256：f6c04a999f774a00ef209490ea45e64603310910d8aa5beac17f7cc7389f4d5c

## 内容与作用

模块说明：Stage 1 - freeze the golden answers.

Reads every registered source through the untouched Python engine and writes one
language-neutral JSON file. That file becomes the judge for the Node port: every
transplanted module is compared against it, field by field.

Read-only against existing code. Nothing here writes into program_v1.

主要函数：\`one\`, \`algorithm_digest\`, \`main\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
