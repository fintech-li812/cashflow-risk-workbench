# 文件说明：persistence.py

- 仓库路径：AI_Command_Workspace/验收/CX-AGENT-FIX-001/Codex/七反例同用例前后对照_v1/before/persistence.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E9%AA%8C%E6%94%B6/CX-AGENT-FIX-001/Codex/%E4%B8%83%E5%8F%8D%E4%BE%8B%E5%90%8C%E7%94%A8%E4%BE%8B%E5%89%8D%E5%90%8E%E5%AF%B9%E7%85%A7_v1/before/persistence.py)
- 归属：历史验证证据或验收材料；须结合版本与实际日志阅读
- 大小：11971字节
- 导出SHA256：13f9a688efe3622965914f7d6ee8112e1eb0c54ef64ea4b90e1ce208fc217720

## 内容与作用

模块说明：WB-AGENT-003 保存与回查：逐字段映射、幂等键、回执、精确回查、超时不确定态。

范围依据：333.md C 项；工件格式依据：规则/制造业Agent周边工程统一接口_v1.md 第 3 节
（mfg-evidence.v1：schema_version / kind=receipt / operation / 五字段 / request_id /
 record_id / payload_sha256 / stored_at / status=committed）。

本模块的 MemoryEvidenceStore 是**本地进程内参考实现，仅用于离线自测**，
不是 MySQL、不是生产存储、不产生任何数据库主键；record_id 明确标注为本地存储 ID。

主要函数：\`build_save_payload\`, \`retry_after_timeout\`

主要类：\`Receipt\`, \`MemoryEvidenceStore\`, \`NoQueryCapabilityStore\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
