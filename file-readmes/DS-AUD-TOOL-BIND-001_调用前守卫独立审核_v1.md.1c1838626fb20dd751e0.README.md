# 文件说明：DS-AUD-TOOL-BIND-001_调用前守卫独立审核_v1.md

- 仓库路径：AI_Command_Workspace/指令/DS-AUD-TOOL-BIND-001_调用前守卫独立审核_v1.md
- 查看文件：[打开原文件](../AI_Command_Workspace/%E6%8C%87%E4%BB%A4/DS-AUD-TOOL-BIND-001_%E8%B0%83%E7%94%A8%E5%89%8D%E5%AE%88%E5%8D%AB%E7%8B%AC%E7%AB%8B%E5%AE%A1%E6%A0%B8_v1.md)
- 归属：任务说明/接续指令；文件存在不代表已执行
- 大小：1820字节
- 导出SHA256：76d95efe1f0c4f386fdb037675c552ddfecd696a08aea5491b4782a5322b9675

## 内容与作用

标题/章节：DS-AUD-TOOL-BIND-001 独立审核任务（待X唤醒，串行）

内容开头：审核对象：交付/CX-TOOL-BIND-001/Codex/v1。开发者Codex；不得由其自签独审。此任务排在既有QA v2、Agent修复v1、发布检查v1独审之后；由Codex看板明确交接后执行，文件本身不会唤醒你。 1. 独立验证manifest、SHA、ZIP内容；在副本重跑61方法和6变异，不能只看开发日志。 2. 自造schema绕过反例：allOf/if/then、oneOf、additionalProperties、嵌套本地引用/失效引用、外部$ref及动态引用、混合方言、自定义vocabulary/format；确保未发生网络检索。

## 打开与使用

文本/代码编辑器；HTML按所属说明预览。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
