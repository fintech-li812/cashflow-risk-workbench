# 文件说明：adapters.py

- 仓库路径：AI_Command_Workspace/验收/CX-AGENT-FIX-001/Codex/七反例同用例前后对照_v1/after/adapters.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/CX-AGENT-FIX-001/Codex/%E4%B8%83%E5%8F%8D%E4%BE%8B%E5%90%8C%E7%94%A8%E4%BE%8B%E5%89%8D%E5%90%8E%E5%AF%B9%E7%85%A7_v1/after/adapters.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：4182字节
- 导出SHA256：c7e1e4d52cdcd1f8f69ce31f5b3642e5c878ca13f62a52d5133f5f90dd29d9b5

## 内容与作用

模块说明：WB-AGENT-003 后端组合：把四类能力接到具体实现。

OfflineFixtureBackend 只服务于显式测试；allow_fixture 默认 False，
生产路径不会自动回退到合成夹具。合成标记在返回的 payload 中原样保留，不擦除。

主要函数：\`with_binding\`

主要类：\`OfflineFixtureBackend\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
