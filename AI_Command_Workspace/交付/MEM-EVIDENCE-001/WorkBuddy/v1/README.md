# MEM-EVIDENCE-001｜可靠结果存储与故障恢复（候选 v1）

执行人/AI：WorkBuddy（服务器侧执行者，登记见 项目登记/WorkBuddy_服务器侧执行者_33847_登记_v1.md）
开工依据：用户（最终决策人）2026-10-24 口头直接指派"从最难的、能独立完成的任务开始做"；按共享区规则"指令冲突以用户最新明确指令优先"。看板正式登记与 Codex 接单流转**待 X 转达补充**，本候选不视为已接单验收。
状态：**candidate（候选），待 DeepSeek 独立审核、Codex 登记验收、X 最终检查。不是生产组件，未连接任何服务器/生产库/千问平台。**

## 这是什么

本地 SQLite 事务证据存储模块 + CLI，实现 mfg-evidence.v1 回执语义：幂等保存、精确回查、历史追加、篡改复核、受控故障恢复。解决"算过却不知道是哪版数据、超时重试写两遍、被覆盖后无法追溯"。

**不是** MySQL 服务、不是 MCP 工具、不做现金流计算（主算法由 X 另指派的队友负责）。

## 一键自证（新环境照抄即可）

在本目录（v1/）执行，仅需 Python 3.10+ 标准库，无第三方依赖：

```
python src/evidence_cli.py selftest --workdir test-output/selftest_你自己起个新目录名
```

期望：stdout 输出 `"selftest": "PASSED"`，退出码 0；任一检查失败则退出码非 0。
注意 `--workdir` 必须是**全新空目录**（不存在或为空），非空目录会被拒绝。

## 完整测试矩阵

```
python tests/run_tests.py
```

实测（2026-10-24，CPython 3.13.12，Windows）：**30 项：PASS 30 / FAIL 0 / BLOCKED 0 / 未执行 0**，退出码 0。逐用例证据（命令/stdout/stderr/退出码）落盘 `test-output/run_20261024_191750/`。

诚实记录（不掩盖过程）：
- 第 1 轮 run_20261024_191459：TC-13 处 runner 自身目录未建崩溃（中断于 13 项，前 13 项全 PASS）。
- 第 2 轮 run_20261024_191535：26 PASS / 4 FAIL。FAIL 根因：负例夹具改金额时未同步 actual_closing 导致勾稽先拒绝（TC-13/TC-17b/selftest 第4项），并发子进程存在建库竞争（TC-17a）。
- 第 3 轮（本轮证据）：修复夹具勾稽与竞争测试预建库后 30/30 PASS。
三轮输出全部保留在 test-output/，可复核演进过程。

## CLI 用法与示例

```bash
# 保存（fixture 必须显式 --allow-fixture，否则拒绝）
python src/evidence_cli.py save --input fixtures/result_success_fixture.json \
  --context fixtures/context_trusted.json --request-id demo-001 \
  --store test-output/selftest_xxx/selftest.db --allow-fixture
# -> {"status":"committed","receipt":{...,"status":"committed",...}} 退出码 0

# 精确回查（限同身份；不存在与跨身份统一 not_found，不泄露别家记录）
python src/evidence_cli.py get --tenant-id fixture-tenant --company-id fixture-company \
  --record-id ev-78f10ce9748f620073921054 --store test-output/selftest_xxx/selftest.db

# 历史与当前有效（同主体同期间，stored_at 最新，绝不跨主体 MAX(id)）
python src/evidence_cli.py history --tenant-id fixture-tenant \
  --company-id fixture-company --period 2026-08 --store test-output/selftest_xxx/selftest.db

# 篡改复核（检出返回退出码 6）
python src/evidence_cli.py verify-store --store test-output/selftest_xxx/selftest.db
```

## 目录说明

| 路径 | 内容 |
|---|---|
| src/evidence_store.py | 核心库：校验、SQLite 事务、幂等、回执、verify |
| src/evidence_cli.py | CLI 五个子命令 + selftest |
| fixtures/ | 全部合成夹具（origin=offline_fixture；qwen_labeled 仅验证代码路径，标签≠平台证据） |
| expected/cli_cases_expected.json | 冻结独立预期（运行前后核 SHA256，禁止运行期改写） |
| tests/run_tests.py | 30 用例矩阵 runner，全部子进程真实调用 CLI |
| test-output/ | 三轮实测证据（含失败轮，如实保留） |
| 设计与接口说明.md / 错误码说明.md / trust_boundary.md / 未实现与待确认.md | 文档 |
| 01_需求与实现映射.csv … 04_继承与改动.csv | 交接清单（模板列头未删列） |
| manifest.json / SHA256SUMS.txt | 交付清单与哈希 |

## 明确未做（边界）

- 未连接服务器/MySQL/千问平台，未部署任何东西；record_id 是本地存储 ID，不是 MySQL 主键。
- 未实现生产认证：可信 context 是测试信任入口（见 trust_boundary.md）。
- 未做财务计算；金额勾稽只做格式与一致性校验。
- 未做承诺的"不可篡改审计"——普通哈希的检测边界如实写在 trust_boundary.md。
- 平台（千问）保存/回查闭环：阻塞，待 MEM-EVIDENCE-001 候选审核通过且另发部署任务。
