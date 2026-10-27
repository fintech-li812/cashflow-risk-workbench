---
name: mfg-program-workbench
description: 使用已绑定的制造业现金流MCP工具完成来源检查、程序现场计算、解释与经用户指示的隔离留档回查。适用于本工作台第一版，不把原生表格、附件解析或固定快照当作本次计算。
---

# 制造业现金流工作台：程序计算版

用户已于2026-10-26确定：千问是操作入口，程序负责计算，MySQL留痕。无需寻找千问原生表格功能。先使用本会话真实存在的MCP工具；技能不能添加工具或改变连接器。

## 先确认连接版本

调用 `get_workbench_status`。要求 `architecture=qwen_entry_program_calculation`，并且工具清单有 `calculate_manufacturing_cashflow`。否则说明仍连接旧版本，停止现场计算；不要把 `read_cashflow_result` 旧快照当作计算成功，不用Bash/Python代替已绑定计算工具。

数据库不可用时，程序计算仍可执行，但明确禁止宣称保存成功。报告实际错误，同一问题每次重试至少30秒，最多3次；保存结果不确定时使用原请求编号回查。

## 选择来源并计算

调用 `list_manufacturing_sources`，采用清单实际返回的source_id。

- `program_demo_v1`：新的合成固定模板，程序现场计算，适合首版联调。
- `program_difference_v1`：合成余额差异测试，必须展示差异并阻止保存。
- `manufacturing_sample_v1`：原八表埋错样例，只读保留，当前完整计算映射仍阻塞。禁止自行缩放D8、删除重复行、补零或用另一个来源的结果代替。

调用 `calculate_manufacturing_cashflow(source_id=实际来源)`。需要查看原始样例时使用 `inspect_manufacturing_source` 和 `get_manufacturing_readiness`。结果为blocked或工具错误时展示原因并停止，不报成功。

解释从工具实际结果取得：期间、期初、三类流入/流出合计、净额、计算期末、独立实际期末、差异、风险标志。使用元。所有当前程序模板都是SYNTHETIC，显著标记“合成数据；程序计算；未通过真实企业验证”。来源哈希和计算版本按返回原值保留，不编造。

## 用户要求保存时

仅在用户明确要求保存且工具返回 `can_save_source_result=true` 时，调用 `save_cashflow_result(result=实际返回的完整result, request_id=本次稳定唯一编号)`。当前仅 `program_demo_v1` 是默认可保存来源；不可修改返回对象，不允许Agent自算或增删金额。余额差异测试不得保存。

`committed` 回执才表示提交；`pending`不是失败或成功，需要原编号回查；`conflict`不要更换编号掩盖冲突。

随后使用该result的period、source_revision、run_id以及同一request_id调用 `query_cashflow_result`。核对记录编号、payload_sha256、全部金额、来源快照及算法哈希。历史回查成功不代表本次新保存，缺少回执不能说已留档。

## 边界

不修改原始文件、不执行付款/授信/通知、不改数据库结构或权限。技能不包含密钥。当前是隔离工程联调，不是真实企业风险预测。高级滚动算法和复杂模型不属于此技能。

向用户逐个提供文件时，每个文件下紧跟简介，说明内容、打开方法、数据类型和限制。
