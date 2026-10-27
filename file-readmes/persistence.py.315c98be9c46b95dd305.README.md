# 文件说明：persistence.py

- 仓库路径：AI_Command_Workspace/交付/CX-SMOKE-001/Codex/v1/验证_正常包/candidate-copy/reference-agent/persistence.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E4%BA%A4%E4%BB%98/CX-SMOKE-001/Codex/v1/%E9%AA%8C%E8%AF%81_%E6%AD%A3%E5%B8%B8%E5%8C%85/candidate-copy/reference-agent/persistence.py)
- 归属：交付或存档材料；包/文档不等于发布或验收通过
- 大小：15467字节
- 导出SHA256：4bf6f0436d88fd42ebb27556925b63d961f17ad0846f43b85620277068bdc875

## 内容与作用

模块说明：WB-AGENT-003 保存与回查：逐字段映射、幂等键、回执、精确回查、超时不确定态。

范围依据：333.md C 项；工件格式依据：规则/制造业Agent周边工程统一接口_v1.md 第 3 节
（mfg-evidence.v1：schema_version / kind=receipt / operation / 五字段 / request_id /
 record_id / payload_sha256 / stored_at / status=committed）。

本模块的 MemoryEvidenceStore 是**本地进程内参考实现，仅用于离线自测**，
不是 MySQL、不是生产存储、不产生任何数据库主键；record_id 明确标注为本地存储 ID。

主要函数：\`build_save_payload\`, \`retry_after_timeout\`, \`validate_store_input\`

主要类：\`Receipt\`, \`MemoryEvidenceStore\`, \`NoQueryCapabilityStore\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
