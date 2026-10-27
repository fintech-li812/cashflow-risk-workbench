# 文件说明：evidence_store.py

- 仓库路径：AI_Command_Workspace/交付/MEM-EVIDENCE-001/WorkBuddy/v1/src/evidence_store.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E4%BA%A4%E4%BB%98/MEM-EVIDENCE-001/WorkBuddy/v1/src/evidence_store.py)
- 归属：程序实现/启动或接口支持
- 大小：26683字节
- 导出SHA256：123fd3446505a1dec15923c3ec97be6796d858d401772bbbfbd56dbea1414768

## 内容与作用

模块说明：MEM-EVIDENCE-001 本地证据存储核心库（SQLite 事务版）。

任务来源：发包/进阶两个任务_20261023/MEM-EVIDENCE-001/v1/任务书_要求与验收.md
接口依据：规则/制造业Agent周边工程统一接口_v1.md（五字段、request_id、规范JSON、
金额元十进制字符串、mfg-evidence.v1 回执）与 规则/结果边界接口.md（status 闭集、
金额勾稽、origin/fixture 约束）。

性质声明：
- 本模块是本地 SQLite 事务存储，不是 MySQL、不是生产服务、不联网。
- record_id 是本地存储 ID（确定性派生），不是任何数据库主键，不声称已入生产库。
- 校验逻辑继承 WB-AGENT-003 参考候选 agent_guard.py 的口径（金额格式/勾稽/状态闭集），
  本包按 MEM-EVIDENCE-001 任务书补齐持久化、幂等、事务、故障恢复与防混查。
- 所有错误消息脱敏：不

主要函数：\`canonical_bytes\`, \`canonical_sha256\`, \`utc_now\`, \`_new_id\`, \`make_record_id\`, \`_require\`, \`_money\`, \`validate_result\`

主要类：\`ValidationError\`, \`FaultInjected\`, \`EvidenceStore\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
