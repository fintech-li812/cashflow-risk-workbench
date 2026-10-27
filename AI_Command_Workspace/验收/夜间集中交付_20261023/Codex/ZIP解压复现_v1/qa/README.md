> v2更新：修复JSON数值1e999/-1e999指数溢出可藏在额外字段的问题；JSON解析和直接库API两层拒绝非有限值。v1冻结保留，后续审核以本v2为最新候选。

# 制造业跨模块验收工具 MEM-QA-001（Codex v2候选）

2026-10-23。作者Codex。状态：离线候选，自测通过，待DeepSeek独立审核、X检查；没有上线。
目的：对导入包、现金流结果、保存回执和交付包做独立检查。不是主算法、存储服务或千问插件；不执行被测代码，不联网，不访问数据库。

## 环境与入口

Python 3.10及以上，标准库，无需pip。CLI从本目录运行；所有输入只读、输出必须是新的目录且不得在输入目录内。下面的输出目录请放在本解压目录之外，不存在才可写。

```powershell
python qa_tool.py selftest --workdir ../qa-selftest-new
python qa_tool.py verify-result --result examples/result.json --context examples/context.json --receipt examples/receipt.json --request-id save-1 --allow-fixture --output ../qa-result-new
python qa_tool.py verify-result --result examples/bad-one-cent.json --context examples/context.json --allow-fixture --output ../qa-reject-new
python qa_tool.py verify-package --package examples/import-package --source examples/import-package-sources --profile profiles/ooxml_profile.v1.json --mapping examples/import-package-mapping.json --output ../qa-import-new
python qa_tool.py replay --case-dir examples/replay-cases --plan-sha256 1104da29aa9ac53ad737bb5e9c1787a7d6aa3c688194ae9618d0da9e1cf10956 --output ../qa-replay-new
python qa_tool.py verify-delivery --input ../some-delivery.zip --output ../qa-delivery-new
```

第三条为故意错一分钱的负例，必须exit=1；不是命令运行失败需要重试。第一条自测保留自己的合成夹具与日志，不清理/删除。不得把示例allow-fixture用在生产。
正常exit=0仅表示该层检查通过；exit=1为失败/无效输入；exit=2为证据阻塞（argparse参数错误也可能使用Python标准退出码2，应结合JSON/命令提示）。

## 已实现

- verify-result：五字段/期间/单位/七金额、元分精度、净额/余额/差异、零与缺值、非success无完整金额、显式夹具隔离；回执身份/请求/内容摘要/时区校验。
- verify-package：路径/文件哈希/记录数/来源键/问题引用；显式选择候选OOXML适配后核原格类型/原值/公式/缓存及原精度元/万元转换，改字段再重算包哈希仍能发现。
- verify-delivery：目录或ZIP只读查看，不解包不执行，拒绝越界/符号链接/重名/超限；清单、版本、用例、独立预期、实际输出检查。工件齐全仍标“执行未观察”。
- replay：固定外部plan-sha256，固定每个输入摘要，只回放verify-result工件用例；支持跨用例同请求不同内容/record冲突；运行前后核计划及输入未变化。不会运行主算法或自动填平台33项通过。
- selftest：72个独立测试方法，含多组子例；v1历史15个变异被抓住，v2新增2个指数溢出/完整对象校验变异也被抓住。不是72条真实平台测试。
- results.json/issues.csv/report.html/summary.md；回放另有case-results.json。HTML纯离线转义，CSV防公式注入，不隐藏失败和阻塞。

## 必须知道的边界

qwen_sheet标签不能证明平台真实性，因此本工具对平台来源一律保留阻塞，需要实际平台取数/重算人工独立核验。committed回执只能核字段与摘要，不能证明数据库commit；不替代存储故障测试或MySQL回查。
context由调用方提供作离线比对基准，不是认证系统。actual_balance_provided/independent_actual_closing/expected_request_id是本地验收上下文补充，不是公共业务接口新字段，也不是已认证的余额来源。
导入cells/normalized底层形状未冻结，profiles中的mfg-qa-ooxml-profile.v1和mfg-qa-map.v1只是本工具候选适配，未修改共享接口；队友格式不相同时先做适配/提案，不能拿本地profile当其违约依据。未知profile/转换/缺源/缺映射保留阻塞。
源与映射如果同时由攻击者替换，普通SHA不证明历史真实性；传入的源目录、映射与预期计划摘要必须独立固定。本工具核所列记录的内容一致性，不证明所有应抽业务行已抽全，也不核日期/非金额转换的业务语义。
旧交付可能不满足本候选通用交付profile（如无manifest），输出缺项要与原任务对照，不自动当作者违反旧合同。ZIP上限2000项/64MiB解压体积、单文件16MiB，超限明确拒绝，不是已证明恶意。

## 资料

docs/适配协议与限制.md、templates/报告与消息草稿.md、test-output/。原先失败轮的日志在验收/MEM-QA-001/Codex/selftest_round1保留，第一轮有一个测试用了非法期间来测合法不同期间，已把测试输入改为2026-09，未改预期迎合程序。
v2的72项全绿、v1历史15/15变异和v2新增2/2变异仅支持相应版本候选质量，不构成独立审核或生产放行。原数据与他人交付未改，未运行任何平台/MCP/服务器写入。
