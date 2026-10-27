# CX-AGENT-002：制造业Agent接入准备包（候选）

本包不是已部署Agent/MCP，不包含算法、服务器或凭据。主工程app.py本次检查为0字节；旧提示词还依赖已暂停模型。本包供WorkBuddy接真实能力，DeepSeek独立审核。

内容：agent_guard.py的结果校验/说明、候选主提示词和八条追问、接口说明、合成fixture、23项unittest。
在本目录运行：python -m unittest discover -s tests -v。Python仅使用标准库，适用于Python3.10+，不需网络/数据库。生产默认拒绝offline_fixture；例子显式allow_fixture才允许。

本次实际自测：23个测试全部通过，退出码0，仅合成离线。第一次带-t参数的discovery因tests不是包产生ImportError；只读检查后等待至少30秒，改为从包根目录执行上述命令通过。未改任何生产数据。
覆盖身份/期间/run/版本不匹配、非法金额/非有限数、净额与余额不勾稽、差异、缺独立实际余额、算法未绑定、未就绪伪造金额、部分范围冒充全口径、fixture进入生产等。
限制：校验器不能证明调用者身份/平台来源/真实数据完整性；当前context在测试中由调用者提供，生产必须真实认证绑定。snapshot_ref和origin字符串不是安全证据。保存工具/回执/精确回查尚由WorkBuddy实现。
最终千问读表/Agent/工具调用/MySQL回查均未在本次执行，不能把23通过当平台已通过。
