# WB-AGENT-003 · 制造业 Agent 接入工程（WorkBuddy v1）

任务入口：`D:\AI_Command_Workspace\333.md`（对应指令 `指令/WB-AGENT-003_制造业Agent接入工程_v1.md`）
范围依据：`规则/制造业现金流一期范围_v1.md`、`规则/制造业Agent周边工程统一接口_v1.md`
本包只做**非算法外围**的 Agent 接入骨架：选对企业与期间 → 读正确版本 → 取得计算结果或明确未就绪 → 解释 → 保存与回查。

---

## 一、状态（三项分开写，不合并）

| 项 | 结果 |
|---|---|
| **离线通过** | 44 项自测全部通过，退出码 0（`test-output/selftest_v1.txt`）。其中 23 项继承自 CX-AGENT-002 基线，21 项为本包新增 |
| **真实平台执行** | **0 项**。千问读表、表格公式、MCP 工具、MySQL 回查**一次都没有执行** |
| **服务器部署** | **未做过**。未连接服务器、未改配置、未建生产表、未部署 |

综合状态：**离线准备完成，平台/部署阻塞**。不是“全链路已跑通”。

---

## 二、完成范围（对照 333.md A—F）

**A. 运行适配层** — `candidate/runtime_adapter.py`
定义 `read_snapshot` / `read_calculated_result` / `save_result` / `query_saved_result`
四类内部能力接口（不是对外 MCP 工具名）。未绑定时返回结构化 `unavailable`
并附缺项清单与人工取证步骤，**不伪造 API 或网页端点**；只能手动平台取数时写清导入证据流程。

**B. 请求流程** — `candidate/request_flow.py`
绑定可信 `tenant_id/company_id/period/source_revision/run_id`（不按文件名或公司名猜）；
记录 `source_revision`、`snapshot_ref`、`calculation_version`；
源数据变更后旧结果失效并重新取数（`test_04` 覆盖）；守卫检查金额/范围/非有限数/缺值。
结果校验**复用继承的 agent_guard**，不重复造规则。Agent 回答只用真实表格结果，不心算替代公式。

**C. 保存与回查** — `candidate/persistence.py`
按实际工具 `inputSchema` 逐字段映射（未取得 schema 即 unavailable，不预设字段名提交）；
`request_id` 为幂等键；超时为 `pending`（结果尚未确认），沿用同一 ID 回查，**禁止随机换 ID 重提**；
同 `request_id` 载荷不同报 `conflict` 且不覆盖；跨租户隔离；
无精确回查能力时明确阻塞并给出只读人工核对步骤。

**D. 最小配置** — `agent/制造业现金流主提示词_v3.txt`、`agent/八条制造业现金流追问_v3.md`、
`docs/X千问配置操作单.md`（字段表、必填配置名、按钮/配置动作、成功证据；不填密码、不用 root、
不让千问伙伴承担普通开发）。

**E. 独立测试** — `run_tests.py`，44 项，失败退出码非 0。
覆盖：正常 / 缺输入 / 单位或金额错误 / 源版本过期 / 企业不匹配 / 部分数据 / 缺实际余额 /
算法未就绪 / 保存前失败 / 提交后超时与重试 / 回查错误，另加六项打回红线专项。
生产**不能**自动回退 fixture（`test_fixture_never_leaks_to_production` 断言）。

**F. 三队友衔接** — `docs/接口映射.md`。使用本包自己的明确标识合成夹具，不等他人完成；
队友正式包到货后只需实现 `Backend` 四方法或替换 `MemoryEvidenceStore`，`RequestFlow` 不需改动。

---

## 三、目录

```
v1/
  README.md                        本文件
  run_tests.py                     自测入口
  requirements.lock.txt            锁定依赖（仅标准库）
  config.example.json              配置示例（仅名称，无凭据）
  candidate/
    agent_guard.py                 继承 CX-AGENT-002，未修改
    runtime_adapter.py             A 项
    request_flow.py                B 项
    persistence.py                 C 项
    adapters.py                    后端组合
  fixtures/synthetic_success.json  继承，未修改
  agent/
    制造业现金流主提示词_v3.txt      D 项
    八条制造业现金流追问_v3.md       D 项
    *_v2_继承原文.*                 继承原文，保留对照
  docs/
    X千问配置操作单.md              D 项
    接口映射.md                     F 项
    未实现清单.md
    来源继承与差异说明.md
  tests/
    test_inherited_guard.py        继承基线 23 项
    test_flow_and_persistence.py   本包新增 21 项
  test-output/selftest_v1.txt      实际运行输出
  SHA256SUMS.txt
```

## 四、复现命令

在包根目录执行（Python 3.10+，无需网络/数据库/服务器）：

```
python run_tests.py
```

期望：`Ran 44 tests ... OK`，`ran=44 failures=0 errors=0 skipped=0`，退出码 0。

## 五、限制（必须连同交付一起阅读）

- 44 项自测是**离线合成夹具**结果，不等于千问平台已通过、不等于 MCP 已部署、不等于 MySQL 已入库
- `MemoryEvidenceStore` 是进程内字典，不是数据库；`record_id` 是本地 ID，不是 MySQL 主键
- 校验器不能证明调用者身份、平台来源或数据完整性；`snapshot_ref` / `origin` 字符串本身不是安全证据
- 生产禁止 `offline_fixture`；夹具仅在显式测试模式可用并带合成标记
- 本包无算法，不计算金额；金额一律来自已绑定表格公式

## 六、待裁决 / 阻塞

见 `docs/未实现清单.md` 第四节：真实回查能力、经营部分视图归属、`record_id` 规则、
超时等待时长上限。U1—U9 全部阻塞在平台侧或队友包，需 X 或 Codex 安排。
