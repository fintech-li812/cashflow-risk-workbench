# 文件说明：evidence_cli.py

- 仓库路径：AI_Command_Workspace/交付/MEM-EVIDENCE-001/WorkBuddy/v1/src/evidence_cli.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E4%BA%A4%E4%BB%98/MEM-EVIDENCE-001/WorkBuddy/v1/src/evidence_cli.py)
- 归属：程序实现/启动或接口支持
- 大小：11451字节
- 导出SHA256：70af89c79306c8290d16724f7a4a7c6ae203eddb0ac100fe3476f5ecc8a79647

## 内容与作用

模块说明：MEM-EVIDENCE-001 CLI：save / get / history / verify-store / selftest。

用法（在交付根目录）：
  python src/evidence_cli.py save --input &lt;结果JSON&gt; --context &lt;可信上下文JSON&gt;       --request-id &lt;逻辑ID&gt; --store &lt;库路径&gt; [--workdir &lt;目录&gt;] [--allow-fixture]
  python src/evidence_cli.py get --tenant-id T --company-id C --record-id R       --store &lt;库路径&gt; [--workdir &lt;目录&gt;]
  python src/evidence_cli.py history --tenant-id T --company-id C --period YYYY-MM       --store &lt;库路径&gt; [--w

主要函数：\`_emit\`, \`_load_json\`, \`_resolve_store\`, \`cmd_save\`, \`cmd_get\`, \`cmd_history\`, \`cmd_verify\`, \`_selftest\`, \`cmd_selftest\`, \`build_parser\`, \`main\`

命令行选项：--input, --context, --request-id, --store, --workdir, --allow-fixture, --fault-inject, --tenant-id, --company-id, --record-id, --store, --workdir；运行前先读所属README。

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
