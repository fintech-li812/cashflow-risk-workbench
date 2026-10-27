# 文件说明：common.py

- 仓库路径：finrisk_workbench_v7/src/common.py
- 查看文件：[打开原文件](../finrisk_workbench_v7/src/common.py)
- 归属：程序实现/启动或接口支持
- 大小：9868字节
- 导出SHA256：a02a399149ae00795e9a5c65b2fdbb870cc9449a9c5a5e78db2e507739867696

## 内容与作用

模块说明：公共层：配置装载、结果口径、输入哈希、日志、审计落库。

对齐 config.json 的两条硬性约束：
- reproducibility.require_input_hash=true  -&gt; 缺输入哈希清单一律拒绝跑
- reproducibility.result_round_decimals=4  -&gt; 所有对外结果统一 4 位小数

主要函数：\`load_config\`, \`load_templates\`, \`set_precision\`, \`r\`, \`rmap\`, \`parse_date\`, \`week_start\`, \`sha256_file\`, \`canonical_hash\`, \`build_input_manifest\`, \`load_csv\`, \`get_logger\`, \`write_json\`, \`write_csv\`

主要类：\`Audit\`

## 打开与使用

代码编辑器；运行依赖与命令以所属工程README为准。

## 状态与限制

这是2026-10-27归档时的静态说明，不证明本文件已执行、已部署或业务验证通过。优先阅读仓库根README和主工作台最新交接；历史文件口径可能已被用户后续决定覆盖。
