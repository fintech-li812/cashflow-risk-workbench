# MEM-IMPORT-002｜制造业 Excel 导入与单元格来源追溯工具 v1

任务编号 MEM-IMPORT-002（承接 MEM-IMPORT-001/222）。执行者：WorkBuddy（AI 助手；**真实姓名占位待用户补填**）。
状态：**candidate（候选）**，未上线、未接生产、未连数据库。

一句话：把制造业 xlsx 变成有原始单元格证据的规范数据包（mfg-import.v1），
并让别人能查出被篡改的字段。

---

## 1. 环境（只装自己的独立环境，不污染他人环境）

- Python：**3.13.12**（见 `PYTHON_VERSION.txt`）
- 依赖（锁定版本，见 `requirements.txt`）：**openpyxl==3.1.5**（仅用于生成夹具与写 xlsx；读取走标准库 zipfile+ElementTree 解析 XML）
- 不需要网络、不需要 MySQL、不需要千问账号、不需要别人的模块

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS/Linux
```

## 2. 三条可直接照抄的 CLI（在解压后的 v1 目录执行）

> 所有输出目录必须**全新**：已存在即拒绝（退出码 2），绝不覆盖旧成果。

### 2.1 自测（只用合成夹具，不需要真实企业文件）

```bash
python run.py selftest --workdir test-output/selftest_run
```
预期：`PASS=31 FAIL=0 BLOCKED=0 NOT_RUN=0`，退出码 0；用例明细见该目录下 `selftest_results.json` / `selftest_log.txt`。

### 2.2 扫描受控样例（样例只读，输出到新目录）

```bash
python run.py scan \
  --input  <放制造业_样例数据.xlsx的目录> \
  --output <全新输出目录> \
  --mapping mapping/mfg_sample_mapping.json \
  --unit-exceptions unit_exceptions.json \
  --tenant-id sample-tenant --company-id sample-company \
  --period 2026-09 --run-id sample-run-1
```
预期：退出码 0；输出 `inventory.json / records.jsonl / issues.jsonl / issues.csv / mapping.snapshot.json / unit_exceptions.snapshot.json / manifest.json / report.html`。
**scan 退出码 0 只表示技术执行成功，不代表数据合格**（业务疑点在 issues.jsonl 与 report.html）。

### 2.3 独立核对（篡改字段并重算清单哈希也逃不掉）

```bash
python run.py verify --package <上一步输出的包目录> --source <源目录>
```
预期：干净包退出码 0；源被改 / 字段被篡改 / 清单被重算 → 退出码 1，并打印源定位（如 `现金流水!行3 D3`）。

## 3. 输出包内容

| 文件 | 作用 |
|---|---|
| `inventory.json` | 输入文件 SHA256、日期系统(1900/1904)、Sheet 清单与原始记录计数、映射/工具版本 |
| `records.jsonl` | 逐记录：`source_record_key`、sheet、row、cells（类型/XML原值/公式/缓存）、normalized（每个字段的真实地址与转换依据）、issues 引用 |
| `issues.jsonl` / `issues.csv` | 问题清单（ID/代码/文件/Sheet/地址/原值/原因/人工动作）；CSV 导出防公式注入 |
| `manifest.json` | kind=import_package、五字段、unit=CNY、tool_version、files[path,sha256,record_count]；清单不含自身哈希 |
| `report.html` | 离线报告：无外部脚本/请求，Excel 内容全部 HTML 转义 |
| `mapping.snapshot.json` | 映射**原始字节拷贝**（保证包内快照哈希 = 源映射哈希，source_revision 可复算） |
| `unit_exceptions.snapshot.json` | 本次生效的单位疑点例外快照 |

统一规范：
- `source_revision = SHA256(规范JSON({"mapping_sha256":…,"sources":[{"logical_name","sha256"}…] 按名排序}))`
- `source_record_key = SHA256(规范JSON({"source_file_sha256","sheet","row"}))`
- 规范 JSON = `json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',',':'), allow_nan=False).encode('utf-8')`
- 金额全部为元、2 位小数**十进制字符串**或明确 `null`，不用浮点存钱；源万元按原精度 ×10000 后在元位 ROUND_HALF_UP 落分（1.234567万 → 12345.67 元，不是 12300.00）

## 4. 本包样例实扫结果（受控样例，非真实企业）

- 源件：`制造业_样例数据.xlsx`，SHA256 `7e32b1ec…c13d0a3b`，scan 前后 **完全一致**（见 `test-output/sample_source_sha_before.txt` / `_after.txt`）
- 结果（见 `test-output/sample_scan_stdout.txt` 与包内文件）：**记录 66 条，问题 3 条**
  - `ISS-0001 UNIT_SUSPECT_PENDING`：`现金流水!D8` 原值 `1631300` —— 绑定源 SHA+Sheet+地址 的已登记单位疑点，**规范值 null、原值保留、不再乘 10000**
  - `ISS-0002/0003 DUPLICATE_ROW`：行 12 与行 15 取值完全相同 —— **两条都保留**并各自给证据，不删除、不合并
  - 8 个 Sheet 中 6 个已映射；`行业参数`、`数据字典` 仅登记不删除、不当真值执行
- 样例中未出现的 Sheet/列一律不硬套；现金流水仅经营性口径，**不伪称全口径收付**

## 5. 篡改实验（关键负例，可复现）

步骤见 `test-output/tamper_steps.txt`，原始日志 `test-output/tamper_verify_log.txt`：

1. 复制扫描包 → 把 `现金流水!行3` 经营性流入 由 `1808700.00` 改成 `180870000.00`
2. **按攻击者方式重算 manifest 中所有文件 SHA256**（清单自洽，纯哈希比对会误判通过）
3. `verify` 仍失败，退出码 **1**，并打印：
   `[FAIL] 第 35 行记录字段 经营性流入（万元） 被篡改: 包内值='180870000.00' 真实源 现金流水!行3 D3 重导值='1808700.00'`

**威胁边界（必须写明）**：本模块不能证明"更早的历史真相"。若攻击者同时替换真实源**并且**替换全部可信哈希，本工具无法识别——源真实性必须依赖外部固定的可信源摘要（如线下登记并单独保管的 SHA256 清单）。

## 6. 目录

```
README.md / 设计与接口说明.md / 错误码说明.md / 未实现与待确认.md
run.py                统一入口（等价于 PYTHONPATH=src python -m mfg_import）
src/mfg_import/       canon · xlsxraw · convert · scanner · verifier · report · selftest · __main__
mapping/              样例映射（源表名/表头行/数据起始行/别名/原单位）
unit_exceptions.json  单位疑点例外（绑定源 SHA + Sheet + 地址）
fixtures/             make_fixtures.py 合成夹具生成器源码（不是手工截图）
tests/expected/       独立预期（冻结文件，运行前后核 SHA256，程序不改写）
test-output/          实际输出：自测、样例扫描、篡改实验、源件前后哈希
01_需求与实现映射.csv · 02_测试结果.csv · 03_证据索引.csv · 04_继承与改动.csv
manifest.json · SHA256SUMS.txt
```

## 7. 边界（本包明确不做）

只做制造业实际现金流周边的导入与证据保留；不做主算法、滚动预测、评级、现金折扣、K灯级/QDP/FUSE、其他行业、通知与定时任务。
不连接千问/云端/生产数据库，不索要账号或私钥，不改源文件，不执行 git push，不外发消息。
