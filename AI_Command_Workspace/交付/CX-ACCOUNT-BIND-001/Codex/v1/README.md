# 统计账户与独立余额证据绑定

CX-ACCOUNT-BIND-001，Codex v1，2026-10-25。此前只有“账户范围/期初/独立期末未绑定”的提示，本轮首次实现实际绑定核验，不重复四个外包模块。

输入为明确登记的JSON记录，不读取Excel、不开发主算法、不推理账户或单位；输出独立的范围/余额绑定诊断，不改变共同结果mfg-agent-result.v1或数据闸词表。

实现：账户与主体范围、纳入排除、月份截止、CNY单位、逐账户两阶段余额、外部审批文件固定摘要、来源记录逐字段核对、证据路径和摘要、读取中变化检测、金额精度与缺项阻断。
只有全部纳入账户的期初与独立期末均有匹配记录，才输出两项合计。无独立余额不填0；负余额和真实0保留；计算期末不当独立来源。

## 运行
```text
python -B src/binding_cli.py check --bundle fixtures/complete_bundle --trust fixtures/trusted_binding.json --output-dir <不存在的新目录> --allow-fixture
python -B selftest.py --output-dir <不存在的新自测目录>
```
退出0：绑定核验ready；2：资料缺项blocked；3：输入/审批/证据不符invalid或输出IO异常。失败也会给明确诊断，不生成可保存的业务结果。
默认拒绝fixture，命令行开关与外部trust.allow_fixture必须同时明确。trust必须在bundle外，由操作者提供；上传文件不能自带一个trust给自己授权。

## 限制
SHA匹配只证明与操作者登记内容一致，不认证银行文件真实性、批准人身份或平台权限。银行提取件/已核账提取件需业务方审批，不能靠source_class字段自证真实。
ready只表示本模块范围与余额登记匹配。始终can_save_source_result=false、can_claim_full_cashflow=false、native_sheet_verified=false、source_authenticity_verified=false。
当前没有真实账户和余额，本轮全部金额例为合成，不关闭真实资料待办，不接千问或数据库、不启动端口。
