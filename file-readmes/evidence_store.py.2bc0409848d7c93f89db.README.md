# 文件说明：evidence_store.py

- 仓库路径：AI_Command_Workspace/验收/20261025_用户归档交付复审/Codex/v1/修订交付/MEM-EVIDENCE-001/Codex/v2/src/evidence_store.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/20261025_%E7%94%A8%E6%88%B7%E5%BD%92%E6%A1%A3%E4%BA%A4%E4%BB%98%E5%A4%8D%E5%AE%A1/Codex/v1/%E4%BF%AE%E8%AE%A2%E4%BA%A4%E4%BB%98/MEM-EVIDENCE-001/Codex/v2/src/evidence_store.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
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
