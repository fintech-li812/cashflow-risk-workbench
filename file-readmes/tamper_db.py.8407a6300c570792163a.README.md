# 文件说明：tamper_db.py

- 仓库路径：AI_Command_Workspace/验收/20261025_用户归档交付复审/Codex/v1/解包待审/MEM-EVIDENCE-001_WorkBuddy_v1/tests/tamper_db.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/20261025_%E7%94%A8%E6%88%B7%E5%BD%92%E6%A1%A3%E4%BA%A4%E4%BB%98%E5%A4%8D%E5%AE%A1/Codex/v1/%E8%A7%A3%E5%8C%85%E5%BE%85%E5%AE%A1/MEM-EVIDENCE-001_WorkBuddy_v1/tests/tamper_db.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：2426字节
- 导出SHA256：451896cd1bc26d596ec6ae819cfcace3dc189c3f08ed9895082d18fef7139784

## 内容与作用

模块说明：故障注入子进程：直接改写本地测试库，用于验证 verify-store 的检测边界。

用法：python tests/tamper_db.py --store &lt;库路径&gt; --mode payload|digest|identity

说明（重要）：evidence_record 带 BEFORE UPDATE 触发器禁止改写（append-only）。
本脚本先 DROP 该触发器，模拟&quot;已具备库文件写权限的攻击者&quot;；这是检测边界演示，
不代表正常调用路径可以改写历史。普通哈希也无法抵御能重写整个库及全部可信摘要的攻击者。

主要函数：\`main\`

命令行选项：--store, --mode, --record-id；运行前先读所属README。

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
