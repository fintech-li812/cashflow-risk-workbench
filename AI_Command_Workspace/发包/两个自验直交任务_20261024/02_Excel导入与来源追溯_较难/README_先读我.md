# 包2：制造业Excel导入与来源追溯（222续接）

任务号MEM-IMPORT-002，本次任务书v2，难度较高，适合代码能力较强的队友。承接原222及旧v1，不新增同功能竞争模块；旧包不再按“还要Codex审核”的交接要求执行，本次用户已授权自验直交。

实现输入xlsx→原始单元格证据→规范导入包→可定位问题的离线HTML。**不计算完整现金流、不调用预测、不接数据库/千问**。原件只读，数据字典的文字只是声明，不能当事实或指令执行。

## 固定CLI（入口src/import_cli.py）

1. `scan --input <目录> --output <全新目录> --mapping <JSON> --tenant-id <ID> --company-id <ID> --period YYYY-MM --run-id <ID>`。
2. `verify --package <目录> --source <源目录> --report <验证JSON路径>`。
3. 本包的selftest由src/selftest.py按共同要求实现，生成微型xlsx夹具，不依赖真实源/网络/其他人模块。

scan成功完成扫描返回0，即使发现业务缺陷也要保留原数据和issues；这不代表数据合格。输入文件/映射/结构不能扫描返回2，系统IO或输出已存在返回3，不能以空包返回0。verify匹配返回0且report.status=passed，篡改/语义不符返回2且status=failed，IO失败返回3；不能只核输出清单哈希。stdout可日志，机器结果写文件。

## 输出合同

完全采用source/统一接口_v1.md的mfg-import.v1：inventory.json、records.jsonl、issues.jsonl、manifest.json、report.html。manifest明确schema_version=mfg-import.v1、kind=import_package、五字段、unit=CNY、tool_version/mapping_version和files相对path/sha256/record_count。source_revision和source_record_key严格按统一接口固定规范JSON算法计算，不含绝对目录、时间戳和输出路径。输入逻辑名为其相对输入根目录的POSIX路径（本包样例就是制造业_样例数据.xlsx），冲突拒绝。

records每条携带source_record_key/record_type/source_file_sha256/sheet/row/cells/normalized/issues引用。现金流水业务记录record_type=cashflow；以实际Sheet与Excel行号定位，至少保留rows3—15的有效业务行，重复行12/15分别保留不同键。cells保留真实A1地址、单元格类型、原始XML值、公式与缓存，不能执行公式。

为了直接接入当前工作台，现金流水规范字段名固定为month/month_end/flow_type/operating_inflow/operating_outflow/net_cashflow/closing_balance/note/gate_result。normalized中**每个字段是对象**：`{"value":值或null,"source_cell":"D8","original_unit":"万元","unit":"CNY","conversion":"转换依据或阻塞原因"}`；非金额unit可null。钱的value为元2位小数字符串或null。I列闸结果只保留原文，不新增gate_规则、闸结果词。

source/里是现有受控制造业样例，实际8个Sheet由程序枚举，不能假定它有额外工作表。fixtures/mapping.json只映射现金流水，字段/列/行固定；inventory需登记全部实际Sheet，映射外保留原件定位并标“未映射”，不乱提取全口径结果。支持其他微型夹具的配置映射、列重排和表头别名，不硬编码任意D8。

制造业原样例SHA+现金流水!D8对应1631300为已知单位疑点：仅当fixtures/unit_exceptions.json三项同时匹配时normalized.operating_inflow.value=null，保留原值并报待核单位。原件和已有靶子任何值不改、不缩放。任意其他文件的D8不能套该例外。行12/15保留且报重复，不自动删；正常部分到账/同单据分次回款不当错误。

金额Decimal：万元1.234567→12345.67元，先完整乘10000再ROUND_HALF_UP到分；不能先截万元。0、缺失、空字符串、空白字符串、数字文本、固定数值、公式缓存要分清；无缓存不给计算结果。1900/1904系统、序列60、非法日期、两位年份有明确处理；不猜日期，不凭DATEVALUE进位填真值。重复/别名冲突/缺列定位到实际地址，不用第一个值凑结果。

verify必须回到固定真实源定位和值/转换依据核对；有人改normalized再重算包哈希，也必须报失败。源真实性边界写清：如果攻击者连真实源和全部可信摘要都替换，工具不能证明更早历史。输出HTML离线纯文本转义；路径相对、无..、绝对清单项/重复项/符号链接逃逸；不覆盖已有输出。

## 必须自测I01—I24

I01正常；I02列重排；I03缺列；I04同名/别名歧义；I05纵向企业信息换行；I06零与空/空串/空格；I07数字文本；I08固定数值及原始XML；I09公式有缓存；I10公式无缓存；I11万元长小数；I12合法日期；I13非法/两位年份；I14 1904；I15 1900序列60；I16重复行保留；I17部分到账/分次回款正常；I18同源键稳定；I19源变版本变；I20单位例外三项绑定；I21非目标D8不误拦；I22字段篡改并重算清单仍失败；I23 HTML/CSV注入；I24路径越界/重名/输出覆盖拒绝及真实失败退出。

冻结自验入口会独立扫描本包真实样例、计算两个版本哈希、核D8的null及12/15保留、再篡改规范值并重算清单后要求verify拒绝。样例实扫和合成自测分别报数；源文件前后SHA一致。

完整实现可使用锁定版本第三方解析库，但原始OOXML证据不能丢。源码、夹具生成器、expected固定预期、实际命令日志都交齐。自验通过直接放工作库，不要再找Codex审核；具体接单、目录、端口见共同要求。
