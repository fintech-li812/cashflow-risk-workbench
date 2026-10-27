# 文件说明：validate_contract.py

- 仓库路径：AI_Command_Workspace/发包/较简单与中等任务_20261023/MEM-CALC-001/v1/01_源文件/数据库契约原候选_v2/tools/validate_contract.py
- 查看文件：[打开原文件](../AI_Command_Workspace/%E5%8F%91%E5%8C%85/%E8%BE%83%E7%AE%80%E5%8D%95%E4%B8%8E%E4%B8%AD%E7%AD%89%E4%BB%BB%E5%8A%A1_20261023/MEM-CALC-001/v1/01_%E6%BA%90%E6%96%87%E4%BB%B6/%E6%95%B0%E6%8D%AE%E5%BA%93%E5%A5%91%E7%BA%A6%E5%8E%9F%E5%80%99%E9%80%89_v2/tools/validate_contract.py)
- 归属：任务说明/接续指令；文件存在不代表已执行
- 大小：34062字节
- 导出SHA256：89ee6aae4be816edf96ea833a7ab177521aeafab2c972115c1990c0a383343b9

## 内容与作用

模块说明：WB-ENG-001 契约自动校验脚本
================================
校验对象（相对本脚本所在 v1/ 目录）：
  candidate/docs/千问办公_MySQL_MCP工具定义_v1.1.json
  candidate/sql/init_v1.1.sql

校验分四节：
  A. 工具 JSON 结构静态断言（14 工具集合 / 24 event_type / 4 risk_level /
     5 scenario / additionalProperties:false / 条件必填 / 验收报告 5 处违规修复）
  B. JSON Schema 正反例实测（jsonschema 4.26.0，真实 validate 调用）
  C. DDL 静态解析核对（表/视图/列/类型/约束与契约映射）
  D. 真实 MySQL 执行 → 恒 BLOCKED（WB-ENG-001 纪律：不在服务器执行 DDL；
     静态解析通过不等于

主要函数：\`report\`, \`section_a\`, \`section_b\`, \`strip_sql_comments\`, \`section_c\`, \`section_d\`, \`main\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
