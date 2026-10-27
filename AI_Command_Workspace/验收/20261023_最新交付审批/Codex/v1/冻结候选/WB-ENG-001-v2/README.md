# WB-ENG-001 · 统一数据库与工具契约（WorkBuddy v1）

- 任务编号：WB-ENG-001（总队列 WB-ENG v1 第 1 包）
- 作者：WorkBuddy（本机 33847）
- 版本：v1（首版交付）
- 日期：2026-10-22
- 状态：**开发完成，暂停待审**。按 CMD-002 流程：Codex 冻结候选 → DeepSeek 独立审核（DS-AUD-001）→ Codex 确认后才可进 WB-ENG-002。

## 交付物清单

| 路径 | 说明 |
|---|---|
| `candidate/sql/init_v1.1.sql` | 数据库地基候选：11 表 + 10 视图，裸 CREATE + 结构预检，无 GRANT |
| `candidate/sql/grants_admin_view_候选.sql` | cf_admin 最小权限变更候选（CREATE VIEW/SHOW VIEW），**未批准、未执行** |
| `candidate/docs/千问办公_MySQL_MCP工具定义_v1.1.json` | 14 工具完整输入 Schema |
| `candidate/docs/千问办公_MySQL_MCP对接协议_v1.1.md` | 协议文档候选（变更点以【v1.1】标注） |
| `tools/validate_contract.py` | 自动校验脚本（A JSON 静态 / B Schema 正反例 / C DDL 静态 / D BLOCKED 声明） |
| `tools/requirements.txt` | 隔离依赖精确版本 |
| `test-output/validate_output.txt` | 校验脚本实际运行输出（69 项） |
| `改动清单.md` | v1.0→v1.1 逐项变更与裁决落点 |
| `测试报告.md` | PASS/FAIL/SKIP/BLOCKED 分明 + 复现命令 |
| `未决项.md` | 未批准业务项与部署阻塞（U-01 等） |
| `SHA256SUMS.txt` | 候选文件哈希清单（供审核冻结比对） |

## 运行环境（实测）

- OS：Windows 10/11 本机（开发/测试均在本机交付目录内完成）
- Python：`C:\Users\33847\.workbuddy\binaries\python\versions\3.13.12\python.exe`（**R-12 修正**：目录名带 3.13.12，实测解释器 `python -V` = **3.13.14**；以 `sys.version` 为准）
- 隔离 venv：`tools/venv/`（jsonschema 4.26.0 等 5 包，见 requirements.txt）
- 源项目 `D:\CashflowRiskWorkbench` 全程只读，未修改任何源文件
- 服务器（R-12：公网 IP 不在本包重复书写，参见 `交付\WB-SRV-001\WorkBuddy\v1\`）：本包未连接、未执行任何 DDL（纪律）

## 复现步骤

```bash
cd "D:\AI_Command_Workspace\交付\WB-ENG-001\WorkBuddy\v1"
# 首次：建隔离环境
"C:\Users\33847\.workbuddy\binaries\python\versions\3.13.12\python.exe" -m venv tools/venv
tools/venv/Scripts/python.exe -m pip install -r tools/requirements.txt
# 运行校验（输出同时落盘）
tools/venv/Scripts/python.exe tools/validate_contract.py 2>&1 | tee test-output/validate_output.txt
echo $?
```

期望：退出码 0；汇总 `PASS=66 FAIL=0 SKIP=1 BLOCKED=2 合计=69`。
BLOCKED 两项为真实 MySQL 执行（纪律禁止，留 WB-ENG-006）；SKIP 一项为
features/feature_names 等长（JSON Schema 无法表达，由 DB CHECK + 服务端兜底）。

## 有效需求与批准规则（本次遵循的裁决）

- `docs/规格裁决_20261021.md`：A1（14 工具）、A2.1（工具清单）、A2.2（24 event_type + 条件必填）、A2.3（11 表 + 公共列）、A5（scenario 5 值）
- `docs/规格裁决_20261022.md`：D8（库名/排序规则）、D9（采纳任务二三表结构）、D10（灯色英文四值）、D11（不设 4 个计算工具）、D12（金额元）、D13（删 30 维硬卡）、D21（UTC 默认表达式）
- `docs/外包交付/验收报告_任务一二三_v2.0.0.md`：第三节 5 处签名违规修复、第四节缺件
- 未决业务项（FUSE 分支/刚性支出/Myer/1.45/K 来源/M-S 冲突）未在本包定案，见 `未决项.md`
