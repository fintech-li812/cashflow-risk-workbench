# 首次MCP探测阻断

实际初始化和tools/list成功，get_workbench_status正常返回，但真实数据库状态不是connected，探测在断言`status['components']['database']=='connected' and status['result_profile']['fixture']`处失败并非0退出。随后只读检查确认本机13317、18765都无监听，未重复密集执行。

保留首次stderr于MCP只读探测_stderr.txt。只恢复本轮已有授权的隔离SSH隧道，不建库、不改权限、不写业务数据；复测另记恢复后日志。这个失败不计为通过，未将诊断改成固定connected。
