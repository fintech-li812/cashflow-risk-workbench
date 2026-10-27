# 文件说明：requirements.lock.txt

- 仓库路径：AI_Command_Workspace/验收/20261025_用户归档交付复审/Codex/v1/修订交付/MEM-EVIDENCE-001/Codex/v2/requirements.lock.txt
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/20261025_%E7%94%A8%E6%88%B7%E5%BD%92%E6%A1%A3%E4%BA%A4%E4%BB%98%E5%A4%8D%E5%AE%A1/Codex/v1/%E4%BF%AE%E8%AE%A2%E4%BA%A4%E4%BB%98/MEM-EVIDENCE-001/Codex/v2/requirements.lock.txt)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：713字节
- 导出SHA256：ad0386dce992407da30ca58eb561374d923765a25ea1948ba38a4799940a763f

## 内容与作用

标题/章节：MEM-EVIDENCE-001 v1 锁定依赖；第三方依赖：无。刻意不引入 PyMySQL / requests / pandas，；以保证&quot;不连服务器、不读写生产库、不部署&quot;的边界可被静态检查（见 tests/static_boundary_check.py）。；复现命令（在包根目录）：；python -m src.cli selftest --workdir &lt;全新目录&gt;；或：；python tests/run_tests.py --workdir &lt;全新目录&gt;

内容开头：实测环境：CPython 3.13.14（Windows，MSC v.1944 64 bit AMD64），仅使用标准库。 最低适用：Python 3.10+（用到 sqlite3 / json / hashlib / decimal / argparse / dataclasses-free 实现） python==3.13.14（实测）

## 打开与使用

文本/代码编辑器；HTML按所属说明预览。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
