# 文件说明：cli.py

- 仓库路径：AI_Command_Workspace/验收/20261025_用户归档交付复审/Codex/v1/解包待审/MEM-EVIDENCE-001_WorkBuddy_v1/src/cli.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/20261025_%E7%94%A8%E6%88%B7%E5%BD%92%E6%A1%A3%E4%BA%A4%E4%BB%98%E5%A4%8D%E5%AE%A1/Codex/v1/%E8%A7%A3%E5%8C%85%E5%BE%85%E5%AE%A1/MEM-EVIDENCE-001_WorkBuddy_v1/src/cli.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：12801字节
- 导出SHA256：f05ac13b97d7fd7737f8a0b35b67cb0d326b777b4a80643aa7f6369606d500d0

## 内容与作用

模块说明：MEM-EVIDENCE-001 CLI：save / get / history / verify-store / selftest（含故障注入入口）。

返回格式统一为单行 JSON（--pretty 可缩进），退出码见 错误码说明.md：
0 OK | 1 未预期内部异常 | 2 用法/路径越界 | 3 校验拒绝 | 4 幂等冲突
5 范围内不存在 | 6 越权/身份范围不符 | 7 存储锁等待超时 | 8 一致性校验失败
9 故障注入子进程终止 | 10 自测断言失败 | 11 保存状态未确定

信任边界：--context 是**被调用者信任的本地测试上下文**（见 trust_boundary.md），
CLI 上自填的 tenant/company 不是认证，必须与可信上下文一致，否则按越权拒绝。

主要函数：\`_emit\`, \`_fail\`, \`_require_workdir\`, \`_open\`, \`_identity_guard\`, \`_load_json_safe\`, \`cmd_save\`, \`cmd_get\`, \`cmd_history\`, \`cmd_verify\`, \`cmd_lock_hold\`, \`cmd_selftest\`, \`build_parser\`, \`main\`

命令行选项：--pretty, --workdir, --input, --context, --request-id, --store, --operation, --allow-fixture, --save-diagnostic, --fault-before-commit, --fault-after-commit, --simulate-unknown；运行前先读所属README。

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
