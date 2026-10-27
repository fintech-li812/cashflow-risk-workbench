# 文件说明：dump_inputs.py

- 仓库路径：CashflowRiskWorkbench/migration/dump_inputs.py
- 查看文件：[打开原文件](../CashflowRiskWorkbench/migration/dump_inputs.py)
- 归属：迁移候选工程；以该目录合同与最新接手记录确认阶段
- 大小：1956字节
- 导出SHA256：145ccc05d0b64117f1bb4ef3b39d91593bf4a6ccaebeb9d9479d14448ad431af

## 内容与作用

模块说明：Read-only dump: 把固化的 xlsx 模板输入解析成语言无关的 JSON fixture。

设计动机：云端（千问 Pages / Node）不应该、也不需要解析 xlsx。
固定模板不是通用导入器——输入在生产侧固化，绑定工作簿 SHA256。
本脚本只在本地开发机跑一次，产物供 Node 侧作为对拍输入。

只读：不修改 program_v1 任何源文件。

主要函数：\`main\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
