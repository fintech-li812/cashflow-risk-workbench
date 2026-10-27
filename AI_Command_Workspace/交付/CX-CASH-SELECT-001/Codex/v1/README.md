# 现金来源防重计与内部转账选择计划

CX-CASH-SELECT-001，Codex v1，2026-10-25。首次实现既有待办B08的可运行防重计与明确配对抵销，不重复Excel导入解析、报告导出、原生适配或发布检查。
输入是明确登记的规范现金事实，不读取原xlsx、不猜银行流水列。按外部操作者审批配置选择主证据；银行和业务同笔不叠加，应收开票/折旧/未用授信不计现金，正常部分回款不报金额错误。
内部转账只有明确审批、同范围不同账户、反向且同日同币同金额匹配才消除合并计入；缺配对或跨日不猜，列待核。单账户对账仍需这些原始流动，不可把本合并选择结果当单账户流水。

```text
python -B src/selection_cli.py plan --bundle fixtures/complete_bundle --trust fixtures/trusted_selection.json --output-dir <全新目录> --allow-fixture
python -B selftest.py --output-dir <全新自测目录>
```
0=选择计划ready，2=业务范围/映射待确认blocked，3=输入或证据不符invalid/IO。原始事件不改；每条均有record_decisions处理轨迹，计数闭合。
仅明确主来源的现金事件进入selected_records，合并内转及批准重复只变选择状态，不删除原始事件。相同金额但不同交易ID不能自动去重。
本模块不输出现金流金额合计、不保存结果，不认证来源真实性或权限，不自动证明完整现金流。所有真实缺项保留；默认拒绝fixture。
