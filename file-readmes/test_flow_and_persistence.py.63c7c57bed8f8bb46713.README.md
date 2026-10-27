# 文件说明：test_flow_and_persistence.py

- 仓库路径：AI_Command_Workspace/验收/夜间集中交付_20261023/Codex/ZIP解压复现_v1/agent/tests/test_flow_and_persistence.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/%E5%A4%9C%E9%97%B4%E9%9B%86%E4%B8%AD%E4%BA%A4%E4%BB%98_20261023/Codex/ZIP%E8%A7%A3%E5%8E%8B%E5%A4%8D%E7%8E%B0_v1/agent/tests/test_flow_and_persistence.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：14234字节
- 导出SHA256：cafad10b18f5d357f915353713e8683f09ffc331877cfa8b5b6026cda585a248

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
