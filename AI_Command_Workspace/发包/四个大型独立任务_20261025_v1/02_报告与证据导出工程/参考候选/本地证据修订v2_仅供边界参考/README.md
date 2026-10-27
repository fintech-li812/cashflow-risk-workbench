# MEM-EVIDENCE-001 Codex修订 v2

原28项矩阵本轮26通过、2未执行，整体退出10；额外8项独立检查通过。修复代码仍待独审，不部署。

本轮修订见审批修订说明.md；历史README_v1.md及既有交接CSV为继承资料，不能把历史v1自报当本轮成绩。
全部离线，不连数据库/千问、不监听端口、不替换现有MCP/MySQL。原始ZIP保留在收件箱。
Python本轮3.12.14，导入夹具依赖openpyxl 3.1.5；证据包标准库。测试预期未重写。
运行：
```text
python -B -m src.cli selftest --workdir <全新目录>
python -B tests/regression_review.py . <全新目录>
```
独立反例脚本输出JSON各case的passed；所有为true才通过。失败计数会在对应运行记录中保留。
导入verify留存临时重导目录以保护证据，不自动清理；测试替换夹具时将旧件改名保留。
不以本候选声称正式上线，仍缺原生表格和真实业务完整数据。
