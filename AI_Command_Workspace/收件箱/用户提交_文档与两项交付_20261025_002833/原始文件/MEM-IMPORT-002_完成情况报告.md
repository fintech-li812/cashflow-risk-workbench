# MEM-IMPORT-002｜Excel 导入与来源追溯 — 任务流程梳理与完成情况报告

- 任务编号：MEM-IMPORT-002（承接 MEM-IMPORT-001 / 222）
- 执行：WorkBuddy（AI）；**真实姓名占位待补**（交付目录需按 `<真实姓名>` 归档）
- 完成时间：2026-10-24（+08:00）｜状态：**candidate（候选，未上线）**
- 离线 ZIP：`交付/MEM-IMPORT-002/MEM-IMPORT-002_WorkBuddy_v1.zip`
  （SHA256 `2c8d78a5…d70c95a43`，旁证 `MEM-IMPORT-002_WorkBuddy_v1.zip.sha256.txt`）

---

## 一、我理解的任务流程（先明确，再施工）

原始任务包里有一套串行协作流程（回执 → 等 X 通知 → 施工 → 交 DeepSeek 独审 → Codex 登记）。本次我按"用户即授权人"直接完成了施工段，其余环节（独立审核、登记）按包内纪律**不由我自审通过**，已在文档中留位。

执行链如下：

```
① 读任务书与规则（任务书_要求与验收 / 统一接口_v1 / 一期范围 / 算法约定 / 结果边界 / AGENTS / 最新审批与反例 / 222）
        ↓
② 只读核对受控样例：哈希 7e32b1ec…c13d0a3b 一致；确认 8 个 Sheet 真实结构与现金流水 A–I 列；D8=1631300；行12/15 重复
        ↓
③ 搭独立环境（Python 3.13.12 + openpyxl 3.1.5，不污染他人环境）
        ↓
④ 实现 scan / verify / selftest（src/mfg_import/）+ 映射配置 + 单位例外（绑定源SHA+Sheet+地址）
        ↓
⑤ 自造合成夹具跑 31 项正反例（不依赖真实企业文件/网络/他人模块）
        ↓
⑥ 受控样例实扫 → verify 通过 → 篡改字段并重算清单哈希的负例实验
        ↓
⑦ 整理交付包（README / 三类说明文档 / 四份交接CSV / manifest / SHA256SUMS）→ 打包 ZIP
        ↓
⑧ 再从 ZIP 解压到全新目录复跑一遍，确认别人照 README 能跑通
```

## 二、交付了什么

| 类别 | 内容 |
|---|---|
| 源码 | `src/mfg_import/`（canon 规范JSON与哈希 / xlsxraw 只读解析XML / convert 金额日期 / scanner 扫描出包 / verifier 独立核对 / report 离线HTML / selftest 自测 / `__main__` CLI） |
| 映射 | `mapping/mfg_sample_mapping.json`（源表名、表头行2、数据起始行3、字段别名、原单位万元）+ `fixtures/mapping_fixture.json`（自测用） |
| 例外 | `unit_exceptions.json`：`现金流水!D8` 绑定源 SHA `7e32b1ec…c13d0a3b` |
| 夹具 | `fixtures/make_fixtures.py`（源码，可重建；含直接改 XML 造公式/空串/serial 60 的能力） |
| 独立预期 | `tests/expected/expected_values.json`（冻结，运行前后核哈希，程序不改写） |
| 实际输出 | `test-output/`（自测 31 项、样例扫描包、篡改实验日志、源件前后哈希） |
| 文档 | README.md、设计与接口说明.md、错误码说明.md、未实现与待确认.md |
| 交接 | 01 需求与实现映射 / 02 测试结果 / 03 证据索引 / 04 继承与改动（固定列头） |

三条可照抄命令（在解压目录执行）：

```bash
python run.py selftest --workdir test-output/selftest_run

python run.py scan --input <样例目录> --output <全新目录> \
  --mapping mapping/mfg_sample_mapping.json --unit-exceptions unit_exceptions.json \
  --tenant-id sample-tenant --company-id sample-company --period 2026-09 --run-id sample-run-1

python run.py verify --package <上一步的输出目录> --source <样例目录>
```

## 三、测试结果（四状态数量闭合）

| 集合 | PASS | FAIL | BLOCKED | NOT_RUN | 合计 |
|---|---|---|---|---|---|
| 合成自测（31 项夹具正反例） | 31 | 0 | 0 | 0 | **31** |
| 受控样例实扫 + verify + 篡改负例 + 只读核验 | 4 | 0 | 0 | 0 | **4** |
| **合计** | **35** | **0** | **0** | **0** | **35** |

- 自测覆盖任务书最低矩阵全部要点：正常/列重排/缺列/重名与别名歧义/纵向字段换行/0与空/数字文本/公式有缓存与无缓存/长小数/万元精度/合法与非法日期/1904/1900虚构闰日/重复保留/部分到账/键稳定/源改变/D8例外绑定与不误拦/HTML与CSV注入/路径越界与重名/故意失败非0退出。
- **样例实扫实际数字**：记录 66 条，问题 3 条（`ISS-0001` D8 单位待核、`ISS-0002/0003` 行 12 与 15 重复证据，两行**都保留**）。
- 从 ZIP 解压到全新目录复跑：`PASS=31 FAIL=0`，退出码 0 —— 满足"另一人只按 README 就能跑"的验收前提。

## 四、关键负例（重点）

1. **篡改字段 + 重算清单哈希仍被抓**：把样例包 `现金流水!行3` 经营性流入由 `1808700.00` 改成 `180870000.00`，并按攻击者方式重算 manifest 所有文件 SHA256 后，verify 仍退出码 **1**，并打印
   `[FAIL] 第 35 行记录字段 经营性流入（万元） 被篡改: 包内值='180870000.00' 真实源 现金流水!行3 D3 重导值='1808700.00'`
2. **D8 不放大也不误拦**：仅在 `源SHA+Sheet+地址` 三要素同时命中时置 null；另一份不同源的同地址数值正常换算为 `16313000000.00`。
3. **金额精度**：`1.234567万 → 12345.67 元`（不是 12300.00）；`80.59999999999999` 原样保留，不显示成 80.6。
4. **日期不猜**：`2026-13-05`、`2026-02-30` 保持 null；`26-01-31` 不猜世纪；1900 系统 serial=60 明确报虚构闰日。
5. **源件只读**：样例扫描前后 SHA256 均为 `7e32b1ec…c13d0a3b`（`test-output/sample_source_sha_*.txt`）。

## 五、待确认 / 下一步（需要人拍板）

1. **交付目录真实姓名**：当前路径用 `WorkBuddy` 占位，需补真实姓名后归档为 `交付/MEM-IMPORT-002/<真实姓名>/v1/`。
2. **D8 真实单位**：未核实，保持 null；核实后按批准口径重导，不得自行缩放。
3. **真实企业数据**：只拿到含故意错误的受控样例，未拿到真实企业文件，因此**不声称真实企业扫描通过**。
4. **可信源摘要保管**：verify 无法对抗"真实源 + 全部可信哈希被同时替换"，需线下固定一份可信 SHA256 清单并明确谁保管。
5. **千问/MySQL 端到端**：本包禁止连接，全部未做（U1–U8 已登记在《未实现与待确认》）。
6. **审核与登记**：按包内纪律，代码待 DeepSeek 独立审核、Codex 登记；我不自审通过、不宣布上线。

## 六、按顺序移交的打包内容

`MEM-IMPORT-002_WorkBuddy_v1.zip` 根目录直接含 `README.md`，解压即可照抄命令运行；包内 manifest.json 记录 316 个交付文件的路径与 SHA256，SHA256SUMS.txt 覆盖其余全部文件及 manifest（排除自身），不含 venv、缓存、私钥或真实个人流水。
