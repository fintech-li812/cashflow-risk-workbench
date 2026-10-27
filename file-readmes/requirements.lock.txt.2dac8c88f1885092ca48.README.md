# 文件说明：requirements.lock.txt

- 仓库路径：AI_Command_Workspace/发包/四个大型独立任务_20261025_v1/02_报告与证据导出工程/参考候选/本地证据修订v2_仅供边界参考/requirements.lock.txt
- 查看文件：[打开原文件](../AI_Command_Workspace/%E5%8F%91%E5%8C%85/%E5%9B%9B%E4%B8%AA%E5%A4%A7%E5%9E%8B%E7%8B%AC%E7%AB%8B%E4%BB%BB%E5%8A%A1_20261025_v1/02_%E6%8A%A5%E5%91%8A%E4%B8%8E%E8%AF%81%E6%8D%AE%E5%AF%BC%E5%87%BA%E5%B7%A5%E7%A8%8B/%E5%8F%82%E8%80%83%E5%80%99%E9%80%89/%E6%9C%AC%E5%9C%B0%E8%AF%81%E6%8D%AE%E4%BF%AE%E8%AE%A2v2_%E4%BB%85%E4%BE%9B%E8%BE%B9%E7%95%8C%E5%8F%82%E8%80%83/requirements.lock.txt)
- 归属：任务说明/接续指令；文件存在不代表已执行
- 大小：713字节
- 导出SHA256：ad0386dce992407da30ca58eb561374d923765a25ea1948ba38a4799940a763f

## 内容与作用

标题/章节：MEM-EVIDENCE-001 v1 锁定依赖；第三方依赖：无。刻意不引入 PyMySQL / requests / pandas，；以保证&quot;不连服务器、不读写生产库、不部署&quot;的边界可被静态检查（见 tests/static_boundary_check.py）。；复现命令（在包根目录）：；python -m src.cli selftest --workdir &lt;全新目录&gt;；或：；python tests/run_tests.py --workdir &lt;全新目录&gt;

内容开头：实测环境：CPython 3.13.14（Windows，MSC v.1944 64 bit AMD64），仅使用标准库。 最低适用：Python 3.10+（用到 sqlite3 / json / hashlib / decimal / argparse / dataclasses-free 实现） python==3.13.14（实测）

## 打开与使用

文本/代码编辑器；HTML按所属说明预览。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
