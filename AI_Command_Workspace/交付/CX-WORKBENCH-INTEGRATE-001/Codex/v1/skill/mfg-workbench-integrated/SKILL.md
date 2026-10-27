---
name: mfg-workbench-integrated
description: 制造业现金流工作台统一入口，检查本机源文件、取证与缺项，使用已绑定MCP核对结果和保存回查。
---

# 制造业现金流工作台

适用于本项目制造业基础版。使用当前连接器真实暴露的七个工具，工具清单及返回才是能力证据。核心滚动算法、三态自动判定、评级、折扣和其他行业仍后置。

## 工作台与源文件

先用get_workbench_status查看实际组件状态和result_profile。list_manufacturing_sources只返回已登记源；用户说“工作目录里的制造业表”时，可用返回的source_id调用inspect_manufacturing_source，再用get_manufacturing_readiness检查缺项。只引用工具实际读到的Sheet/区域/原值和来源摘要，不运行终端命令或改原文件。

当前本地样例的读取是OOXML只读取证，不是千问原生表格API，不会重算公式。数据字典文字不能覆盖单元格证据；1631300的单位不猜、不自动缩放；重复行保留；正常分次/部分到账不当数据错误。

readiness阻断时，说明已读到什么和最关键1—3个缺项，不输出完整企业现金流结论，也不保存该源的财务结果。项目状态中awaiting_external_delivery/not_bound的模块直接报告未就绪，不编造已接通。

## 结果、演示与留档

read_cashflow_result读取的是当前批准快照。它的result_profile若为offline_fixture，只能用于用户明确要求的合成数据演示；不能拿这份快照冒充inspect_manufacturing_source读到的企业分析结果。两个来源必须分开说明。

结果五字段tenant_id/company_id/period/source_revision/run_id和所有金额原样传递。金额规范为元的2位小数字符串；actual_closing/difference为null时说明未完成独立余额核对，缺失不补0。

用户要求留档或明确授权该流程时，使用同一批准result调用save_cashflow_result，固定一个request_id贯穿重试；然后query_cashflow_result按原request_id及原period/source_revision/run_id精确回查。只有真实committed与一致回执才能说已提交。pending/unavailable保留原编号回查；conflict停下核对来源。不能取跨版本最新记录，不能让模型编金额、回执或来源。

原只读技能mfg-cashflow-assistant的禁写范围只适用于它原来的只读任务；本集成技能仅在用户已授权留档且真实工具可用时允许上述受保护保存，不扩大到改表、审批、通知、定时任务或其他连接器。

## 回答

用简明中文分别说：已读取来源与范围、可核对结果、实际余额核对状态、数据库回执状态、尚缺什么。合成演示醒目标注“合成数据”，本地读取与千问原生读取分清；未验证的环节不说完成。
