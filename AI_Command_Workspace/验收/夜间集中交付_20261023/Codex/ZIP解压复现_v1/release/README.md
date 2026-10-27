# CX-RELEASE-001｜只读发布前条件检查器（候选）

2026-10-23，作者Codex，标准库Python3.10+。用途是防止把候选文件或自报通过误认为已经能上线。不是部署脚本，不执行候选、不联网、不读口令、不写库。

```powershell
python test_preflight.py
python preflight.py --plan 当前项目发布计划_只读检查输入.json --project-root D:/CashflowRiskWorkbench --workspace-root D:/AI_Command_Workspace --output ../release-preflight-new
```
测试不依赖D盘或源项目；16项独立测试通过。可用MFG_PREFLIGHT_TEST_WORKDIR指定测试证据目录；不删除测试工件。第二条需要实际项目目录，缺目录/文件会如实失败，不是需要重试的未知故障。

实际项目只读检查：3项文件/候选内容核对通过、3个正式服务文件0字节失败、9项真实审核/平台/数据库/业务签收阻塞。exit1是预期的未具备发布条件，不是程序崩溃。新候选代码并未写入主项目，不能用本包把app.py空文件自动改成非空。
基础服务配置的历史完成记录继续有效，但没有恢复演练/真实千问与MySQL闭环的完成证据。此检查不重新SSH探测云端当前状态，不用本地文件推断服务器全部运行态。

任何declared_status=通过或manifest自报approved都不能自动授权；release_authorized始终false，最终仍由DeepSeek独审、X检查与Codex登记。工具可以指出哪些文件条件满足，不能认证人工签名或平台证据真实性。非空代码也不等于功能已实现。
schema=mfg-release-preflight.v1，target=qwen_office；artifacts中root为project/workspace、path为相对路径，kind=file/candidate_zip；候选ZIP另需task_id与可选固定sha256。ZIP仅读文件和manifest，不解包不执行。manual_gates九项缺任何项会自动补阻塞，不允许空列表“全绿”。
用户实际使用目录变化时新建计划，不改本快照当历史证据；候选ZIP版本变更必须用新摘要。报告包括preflight.json和发布前阻断清单.md。程序输出0条自动发布命令，真实部署另按审核后步骤执行。
