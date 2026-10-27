# 文件说明：selftest.py

- 仓库路径：AI_Command_Workspace/验收/20261025_用户归档交付复审/Codex/v1/解包待审/MEM-EVIDENCE-001_WorkBuddy_v1/src/selftest.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/20261025_%E7%94%A8%E6%88%B7%E5%BD%92%E6%A1%A3%E4%BA%A4%E4%BB%98%E5%A4%8D%E5%AE%A1/Codex/v1/%E8%A7%A3%E5%8C%85%E5%BE%85%E5%AE%A1/MEM-EVIDENCE-001_WorkBuddy_v1/src/selftest.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：47300字节
- 导出SHA256：69af3300c9d8c9a1a462b78351af4149df23eb102a3da1c82e6a54027152e11a

## 内容与作用

模块说明：MEM-EVIDENCE-001 自测编排：在全新工作目录跑完整测试矩阵。

用法：python -m src.cli selftest --workdir &lt;全新目录&gt;
      python tests/run_tests.py --workdir &lt;全新目录&gt;

约束：
- 工作目录必须全新（不存在或为空目录），已存在且非空直接拒绝（退出码 2）。
- 独立预期来自 expected/ 冻结文件，运行只读不写；运行前后核验 expected/ 与 fixtures/ 的哈希。
- 故障注入只终止本包自己启动的子进程，不碰任何外部进程/服务器。
- 自测结论只针对本地 SQLite 测试库，不代表千问/生产 MySQL 行为。

主要函数：\`_cli\`, \`_script\`, \`_json\`, \`sha256_file\`, \`snapshot_tree\`, \`count_rows\`, \`first_record_id\`, \`stored_digest\`, \`run_selftest\`

主要类：\`Runner\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
