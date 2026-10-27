"""WB-AGENT-003 候选代码包：制造业 Agent 接入工程（非算法外围）。

模块分工：
  agent_guard.py     继承 CX-AGENT-002（未修改冻结内容）：结果校验与渲染
  runtime_adapter.py A 项：四类内部能力接口 + 结构化 unavailable
  request_flow.py    B 项：可信绑定、源版本失效重取、守卫
  persistence.py     C 项：逐字段映射、幂等、回执、精确回查、超时不确定态
  adapters.py        后端组合（含仅测试可用的离线夹具后端）

本包不含算法、不连接服务器、不读写生产库、不部署。
"""
__all__ = ["agent_guard", "runtime_adapter", "request_flow", "persistence", "adapters"]
