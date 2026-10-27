# 文件说明：gen_input.py

- 仓库路径：finrisk_workbench_v7/src/gen_input.py
- 查看文件：[打开原文件](../finrisk_workbench_v7/src/gen_input.py)
- 归属：程序实现/启动或接口支持
- 大小：11491字节
- 导出SHA256：cfc820db707215737262e64778087454bff34b69642a5343ec2ad42a9a9e6770

## 内容与作用

模块说明：生成确定性合成输入台账（config.company.note 已声明为合成演示数据）。

random.seed 固定 -&gt; 重复运行产生完全相同的文件，可与 require_input_hash 对拍。
故意注入四类缺陷，供数据质量评分与&quot;判断受限&quot;分支真实触发：
缺关键字段 / 过期(record_date 超出 freshness_days) / 重复 collection_id / 未通过核验。

主要函数：\`gen_collections\`, \`gen_payments\`, \`gen_history\`, \`gen_accuracy\`, \`gen_credit\`, \`gen_change_requests\`, \`gen_overrides\`, \`main\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
