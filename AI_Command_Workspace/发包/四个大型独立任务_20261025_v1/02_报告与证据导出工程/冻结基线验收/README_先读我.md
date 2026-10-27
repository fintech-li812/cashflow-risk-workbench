# 包1：制造业报告与证据导出器

任务号MEM-REPORT-002。难度中等，交给能写Python/HTML的队友。当前工作台已有合法结果与MySQL回执，缺可携带、可复核的正式导出组件。此包补这个空白，不改算法和存储，也不重复开发浏览器工作台。

## 固定命令与产物

实现`src/report_cli.py export --result <JSON> --context <五字段JSON> --output-dir <新目录> [--receipt <JSON>] [--allow-fixture]`。

输出report.html（单文件离线HTML，内联CSS）、report.csv（UTF-8/可带BOM，表头固定key,value）、result.json（与输入语义完全一致）、manifest.json；只有确实给了有效receipt才输出receipt.json。manifest.schema_version=`mfg-report-export.v1`，files为path/sha256列表，路径相对、无重复/越界，不包含自身。正常返回0；输入/合同/证据不匹配返回2且不创建输出目录；输出已存在/IO异常返回3，保留原输出不覆盖。

先校验再建输出目录。用source/agent_guard.py的约束验证结果；不修改此参考。JSON拒绝重复键、非有限数。context由调用方提供，不从企业名猜ID。非success结果本身可合法导出，但不能展现成功金额或配成功回执。

HTML写清企业/期间/单位/来源/计算版本、七金额字段、缺项/异常说明、提供的留档凭据。合成数据必须显著出现“合成数据”，默认拒绝，只有--allow-fixture可导出。actual_closing/difference为null时显示“尚未完成余额核对”，不能填0或宣称勾稽完成。

没有receipt写“未提供入库凭据”，不生成假的receipt文件。有receipt先核schema_version/kind/operation/status=committed、五字段、非空request_id/record_id、合法stored_at、payload_sha256；摘要针对完整规范结果。任何不符返回2。即使匹配，也标“回执文件匹配，未在线复核数据库”；本工具不写库、不在线查库，不能说本次执行了保存。origin=qwen_sheet仅为来源声明，必须提示本工具未验证千问原生取数。

HTML不含脚本、外链、iframe、在线资源；所有输入文本转义。CSV每一行固定key/value，至少有amounts.<七键>和source.<四定位键>；=、+、-、@及前置控制字符引导的公式文本要中和（在展示CSV中前置单引号），原始JSON保持不变，不把CSV防注入后的展示串反写金额。恶意workbook_ref不当路径打开，不加载外部资源。

## 必须自测（R01—R20，与task.json对应）

R01合法结果+匹配回执；R02无回执；R03缺独立余额；R04 missing_inputs；R05 formula_error；R06 unavailable；R07企业/租户不匹配；R08期间/来源/run不匹配；R09回执摘要不符；R10浮点/指数/NaN/无限值；R11三项算术勾稽不符；R12负净额与负余额合法保留；R13重复JSON键；R14合成默认拒绝；R15 HTML注入；R16 CSV注入；R17已有输出不覆盖；R18缺文件/依赖时非0；R19多个来源引用及长中文可读；R20新环境解包复现、输入原件SHA不变。

冻结自验入口还会独立构造多组JSON、故意篡改回执与金额、重复执行同输出路径。实现源码不得只识别夹具文件名、测试路径或case_id。

## 源文件

source/agent_guard.py为当前保护逻辑，只参考/复用不改协议。fixtures/result.json为已用合成结果，receipt.json为同一合成请求的真实隔离库回执，context.json为对应五字段。该回执只用于输入样例，不意味着队友连接过数据库。

不需要导入器产物、真实企业数据、MySQL或千问账户。自验通过直接提交工作库，具体目录、端口及回执格式见共同要求。历史MEM-DOC-001的文字整理不因此标为完成，本包只负责可运行导出组件。
