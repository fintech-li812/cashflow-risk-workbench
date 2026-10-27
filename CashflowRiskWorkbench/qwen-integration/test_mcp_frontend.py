# -*- coding: utf-8 -*-
"""千问办公 MCP Server 自检（单进程内驱动，不额外拉起子进程）。

覆盖：
  · stdio 协议栈：initialize / tools/list / tools/call
  · 前端指令统一入口 frontend.dispatch 的正常、参数错误、未知 action
  · 两个独立工具
  · HTTP 传输与鉴权（127.0.0.1 随机端口，线程内起停）

运行：python test_mcp_frontend.py
"""
import io
import json
import os
import sys
import threading
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mcp_frontend_server as S  # noqa: E402

fails = []


def check(name, cond, got=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else "  -> %s" % (got,)))
    if not cond:
        fails.append(name)


# ---------------------------------------------------------------------------
# 一、stdio 协议栈：把标准输入输出替换成内存缓冲后直接跑 serve_stdio()
# ---------------------------------------------------------------------------
REQ = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
        "name": "frontend.dispatch",
        "arguments": {"action": "risk.assess",
                      "params": {"lamp": "红灯", "industry": "制造业", "amount": 300000},
                      "request_id": "req-front-001", "session_id": "s-1", "actor": "张伟"}}},
    {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
        "name": "frontend.dispatch",
        "arguments": {"action": "risk.assess", "params": {"lamp": "紫色", "amount": -5}}}},
    {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {
        "name": "frontend.dispatch", "arguments": {"action": "no.such"}}},
    {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {
        "name": "frontend.dispatch", "arguments": {"action": "echo", "params": {}}}},
    {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {
        "name": "frontend.dispatch", "arguments": {"action": "echo", "params": {"text": "hi"}}}},
    {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {
        "name": "workbench.ledger_query", "arguments": {"risk_level": "HIGH"}}},
    {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {
        "name": "workbench.risk_assess", "arguments": {"score": 85}}},
    {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {
        "name": "not.exist", "arguments": {}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
]
stdin_buf = io.StringIO("".join(json.dumps(m, ensure_ascii=False) + "\n" for m in REQ))
stdout_buf = io.StringIO()
old_in, old_out = sys.stdin, sys.stdout
sys.stdin, sys.stdout = stdin_buf, stdout_buf
try:
    S.serve_stdio()
finally:
    sys.stdin, sys.stdout = old_in, old_out

lines = [l for l in stdout_buf.getvalue().splitlines() if l.strip()]
resps = {}
for l in lines:
    o = json.loads(l)
    if o.get("id") is not None:
        resps[o["id"]] = o

print("=== stdio 协议栈（%d 条响应）===" % len(resps))
r1 = resps[1]["result"]
check("initialize 返回 serverInfo", r1["serverInfo"]["name"] == "cashflow-workbench-frontend", r1)
print("       ", r1["serverInfo"], "|", r1["protocolVersion"])

names = [t["name"] for t in resps[2]["result"]["tools"]]
check("tools/list 至少 3 个工具", len(names) >= 3, names)
print("       ", names)

d3 = resps[3]["result"]["structuredContent"]
check("ok=True code=0", d3["ok"] and d3["code"] == 0, d3)
check("红灯 → HIGH", d3["data"]["risk_level"] == "HIGH", d3["data"])
check("负责人 财务总监-张伟", d3["data"]["owner"] == "财务总监-张伟", d3["data"])
check("30万 → 双签", d3["data"]["approval"] == "双签", d3["data"])
check("request_id 回显", d3["meta"]["request_id"] == "req-front-001", d3["meta"])
print("       ", d3["data"]["risk_level"], d3["data"]["lamp"], d3["data"]["owner"],
      "| 替补:", d3["data"]["deputy"], "| 审批:", d3["data"]["approval"],
      "| 耗时 %sms" % d3["meta"]["elapsed_ms"])

d4 = resps[4]["result"]["structuredContent"]
check("非法枚举/负数 → 4001", (not d4["ok"]) and d4["code"] == 4001, d4)
print("       ", d4["error"]["code"], "|", d4["error"]["message"])

d5 = resps[5]["result"]["structuredContent"]
check("未知 action → 4002", (not d5["ok"]) and d5["code"] == 4002, d5)
print("       ", d5["error"]["message"], "| 允许:", d5["error"]["detail"]["allowed"])

d6 = resps[6]["result"]["structuredContent"]
check("缺必填 text → 4001", (not d6["ok"]) and d6["code"] == 4001, d6)
print("       ", d6["error"]["message"])

d7 = resps[7]["result"]["structuredContent"]
check("echo 正常返回", d7["ok"] and d7["data"]["echo"] == "hi", d7)

d8 = resps[8]["result"]["structuredContent"]
check("ledger_query 命中高风险", d8["total"] >= 1, d8)
print("       total =", d8["total"], [i["matter_id"] for i in d8["items"]])

d9 = resps[9]["result"]["structuredContent"]
check("score=85 → HIGH", d9["risk_level"] == "HIGH", d9)
print("       ", d9["risk_level"], d9["lamp"], d9["owner"], "sla", d9["sla_hours"], "h")

check("未知工具 → JSON-RPC error", "error" in resps[10], resps[10])
print("       ", resps[10].get("error"))

check("notifications 无响应（不污染通道）", 11 not in resps and len(resps) == 10, len(resps))

# ---------------------------------------------------------------------------
# 二、HTTP 传输与鉴权
# ---------------------------------------------------------------------------
print()
print("=== HTTP 传输与鉴权 ===")
S._Handler.TOKEN = "tk-demo"
srv = S.ThreadingHTTPServer(("127.0.0.1", 0), S._Handler)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d" % port


def post(payload, token=None):
    req = urllib.request.Request(BASE + "/mcp", data=json.dumps(payload).encode("utf-8"),
                                 method="POST", headers={"Content-Type": "application/json"})
    if token:
        req.add_header("X-MCP-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode("utf-8")[:200]}


no_tok = post({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
check("无 token → 401", no_tok.get("http_error") == 401, no_tok)
bad_tok = post({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, "wrong")
check("错 token → 401", bad_tok.get("http_error") == 401, bad_tok)
ok_tok = post({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, "tk-demo")
check("正确 token → 200 返回工具清单", "result" in ok_tok, ok_tok)
with urllib.request.urlopen(BASE + "/health", timeout=10) as r:
    health = json.load(r)
check("/health 正常", health.get("ok") is True, health)
print("        tools:", health.get("tools"))
h = post({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
    "name": "frontend.dispatch",
    "arguments": {"action": "ledger.query", "params": {"state": "PENDING_CONFIRM"}}}}, "tk-demo")
check("HTTP 下 dispatch 可用", h["result"]["structuredContent"]["ok"], h)
srv.shutdown()

print()
print("结果：%s" % ("全部通过" if not fails else "失败 %d 项：%s" % (len(fails), fails)))
sys.exit(1 if fails else 0)
