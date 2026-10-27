# 文件说明：README_先读我.md

- 仓库路径：AI_Command_Workspace/发包/四个大型独立任务_20261025_v1/02_报告与证据导出工程/冻结基线验收/README_先读我.md
- 查看文件：[打开原文件](../AI_Command_Workspace/%E5%8F%91%E5%8C%85/%E5%9B%9B%E4%B8%AA%E5%A4%A7%E5%9E%8B%E7%8B%AC%E7%AB%8B%E4%BB%BB%E5%8A%A1_20261025_v1/02_%E6%8A%A5%E5%91%8A%E4%B8%8E%E8%AF%81%E6%8D%AE%E5%AF%BC%E5%87%BA%E5%B7%A5%E7%A8%8B/%E5%86%BB%E7%BB%93%E5%9F%BA%E7%BA%BF%E9%AA%8C%E6%94%B6/README_%E5%85%88%E8%AF%BB%E6%88%91.md)
- 归属：任务说明/接续指令；文件存在不代表已执行
- 大小：3854字节
- 导出SHA256：b59fbd48c98ea85fd05a8f09023fffcf4c1f252e4f6993e73ec94b29bae9bb14

## 内容与作用

标题/章节：包1：制造业报告与证据导出器；固定命令与产物；必须自测（R01—R20，与task.json对应）；源文件

内容开头：任务号MEM-REPORT-002。难度中等，交给能写Python/HTML的队友。当前工作台已有合法结果与MySQL回执，缺可携带、可复核的正式导出组件。此包补这个空白，不改算法和存储，也不重复开发浏览器工作台。 实现`src/report_cli.py export --result &lt;JSON&gt; --context &lt;五字段JSON&gt; --output-dir &lt;新目录&gt; [--receipt &lt;JSON&gt;] [--allow-fixture]`。 输出report.html（单文件离线HTML，内联CSS）、report.csv（UTF-8/可带BOM，表头固定key,value）、result.json（与输入语义完全一致）、manifest.json；只有确实给了有效receip

## 打开与使用

文本/代码编辑器；HTML按所属说明预览。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
