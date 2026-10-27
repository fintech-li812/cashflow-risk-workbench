# 文件说明：verifier.py

- 仓库路径：AI_Command_Workspace/发包/四个大型独立任务_20261025_v1/01_导入与追溯工程升级/参考候选/导入修订v2/src/mfg_import/verifier.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E5%8F%91%E5%8C%85/%E5%9B%9B%E4%B8%AA%E5%A4%A7%E5%9E%8B%E7%8B%AC%E7%AB%8B%E4%BB%BB%E5%8A%A1_20261025_v1/01_%E5%AF%BC%E5%85%A5%E4%B8%8E%E8%BF%BD%E6%BA%AF%E5%B7%A5%E7%A8%8B%E5%8D%87%E7%BA%A7/%E5%8F%82%E8%80%83%E5%80%99%E9%80%89/%E5%AF%BC%E5%85%A5%E4%BF%AE%E8%AE%A2v2/src/mfg_import/verifier.py)
- 归属：任务说明/接续指令；文件存在不代表已执行
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
