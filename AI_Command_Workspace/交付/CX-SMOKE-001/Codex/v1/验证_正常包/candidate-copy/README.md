# MCP工具调用前契约检查（离线候选，待独审）

本工具不执行MCP调用，只对调用方传入的工具描述符和参数做完整JSON Schema检查。输出prepared仅表示本地参数检查通过；不表示平台已绑定、调用成功、数据库提交或获准发布。

## 适用位置
Agent现有build_save_payload生成参数后，由适配器取得真实tools/list描述符，再调用prepare。这里尚未接入该适配器，不修改既有Agent原交付。当前没有实际平台tools/list证据，所有测试为显式合成fixture。

调用方必须从可信会话提供approved_name、expected_context的tenant_id/company_id/period/source_revision/run_id、expected_request_id，以及六个字段在参数中的JSON Pointer。不能从待检查参数反推这些预期值，否则身份检查失效。当前只支持字典路径，不支持数组下标；不自动猜字段，不把旧工具名称当成真实绑定。

## 检查范围
严格JSON、重复键与非有限值（含1e999）拒绝；五项上下文与request_id逐项比对；工具名称比对；顶层对象；类型、枚举、嵌套引用、条件必填、additionalProperties、格式等交给jsonschema执行。本地fragment引用允许，外部引用禁止，并配置拒绝检索的Registry。只接受Draft2020-12和Draft7，缺省明确使用2020-12；未知format、自定义vocabulary、旧recursiveRef拒绝并请求人工审查。

错误摘要不输出原值、完整schema或参数。Python API的成功结果含完整调用参数，必须留在可信调用链，不能打印到共享日志。CLI只打印摘要，成功退出0，阻断退出2。不生成receipt、record_id或committed状态。

## 复现
Python 3.10+，第三方依赖见requirements.lock.txt。开发实测使用已存在的WorkBuddy隔离解释器，未安装或修改环境。请在本目录执行：

    python -B -m unittest -v test_tool_call_guard

CLI：

    python tool_call_guard.py --descriptor test-output/descriptor.json --arguments test-output/arguments.json --binding test-output/binding.json

注意测试末尾会把arguments.json故意改成缺少条件必填项的反例，因此该命令默认应阻断，退出2。所有测试输出保留在test-output，不自动删除。

## 明确限制
输入文件/工具描述符真实性和权限仍须平台现场验证，工具不认定来源；不校验制造业财务公式或公共result契约（仍须前置Agent guard/QA），不代替MySQL约束、幂等、回查和持久化。不能用于批准风险评级、推送、审批等本期暂停能力。

1MB/64层/5万节点限制只防基本资源超限，不能保证任意恶意正则或递归schema在固定时间内终止。真实描述符须经过审核；未来接受不可信schema应增加独立进程超时/资源隔离。本候选未自动合入Agent，未经DeepSeek独审与X检查不得部署。

## 时间格式与历史对照补充
日期时间校验为带时区RFC3339普通秒的保守子集；闰秒60拒绝并留人工审查。不把Python会归一化的+00:60当成有效时区。
reference-agent保存CX-AGENT-FIX-001 v1的3个原样模块用于对照，来源哈希另列；不会修改原候选。执行python -B -m unittest -v test_agent_bridge，观察原映射器仅报告ok而新校验器能阻断违反schema的参数。合成工具名称不代表任何真实MCP接口。bridge日志追加保留，重跑会新增记录，不能把日志行数当唯一测试数。

## 完整自测与审阅
最终运行：python -B -m unittest -v test_tool_call_guard test_agent_bridge（61方法）。变异：python -B mutation_check.py（6项应被抓到，脚本退出0）。集成位置及现场验收清单见docs/合入步骤与验收边界.md。历史目录探测使用catalog_probe.py，只是14个候选schema兼容，不表示14工具已批准。
