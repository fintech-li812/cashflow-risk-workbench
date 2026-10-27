# 制造业导入包审批修订报告
原WorkBuddy v1本次审批打回，Codex v2修复候选已另存。原ZIP摘要2c8d78a5985e778584a3854dfc24af947e2d577029b1c167e71b919d70c95a43。
原包存在日期1900序列1/59少一天、verify清单缺必需项仍通过、测试文件永久删除逻辑；前两项有修前修后反例。
修订后31/31自测与6/6独立检查通过。受控样例实扫66记录3问题，D8规范null、12/15行均保留，未修改源xlsx。
原包manifest漏列36个嵌套manifest，根清单误按文件名排除了全部同名文件；v2根清单将覆盖全部工件，仅排除根manifest与SHA256SUMS。
最新自验合同要求src/import_cli.py、src/selftest.py、schema_version及operating_inflow/source_cell等，当前包仍沿旧接口，冻结自验未通过。
因此只收为修复候选，不合并千问正式服务；需适配最新合同并通过冻结自验。真实姓名不是阻止收件理由，先登记WorkBuddy，姓名待X补。
