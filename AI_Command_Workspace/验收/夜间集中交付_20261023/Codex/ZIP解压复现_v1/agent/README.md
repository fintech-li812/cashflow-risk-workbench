# CX-AGENT-FIX-001｜Agent边界修复候选

作者Codex，2026-10-23。继承WorkBuddy WB-AGENT-003 v1，另目录修复，不改原交付。状态：离线自测完成，待DeepSeek独立审核、X统一检查；不批准部署。

从本目录运行：
```powershell
python run_tests.py
```
Python3.10+、标准库，无需外部依赖。71项方法通过（继承44、新增27），0失败/错误/跳过；其中1项继承测试把“参数准备=committed”的错误断言改为内部ok，原因见docs/修复逐条说明.md，不改金额或独立预期迎合程序。
七个原反例使用同一份测试源码前后对照：原版七项均暴露问题，修复版七项通过。9项与独立MEM-QA-001接口联测符合预期，包含2次同源不同run、伪回执/换企业拦截、提交后丢回执恢复、同请求异内容冲突、真实制造样例D8一格的原值/篡改/错误换算核对。真实样例一格通过不代表导入工具/全口径业务验收通过。

核心变化：缓存/来源与run绑定、先校验后缓存、保存前核身份/金额、回执精确匹配、pending读取阻断、参数准备不报提交成功、嵌套可变别名隔离。内部状态和适配说明见docs。

公开save_result增加可选allow_fixture关键字；未提供时只继承明确开启测试的Backend.allow_fixture is True，不让生产Backend自动回退。真实Backend应保持False并接可信认证/平台证据。production=qwen_sheet标签不证明来源，需真实平台适配证据。
build_save_payload原先成功返回committed，现仅ok，属于候选内部接口语义修正；消费者必须等待真正save_result提交并核回执，不能再拿准备结果显示已保存。共同业务结果和mfg-evidence.v1枚举未改。

历史失败轮round1/round2和最终round3均保存在验收/CX-AGENT-FIX-001/Codex，原七反例在验收/WB-AGENT-003/Codex/边界反例_20261023_v1。原码SHA和diff在docs。源码及测试不写库、不发通知、不联网。

未完成：真实千问读表/重算、实际MCP inputSchema绑定/调用、生产身份认证、持久化证据存储、MySQL回查、外包导入/存储两包集成、独立审核。平台和真实MySQL实测均0项；原44离线通过不再用作原候选可部署依据。
docs/继承README_原文及其他继承平台操作单均为历史候选，菜单/认证字段/黄灯话术未实测，不能照旧宣称平台能力；当前规则/制造业现金流一期范围优先。请先按本README与修复说明操作。
