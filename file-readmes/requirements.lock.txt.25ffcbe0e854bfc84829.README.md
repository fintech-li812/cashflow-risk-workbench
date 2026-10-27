# 文件说明：requirements.lock.txt

- 仓库路径：AI_Command_Workspace/验收/夜间集中交付_20261023/Codex/ZIP解压复现_v1/agent/requirements.lock.txt
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/%E5%A4%9C%E9%97%B4%E9%9B%86%E4%B8%AD%E4%BA%A4%E4%BB%98_20261023/Codex/ZIP%E8%A7%A3%E5%8E%8B%E5%A4%8D%E7%8E%B0_v1/agent/requirements.lock.txt)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：541字节
- 导出SHA256：a471097ecfe6a9c6dcc511917dcf7a894120bed3ed1fb86c2ad8595129935327

## 内容与作用

标题/章节：WB-AGENT-003 锁定依赖（离线自测环境）；实测环境：CPython 3.13.12（Windows），仅使用标准库，无第三方依赖。；最低适用：Python 3.10+（仅用 dataclasses / typing / json / hashlib / re / unittest）；第三方依赖：无。本包刻意不引入 PyMySQL / requests / pandas 等，；以保证“不连服务器、不读写生产库、不部署”的边界可被静态检查。；复现命令（在包根目录）：；python run_tests.py

内容开头：python&gt;=3.10

## 打开与使用

文本/代码编辑器；HTML按所属说明预览。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
