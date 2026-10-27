# 制造业Agent周边工程统一接口 v1

日期2026-10-23。只做制造业现金流；核心算法、财务分析原理和滚动预测由另一个队友负责，本轮三包不重复实现。原件只读。平台函数用户已确认可用，真实读表/算法/MCP链路仍待验证。

## 统一的五个身份/版本字段

所有包、结果与回执必须携带tenant_id、company_id、period、source_revision、run_id，字段名完全一致，类型均为非空字符串。period为YYYY-MM且月份合法。调用者提供企业/租户/run，不能根据文件名或公司名称猜数据库ID；平台运行时由认证绑定提供可信身份，不允许上传内容覆盖。
source_revision在导入包中按下述固定算法计算；结果和回执原样传递，数据改变必须变更版本。每个规范业务数据包注明unit=CNY，所有金额为元、2位小数的十进制字符串或明确null，不能用JSON浮点存钱。
request_id是每次逻辑保存操作的非空标识，与run_id不同；同一逻辑重试沿用同一request_id和相同payload，新结果用新逻辑请求。tenant/company等身份字段不是认证机制，不能仅凭传入字段授权读写。

## 三种工件，各司其职

1. mfg-import.v1：导入包。manifest.json带kind=import_package、五字段、unit、tool_version、mapping_version及files清单。files逐项为相对path/sha256/record_count；禁止绝对路径、..或重复path。清单不包含自身哈希。
source_revision=SHA256(UTF8规范JSON)：对象为{"sources":[{"logical_name":输入逻辑文件名,"sha256":源文件SHA256},...],"mapping_sha256":映射文件字节SHA256}。sources按logical_name排序；逻辑名不可冲突；不含绝对路径、扫描时间和输出路径。
inventory.json登记输入日期系统、文件/Sheet/表头及数量；records.jsonl每条含source_record_key、record_type、source_file_sha256、sheet、row、cells、normalized、issues引用。source_record_key=SHA256(规范JSON对象{"source_file_sha256":...,"sheet":实际Sheet名,"row":整数行号})。cells按A1地址保留类型/原始XML值/公式/缓存；normalized字段逐个有真实地址及转换依据，未知值null。issues.jsonl包括issue_id/code、来源定位、原因、人工动作。issue_code是导入问题分类，不是gate_规则和闸结果。
2. mfg-agent-result.v1：算法/千问表格结果，采用CX-AGENT-002/Codex/v1/接口与状态说明.md和fixtures/synthetic_success.json定义的扁平字段，不再套一层重复context。五字段与导入包一致，schema_version即此版本，industry=manufacturing。
status为success/missing_inputs/formula_error/unavailable；非success时amounts=null、issues非空。成功时origin=qwen_sheet、unit=CNY、coverage=full_cashflow、calculation_version非空、source有workbook_ref/sheet/range/snapshot_ref；amounts包含opening/inflow/outflow/net/closing/actual_closing/difference七键。独立实际余额缺失时后两键都null，不能假报完成勾稽。只有经营数据时不要伪造full_cashflow，返回缺项和经营部分说明；经营部分视图后续另审扩展。
离线夹具origin=offline_fixture，只能在显式测试模式使用并醒目标注；生产模式禁止fixture。标签本身不能证明真实平台来源，适配器必须绑定实际读表/重算证据。未有算法或平台时返回unavailable，不产生假成功。
3. mfg-evidence.v1：本地证据存储回执。schema_version=mfg-evidence.v1、kind=receipt、operation=save_cashflow_result、五字段、request_id、record_id、payload_sha256、stored_at、status=committed。仅真实原子提交完成后生成；record_id是本地存储ID，不能伪称MySQL主键。
相同(tenant_id,company_id,operation,request_id)和同payload_sha256返回同record_id；同键不同payload必须冲突，不覆盖旧值；不同租户隔离。旧记录只追加，新版本保留历史，并明确当前有效记录的选择规则，不能以最大ID猜跨企业最新。

## 固定JSON与金额规范

规范JSON统一json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')；字符串保留Unicode码点，不额外归一化。payload_sha256针对完整结果对象，不包含后来生成的回执。业务值字符串精度保留原始证据，源万元按原精度乘10000后在元位ROUND_HALF_UP落到分；单位疑点不自动换算。浮点噪声不等于可以把万元先截到2位。
原件不改、不补0、不猜日期、不删除重复、不把正常部分到账当错误。缺失和真实0必须区分。异常、阻塞不能都塞入success。
路径、账户和私钥不进业务输出/日志；仅记录非敏感配置项名。不得新增生产event_type或gate_词表；本文件的schema/status是候选本地接口，和旧MCP/SQL的映射由WorkBuddy另交差异表，未批准不得部署。

## 交接规则

每个队友可以在自己的v1/v2目录迭代，固定接口内的错误修复不用反复问用户；不得修改他人目录、共享规范、原数据、服务器或已验收版本。字段/单位/公式/权限变化必须写变更提案，批准后发布共同版本，不可各改各的。
三包各有合成独立夹具和selftest，不能等待别人先做完才自测；这些fixture必须明显是测试。最终集成按导入→证据存储→验收工具顺序交接，严格串行，不同时启动多个施工任务。
统一交付README、锁定依赖、自测入口、机器可读结果、源原件前后哈希、限制、SHA256SUMS。正例和负例都有独立预期；失败退出码非0；不得边运行边覆盖预期基准。最终全体成果先交X检查，未通过不能说已上线。
