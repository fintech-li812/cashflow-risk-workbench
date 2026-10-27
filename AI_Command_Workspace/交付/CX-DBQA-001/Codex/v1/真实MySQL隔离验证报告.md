# CX-DBQA-001 真实MySQL隔离验证报告
日期：2026-10-22（Asia/Shanghai）。执行者：Codex。

## 结论
WB-ENG-001 v1候选DDL可在服务器当前MySQL 8.0.46创建11张表及10个视图；15项实测14通过、1失败。
失败为R-04：两条已发布模板同一effective_from，后行supersedes前行，v_template_published_latest返回2行，预期仅最新有效1行。确认DeepSeek独立审核该问题成立，不能将此候选投入业务使用。
本轮是隔离验证，不是正式部署，也不是千问端到端测试。

## 固定输入与范围
完整候选文件清单逐项SHA256核对一致。SQL哈希：c588fedfcf6ebc2e13c2f6c2190ce965c78bcad0cb099992c9af541fde45802e。
使用数据库cfqa_20261022_125214，只将原脚本cf_workbench引用替换为隔离库名，未改候选表/视图/约束。原文件未修改。
服务器隔离脚本与日志目录：/var/tmp/cfqa_20261022_125214。
测试数据全部为synthetic-test，交易测试在事务中运行并ROLLBACK；失败连接关闭后事务自动回滚。实测所有测试表行数均0。
测试数据库与1个额外候选修复视图暂留供复验，不删除任何库或原始文件。未新增账号授权、未改全局参数或服务。
正式cf_workbench与new_project前后对象列表一致且均为空。

## 15项验证
1. 11表10视图：通过。
2. 会话+08时created_at仍取UTC：通过。
3. 风险事件缺rule/version/level：CHECK拒绝，符合预期。
4. 非法event_type：CHECK拒绝，符合预期。
5. 非法风险枚举：CHECK拒绝，符合预期。
6. 同tenant重复request_id：唯一约束拒绝，符合预期。
7. 不同tenant同request_id：允许，符合预期。
8. 128字符request_id：允许，符合预期。
9. 129字符request_id：拒绝，符合预期。
10. 同租户追加纠错视图排除原行：通过。
11. 跨租户supersedes指针不能隐藏原租户行：视图通过（不代表应用允许该指针，服务端仍需拒绝越权引用）。
12. 非法ledger哈希：CHECK拒绝，符合预期。
13. pending反馈actual_value=NULL且predicted_value=0.30：DB允许，证实R-01为Schema/DB契约冲突。
14. audit_id='A-demo-001'：BIGINT拒绝，证实R-02的接口示例无法入库。
15. 已替代模板同生效时间：失败，实际2行，预期1行。
各项实际返回码和原文见真实MySQL验证.json。负例预期报错不是操作重试，未循环重复写入。

## R-04修复建议的额外验证
仅在隔离库新增v_template_latest_proposed，原候选视图保留以便对照。
建议语义：只看当前已生效published行；仅同tenant同industry的已生效published后继能替代原行；候选按effective_from降序、id降序选一行。
4场景均通过：替代后返回replacement；同时间未关联替代的并列版本返回second；未来后继不提前生效；草稿后继不使已发布版失效。最终测试行数0。
该查询是待独立复核候选，未替换源项目或正式库。实现与最终规则确认后由作者合入新版本。

## 未覆盖
未以cf_admin执行隔离DDL，未验证其CREATE DATABASE/CREATE VIEW权限；未测MCP事务代码、鉴权、并发服务、真实模型及千问平台。DDL和事务单独通过不证明应用幂等实现正确。R-03/R-05及company_id/账本例外仍需契约裁决。
