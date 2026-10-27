# MEM-EVIDENCE-001 v1｜可靠结果存储与故障恢复（本地 SQLite 事务）

- 任务编号：MEM-EVIDENCE-001（对应原总清单 D03/D04，接原任务二）
- 作者：WorkBuddy（AI）｜状态：**candidate（候选，未审核、未上线）**
- 范围：制造业现金流结果的**本地可靠存储、幂等保存、精确回查与故障恢复**
- 不在范围：主算法、滚动预测、评级、现金折扣、K灯级/QDP/FUSE、其他行业、通知与定时任务；
  **不连千问/云端/生产数据库，不部署服务**

> 本包全部结果来自**合成夹具**与**本机受控 SQLite 测试库**。
> `status=committed` 仅表示本地事务已提交，**不是**服务端 MySQL 入库证明，也不代表千问/生产运行通过。

---

## 1. 环境要求

- Python：实测 **CPython 3.13.14**（Windows），最低 3.10+；**无任何第三方依赖**（仅标准库，见 `requirements.lock.txt`）
- 不需要服务器账号、不需要完整项目、不需要其他队友的成品
- 数据库只在调用者传入的 `--workdir` 内创建，路径逃出目录一律拒绝（退出码 2）

## 2. 一条命令自测（照抄即可）

在**解压后的包根目录**执行（`<新目录>` 必须是全新目录，已存在且非空会被拒绝）：

```bash
python -m src.cli selftest --workdir <新目录>
# 等价入口：
python tests/run_tests.py --workdir <新目录>
```

Windows 实测示例：

```bash
python -m src.cli selftest --workdir D:\tmp\mem-evidence-run1
```

预期：**28 个用例全部通过，退出码 0**；结果写入 `test-output/`（`results.json`、`results.csv`、
`summary.md`、`run_log.txt`、`cases/*.out`）。存在失败/阻塞/未执行时退出码 10。

验证"失败退出码能真实触发"（故意让一例断言失败）：

```bash
python -m src.cli selftest --workdir D:\tmp\mem-evidence-inject --inject-failure
# 预期退出码 10，输出 code=SELFTEST_FAILED
```

## 3. 目录结构

```
README.md                     本文件
设计与接口说明.md              存储结构、迁移、事务时序、幂等/冲突、版本选择、适配说明
错误码说明.md                  退出码与语义状态对照
trust_boundary.md             信任边界（未接生产认证，如实说明）
未实现与待确认.md              未实现清单与待裁决项
src/
  result_guard.py             结果校验守卫（继承参考候选 agent_guard.py 的防御式改写）
  evidence_store.py           SQLite 事务存储、幂等、回执、历史、verify-store
  cli.py                      save/get/history/verify-store/selftest + 故障注入入口
  selftest.py                 测试矩阵编排
tests/
  run_tests.py                自测入口（与 CLI selftest 等价）
  tamper_db.py                篡改子进程（模拟具备库文件写权限者）
  static_boundary_check.py    静态边界扫描（无外连/无删除逻辑/无凭据读取）
fixtures/                     合成夹具（全部标注合成，非真实数据）
expected/                     冻结的独立预期（运行只读，前后核哈希）
test-output/                  本次运行结果与原始输出
01_需求与实现映射.csv / 02_测试结果.csv / 03_证据索引.csv / 04_继承与改动.csv
manifest.json / SHA256SUMS.txt / requirements.lock.txt
```

## 4. CLI 完整实例

以下命令在包根目录执行，`--workdir` 指向本次运行目录，库文件只能建在该目录内。

### 4.1 save（保存正式结果）

```bash
python -m src.cli save --workdir D:\tmp\run1 \
  --input fixtures/synthetic_success.json \
  --context fixtures/trusted_context.json \
  --request-id req-main-001 --store tc01.sqlite3 --allow-fixture
```

实际输出（节选，单行 JSON）：

```json
{"code":"OK","fixture_warning":"【合成数据·非生产·offline_fixture】 本次为合成夹具结果，不代表真实来源，不得当作生产证据","ok":true,"outcome":"created","receipt":{"company_id":"fixture-company","is_fixture":true,"kind":"receipt","note":"本地存储ID，不是MySQL主键；committed 仅表示本地事务已提交","operation":"save_cashflow_result","payload_sha256":"ccd841c7b7412c0ffc9035f7611ca38ced60dbf2fd4f1fc687ce9c1b1e7c4456","period":"2026-08","reconciliation_state":"completed","record_id":"loc-8b0eccb1d1979b5df9d4d4d0","request_id":"req-main-001","run_id":"fixture-run-1","schema_version":"mfg-evidence.v1","source_revision":"fixture-rev-1","status":"committed","stored_at":"2026-10-24T15:07:28Z","tenant_id":"fixture-tenant"},"status":"committed"}
```

要点：`--allow-fixture` 是测试开关；生产来源 `origin=qwen_sheet` 时不要加，也不允许反过来把 fixture
写成 qwen_sheet。非 success 结果只能走 `--save-diagnostic`（存诊断，不产生正式回执）。

### 4.2 get（精确读取并复核摘要）

```bash
python -m src.cli get --workdir D:\tmp\run1 --context fixtures/trusted_context.json \
  --record-id loc-8b0eccb1d1979b5df9d4d4d0 --store tc01.sqlite3
```

```json
{"code":"OK","fixture_warning":"【合成数据·非生产·offline_fixture】","ok":true,"receipt":{"...":"同上回执"},"record_id":"loc-8b0eccb1d1979b5df9d4d4d0","reconciliation_state":"completed"}
```

跨身份读取（用另一份固定可信上下文）被拒，**且响应不含原记录内容**：

```bash
python -m src.cli get --workdir D:\tmp\run1 --context fixtures/trusted_context_other.json \
  --record-id loc-8b0eccb1d1979b5df9d4d4d0 --store tc01.sqlite3
# {"code":"SCOPE_DENIED","details":{},"message":"record is outside the trusted identity scope","ok":false,"status":"denied"}
# 退出码 6
```

### 4.3 history（只追加 + 当前有效选择）

```bash
python -m src.cli history --workdir D:\tmp\run1 --context fixtures/trusted_context.json \
  --period 2026-08 --store tc17.sqlite3
```

返回 `count=2`、`distinct_source_revisions=["fixture-rev-1","fixture-rev-2"]`、
`current_record_id` 为同主体同期间内最后写入的一条，并附带 `current_selection_rule` 原文说明。
可用 `--source-revision fixture-rev-1` 显式锁定旧版本；旧记录既不删除也不被改写。

### 4.4 verify-store（一致性复核）

```bash
python -m src.cli verify-store --workdir D:\tmp\run1 --store tc01.sqlite3
# {"code":"OK","message":"store consistency check passed","ok":true,"report":{"diagnostic_records":0,"formal_records":1,"problems":[],"store_schema_version":"evidence-schema-1","verified_at":"..."},"status":"verified"}
```

检出篡改时退出码 8，并给出问题码（PAYLOAD_HASH_MISMATCH / IDENTITY_LINK_BROKEN /
RECEIPT_INCOMPLETE / AMOUNT_RECONCILE_FAILED / DIAGNOSTIC_MISLABELED）。

### 4.5 故障注入入口（只影响本包自己启动的子进程）

| 参数 | 作用 | 期望 |
|---|---|---|
| `--fault-before-commit` | INSERT 后、COMMIT 前终止进程 | 退出码 9；库中 0 条；重新打开自动回滚 |
| `--fault-after-commit` | COMMIT 后、回执返回前终止进程 | 退出码 9；库中有 1 条；同 request-id 重试返回原 record_id |
| `--simulate-unknown` | 提交已完成但回执未确定交付 | 退出码 11 UNKNOWN_STATE，**不报成功** |
| `lock-hold --seconds N` | 子进程独占写锁 | 期间 save 返回退出码 7 STORAGE_BUSY，不无限重试 |

## 5. 本次自测结果（本机合成夹具）

| 项目 | 数值 |
|---|---|
| 用例总数 | 28 |
| 通过 / 失败 / 阻塞 / 未执行 | 28 / 0 / 0 / 0 |
| selftest 退出码 | 0 |
| 故意断言失败运行 | 退出码 10（`test-output/inject_failure_run.json`） |
| 实测环境 | CPython 3.13.14，Windows |

覆盖：正常提交与重启读回、幂等回放、同键冲突、全 0 金额、缺实际余额、差异一分、非法金额/非有限值/勾稽错误、
缺必填、身份错、源版本错、非 success 拒绝与诊断通道、默认拒 fixture 与显式允许、提交前故障、提交后回执丢失恢复、
6 进程受控竞争、SQLite 锁超时、历史追加与当前版本选择、跨身份隔离、verify 正常与库重开、payload/摘要/关联字段三类篡改、
路径穿越与重名拒绝、SQL 特殊字符、未确定态、故意断言失败、静态边界检查、独立预期运行前后哈希一致。
明细见 `02_测试结果.csv` 与 `test-output/results.json`。

## 6. 退出码速查

0 OK｜1 未预期异常｜2 用法/路径越界｜3 校验拒绝｜4 幂等冲突｜5 范围内不存在｜6 越权｜
7 锁超时｜8 一致性失败｜9 故障注入｜10 自测失败｜11 保存状态未确定
完整口径见 `错误码说明.md`。

## 7. 边界与声明

- 未接生产认证：`--context` 只是**测试可信上下文**，CLI 自填身份必须与它一致，详见 `trust_boundary.md`。
- 摘要只能检出"未同步改写全部可信摘要"的改动；能重写整个库及全部可信摘要的攻击者不在防护范围内，
  本包不宣称不可篡改审计或完整密码学认证。
- 源文件（01_源文件/**）只读未改：23 项 SHA256 与源包 `manifest.json` 一致（见 `04_继承与改动.csv` CHG-06）。
- 交付为候选状态，需 DeepSeek 独立审核、Codex 登记验收后方可进入共同基线；未通过不得称已上线。
