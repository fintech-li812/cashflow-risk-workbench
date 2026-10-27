# 文件说明：run_tests.py

- 仓库路径：AI_Command_Workspace/验收/20261025_用户归档交付复审/Codex/v1/解包待审/MEM-EVIDENCE-001_WorkBuddy_v1/tests/run_tests.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/20261025_%E7%94%A8%E6%88%B7%E5%BD%92%E6%A1%A3%E4%BA%A4%E4%BB%98%E5%A4%8D%E5%AE%A1/Codex/v1/%E8%A7%A3%E5%8C%85%E5%BE%85%E5%AE%A1/MEM-EVIDENCE-001_WorkBuddy_v1/tests/run_tests.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：961字节
- 导出SHA256：9f75b90c2f8936fd75f3c33f9e16049e17e837dd5e436888ef928eef43cb9ad9

## 内容与作用

模块说明：自测入口（与 `python -m src.cli selftest` 等价）。

用法：python tests/run_tests.py --workdir &lt;全新目录&gt;
退出码：0 全部通过；10 存在失败/阻塞/未执行；2 工作目录已存在且非空。

主要函数：\`main\`

命令行选项：--workdir, --pretty, --inject-failure；运行前先读所属README。

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
