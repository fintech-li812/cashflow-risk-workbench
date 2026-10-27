# 文件说明：test_flow_and_persistence.py

- 仓库路径：AI_Command_Workspace/验收/20261023_最新交付审批/Codex/v1/冻结候选/WB-AGENT-003/tests/test_flow_and_persistence.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/20261023_%E6%9C%80%E6%96%B0%E4%BA%A4%E4%BB%98%E5%AE%A1%E6%89%B9/Codex/v1/%E5%86%BB%E7%BB%93%E5%80%99%E9%80%89/WB-AGENT-003/tests/test_flow_and_persistence.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：14188字节
- 导出SHA256：f8934c77ed77ddd32cb23e521f135ed6c79d32f25e559c016015299e3a9ee8ee

## 内容与作用

模块说明：WB-AGENT-003 独立测试：流程 + 保存回执 + 六项打回红线。

覆盖 333.md E 项列出的 11 类场景。所有用例使用明确标识的合成夹具；
生产路径不允许夹具泄漏（由 test_fixture_never_leaks_to_production 等用例断言）。
失败即以非 0 退出，不重写独立预期。

主要函数：\`binding\`

主要类：\`CountingBackend\`, \`SnapshotOnlyBackend\`, \`FixedResultBackend\`, \`FlowTests\`, \`RedLineTests\`, \`MappingTests\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
