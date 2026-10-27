# 文件说明：evidence_store.py

- 仓库路径：AI_Command_Workspace/发包/四个大型独立任务_20261025_v1/02_报告与证据导出工程/参考候选/本地证据修订v2_仅供边界参考/src/evidence_store.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E5%8F%91%E5%8C%85/%E5%9B%9B%E4%B8%AA%E5%A4%A7%E5%9E%8B%E7%8B%AC%E7%AB%8B%E4%BB%BB%E5%8A%A1_20261025_v1/02_%E6%8A%A5%E5%91%8A%E4%B8%8E%E8%AF%81%E6%8D%AE%E5%AF%BC%E5%87%BA%E5%B7%A5%E7%A8%8B/%E5%8F%82%E8%80%83%E5%80%99%E9%80%89/%E6%9C%AC%E5%9C%B0%E8%AF%81%E6%8D%AE%E4%BF%AE%E8%AE%A2v2_%E4%BB%85%E4%BE%9B%E8%BE%B9%E7%95%8C%E5%8F%82%E8%80%83/src/evidence_store.py)
- 归属：任务说明/接续指令；文件存在不代表已执行
- 大小：25103字节
- 导出SHA256：5b5e6ddea7a25692524cbd3ad92d3372e80c6b21f72d978b69d7d0a2b717686b

## 内容与作用

模块说明：MEM-EVIDENCE-001：本地 SQLite 事务化证据存储。

边界（与任务书一致）：
- 只做制造业现金流结果的**本地**可靠存储与回查；不连 MySQL、不连千问、不部署服务。
- 正式结果只在事务 COMMIT 成功之后生成 mfg-evidence.v1 回执；committed 仅表示本地库已落库，
  不表示服务端 MySQL 已入库。
- 幂等唯一键 = (tenant_id, company_id, operation, request_id)；同键同规范摘要回放原 record_id，
  同键异摘要冲突且不覆盖。
- 历史只追加（触发器禁止 UPDATE/DELETE）；当前有效记录的选择规则显式可解释，绝不跨企业取 MAX(id)。
- 所有 SQL 全部参数化；不接收任何外部 SQL；数据库文件路径必须由调用者限定在测试工作目录内。

本文件不实现任何金额计算，计算口径校验委托 src/result_guard.py。

主要函数：\`utc_now\`, \`make_record_id\`, \`load_json_file\`, \`resolve_store_path\`, \`hold_exclusive_lock\`

主要类：\`StoreError\`, \`Store\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
