# 文件说明：verifier.py

- 仓库路径：AI_Command_Workspace/验收/20261025_用户归档交付复审/Codex/v1/修订交付/MEM-IMPORT-002/Codex/v2/src/mfg_import/verifier.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/20261025_%E7%94%A8%E6%88%B7%E5%BD%92%E6%A1%A3%E4%BA%A4%E4%BB%98%E5%A4%8D%E5%AE%A1/Codex/v1/%E4%BF%AE%E8%AE%A2%E4%BA%A4%E4%BB%98/MEM-IMPORT-002/Codex/v2/src/mfg_import/verifier.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：7533字节
- 导出SHA256：58c5e7984d69c301e593bc61bc2fecc9969bbb3727c76409913af654237ce0bb

## 内容与作用

模块说明：verify：独立核对导入包与真实源。

不止比哈希：用包内 mapping/例外快照从真实源重新推导 records/issues，
与包内文件逐字节比对。即便攻击者改了字段并重算 manifest 哈希，
也会因与真实源推导结果不符而失败，并指出源地址。

主要函数：\`_retained_verification_dir\`, \`_load_json\`, \`verify\`, \`_locate_diff\`

主要类：\`VerifyFailure\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
