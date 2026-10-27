# 文件说明：run_tests.py

- 仓库路径：AI_Command_Workspace/交付/MEM-EVIDENCE-001/WorkBuddy/v1/tests/run_tests.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E4%BA%A4%E4%BB%98/MEM-EVIDENCE-001/WorkBuddy/v1/tests/run_tests.py)
- 归属：测试用例/测试输入；不作为生产业务入口
- 大小：17785字节
- 导出SHA256：5f126351648b2c62eab372518b4356cca7a3b00d82b229a55f62d31d555ccd97

## 内容与作用

模块说明：MEM-EVIDENCE-001 独立测试矩阵 runner。

运行（在交付根目录 v1/ 下）：
    python tests/run_tests.py

约定：
- 每个用例通过 subprocess 真实调用 src/evidence_cli.py（独立进程），
  退出码/stdout/stderr 原样落盘 test-output/&lt;用例&gt;/。
- 独立预期只读 expected/cli_cases_expected.json（冻结），运行前后核其 SHA256，
  本程序永不改写 expected/ 与 fixtures/。
- 判定：实际退出码与预期一致且关键关系断言通过 → PASS，否则 FAIL；
  非预期异常如实 FAIL 并附类型名，不伪装 BLOCKED。
- 任一用例 FAIL → 汇总退出码 1；全部 PASS → 0。

主要函数：\`sha256_file\`, \`run_cli\`, \`db_count\`, \`db_all_count\`, \`db_diag_count\`, \`record\`, \`expect_exit\`, \`main\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
