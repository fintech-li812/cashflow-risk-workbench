# Cashflow Risk Workbench 项目归档

D盘财务现金流Workbench的独立归档仓库，导出日期2026-10-27。公开可见。保留原目录结构、实现、任务/交付/验收、历史资料，并为每个源文件提供一份独立README。

## 从哪里开始

- [主工作台README](CashflowRiskWorkbench/README.md)
- [给Web助手与WorkBuddy的完整交接](CashflowRiskWorkbench/%E4%BA%A4%E6%8E%A5%E7%BB%99WorkBuddy%E4%B8%8EWeb%E5%8A%A9%E6%89%8B_%E5%BD%93%E5%89%8D%E5%85%A8%E8%B2%8C_20261027.md)
- [逐文件说明总索引](FILE_INDEX.md)
- [共享任务看板](AI_Command_Workspace/%E4%BB%BB%E5%8A%A1%E7%9C%8B%E6%9D%BF.md)
- [纳入文件与摘要](EXPORT_MANIFEST.json)
- [脱敏与排除记录](EXPORT_EXCLUSIONS.json)

## 仓库结构

| 目录 | 内容 |
|---|---|
| CashflowRiskWorkbench/ | 当前主工作台、前端、Python计算/MCP、合成数据、最新交接；含迁移/移动端候选 |
| AI_Command_Workspace/ | 团队规则、任务、源码候选、交付、审查及测试证据 |
| finrisk_workbench/ | 历史财务目录，原样保留，不作为当前入口 |
| finrisk_workbench_v7/ | 旧版历史资料，原样保留 |
| D_drive_support/ | D盘相关启动配置与辅助文件 |
| file-readmes/ | 每个源文件独立说明，含未上传原件的原因 |
| file-index/ | 分页索引，避免大README无法正常浏览 |

## 当前事实边界

归档中有完整合成八表程序版v1.2及原目录100项测试记录：期初100000、流入185000、流出108000、净额77000、期末177000、差异0。它是SYNTHETIC工程演示，不是真实企业风险准确率；本次GitHub归档未重新运行所有程序，也不证明后来新增的Node迁移/移动端候选已完成。
公开Workbench网站、云端API、网页AI工作流和跨设备完整验收在本次交接时尚未完成。用户已将策划转交Web助手、实施交WorkBuddy；独立后台v3方案仍是候选，不视为最终批准。
C盘独立cashflow_project 0.2.0模型资产不在本次D盘归档范围；my_agent和其他无关D盘项目未纳入。

## 如何使用

这是来源可追踪的归档，不是一个已发布云应用。主程序位于CashflowRiskWorkbench/mcp-server/program_v1；原运行配置固定在D盘，并依赖本机受控来源与隔离数据库。克隆到其他路径/机器时，先读对应文件说明，按实际环境配置路径、依赖、数据库及认证；不要批量执行历史任务包或使用root/QA入口做公网服务。
Python依赖声明、Node候选和历史执行命令保留在各自目录。归档不包含虚拟环境、node_modules、缓存或凭据，不在README中提供密码或私钥。

## 文件覆盖、脱敏与限制

- 纳入源文件：8271个，逐文件说明：8344份（含排除记录）。
- 原件排除：73个，其中72个数据库二进制、1个含口令文本的旧ZIP；对应展开旧文档的导出副本已脱敏。
- 仅2份旧方案文本在导出副本中脱敏；原D盘文件未修改。
- 环境/缓存等目录排除18个，清单见EXPORT_EXCLUSIONS.json；运行环境应按锁定依赖重建。
- 每个纳入源文件都能在EXPORT_MANIFEST.json找到SHA256与独立README；生成的README/索引不再递归生成新的README。
- .gitattributes禁止换行转换，尽量保留复制字节。文件中的旧SHA/清单描述的是历史工件，脱敏副本不冒充旧工件原字节。
- 静态敏感信息检查不构成绝对无泄露保证；发现问题应修订公开副本并按实际情况处理。没有自动授予仓库代码的开源许可证。

## 维护约定

原项目来源及运行态保留在D盘，本仓库首次是独立归档。不要把同名历史文件误认当前版本；读最新交接后再开工。
