# 分账户余额与合并口径核对

CX-ACCOUNT-RECON-001，Codex v1，2026-10-25。首次实现分账户核对，串接本轮新的账户证据绑定与跨源选择计划。旧基础算术仅复用，未重写滚动或三态算法。

关键区别：内部转账在公司合并口径抵销，但两端仍计入各自银行账户的流入/流出。用合并选择后的流水去对单账户会对错，本模块显式保留两套口径。
每账户计算期初、实际收付、净额、计算期末、登记独立期末及差异；各账户净额与差异之和必须分别等于合并结果。原始记录与审批关系保留，不能自动调平。

运行：
```text
python -B src/reconcile_cli.py --account-bundle fixtures/account_bundle --account-trust fixtures/account_trust.json --cash-bundle fixtures/cash_bundle --cash-trust fixtures/cash_trust.json --output-dir <全新目录> --allow-fixture
python -B selftest.py --output-dir <全新自测目录>
```
0=离线合成核对完成（差异非0仍会原样报告）；2=资料缺项/真实数据须原生公式等blocked；3=输入不符invalid或IO。看reconciliation_state判断matched或difference_pending_review，不以退出0当所有余额相等。

真实业务资料不会在本Python候选直接计算：operator_registered_evidence返回blocked，要求千问批准原生公式链。默认也拒绝fixture，只有显式允许才运行合成对照。
不保存数据库、不改7工具、不改源xlsx；输出始终can_save_source_result=false、native_sheet_verified=false。此包不替代四外包的原生适配或发布验收。
