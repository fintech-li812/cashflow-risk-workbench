# 文件说明：tamper_db.py

- 仓库路径：AI_Command_Workspace/发包/四个大型独立任务_20261025_v1/02_报告与证据导出工程/参考候选/本地证据修订v2_仅供边界参考/tests/tamper_db.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E5%8F%91%E5%8C%85/%E5%9B%9B%E4%B8%AA%E5%A4%A7%E5%9E%8B%E7%8B%AC%E7%AB%8B%E4%BB%BB%E5%8A%A1_20261025_v1/02_%E6%8A%A5%E5%91%8A%E4%B8%8E%E8%AF%81%E6%8D%AE%E5%AF%BC%E5%87%BA%E5%B7%A5%E7%A8%8B/%E5%8F%82%E8%80%83%E5%80%99%E9%80%89/%E6%9C%AC%E5%9C%B0%E8%AF%81%E6%8D%AE%E4%BF%AE%E8%AE%A2v2_%E4%BB%85%E4%BE%9B%E8%BE%B9%E7%95%8C%E5%8F%82%E8%80%83/tests/tamper_db.py)
- 归属：任务说明/接续指令；文件存在不代表已执行
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
