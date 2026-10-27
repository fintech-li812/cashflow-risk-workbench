# 文件说明：adapters.py

- 仓库路径：AI_Command_Workspace/验收/WB-AGENT-003/Codex/接入前检查_v1/测试副本/candidate/adapters.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/WB-AGENT-003/Codex/%E6%8E%A5%E5%85%A5%E5%89%8D%E6%A3%80%E6%9F%A5_v1/%E6%B5%8B%E8%AF%95%E5%89%AF%E6%9C%AC/candidate/adapters.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：4069字节
- 导出SHA256：2d0231a4b5978e94b5c2952e9a556b53620daa173f05cdee855f9d4a12c15dcc

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
