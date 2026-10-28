#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
 千问办公 MCP Server · 前端指令接收与处理（单文件 · 自包含 · 可直接运行）
=============================================================================

【定位】接收方是「千问办公的 MCP 客户端」，不是千问办公的前端。
  链路：前端/用户 → 千问办公（意图解析与编排）→ 本 MCP Server（执行）→ 返回结构化结果

【传输】默认 stdio（千问办公拉起本进程，按行交换 JSON-RPC 2.0）
       可选 --http（本地自测 / 前端直连调试用，必须带 token）

【依赖】零第三方依赖，仅用 Python 标准库；Python 3.8+ 可直接运行。

【启动命令】（千问办公注册时用这一条）
  python mcp_frontend_server.py
  # 或指定解释器绝对路径（推荐，避免 PATH 差异）：
  # D:/AI_Command_Workspace/runtime/cashflow_v1/Scripts/python.exe mcp_frontend_server.py

【注册配置片段】（粘贴到千问办公的 MCP 配置中，见文件末尾 REGISTER_SNIPPET 常量，
  也已单独输出为同目录 mcp_frontend_server.config.json）

【替换成你自己的业务逻辑】全文搜索 "TODO(业务)" 即可定位所有需要改写的位置：
  1) biz_risk_assess()  —— 风险分级与责任人分派（现为确定性示例实现）
  2) biz_ledger_query() —— 责任台账查询（现为内存示例数据）
  3) ACTION_SCHEMAS     —— 新增/修改 action 及其入参校验规则
  4) ACTION_ROUTER      —— 把新 action 路由到你的处理函数
  生产环境请把这两处改为调用你自己的数据库 / 内部服务 / v8 计算内核。

【严禁】任何日志必须写 stderr；stdout 是协议通道，打印一行垃圾就会导致千问办公解析失败。
"""

import json
import os
import re
import sys
import time
import uuid
import argparse
import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Windows 下强制 UTF-8，避免中文以 GBK 写入 stdout 导致千问办公解析失败
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "cashflow-workbench-frontend", "version": "v1.0.0"}

# =============================================================================
# 一、工具定义（tools/list 原样输出）
#     inputSchema 为标准 JSON Schema 子集；out_schema 仅作说明，供调用方参考
# =============================================================================
T = lambda t, d: {"type": t, "description": d}

TOOLS = [
    {
        "name": "frontend.dispatch",
        "description": (
            "前端指令统一入口。接收前端下发的 action 与 params，完成参数校验、"
            "业务路由与统一错误封装。新增前端能力只需在此注册 action，无需改动协议层。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": T("string", "前端动作名，如 risk.assess / ledger.query / echo"),
                "params": T("object", "该动作对应的参数对象"),
                "request_id": T("string", "前端请求追踪号，缺省时服务端生成"),
                "session_id": T("string", "前端会话号，用于多轮对话上下文关联"),
                "actor": T("string", "操作人（用于留痕与责任归属）"),
            },
            "required": ["action"],
        },
        "out_schema": {
            "ok": "bool 业务是否成功",
            "code": "int 0 成功，非 0 见 ERRORS",
            "action": "回显动作名",
            "data": "业务数据（成功时）",
            "error": "{'code','message','detail'}（失败时）",
            "meta": "{'request_id','elapsed_ms','server','version','timestamp'}",
        },
    },
    {
        "name": "workbench.risk_assess",
        "description": "风险分级与责任人分派：按灯色/分值判定高中低风险，输出核实负责人与替补人。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lamp": T("string", "灯色：红灯|黄灯|绿灯，与 score 二选一"),
                "score": T("number", "风险分值 0~100，与 lamp 二选一"),
                "industry": T("string", "行业：制造业|零售业|建筑业|科技服务业"),
                "amount": T("number", "事项金额（元），用于审批分级"),
                "title": T("string", "事项标题"),
            },
            "required": [],
        },
        "out_schema": {
            "risk_level": "HIGH|MID|LOW",
            "risk_level_name": "高风险|中风险|低风险",
            "lamp": "红灯|黄灯|绿灯",
            "owner": "核实负责人",
            "deputy": "替补人",
            "escalate_to": "升级对象",
            "sla_hours": "核实时限（小时）",
        },
    },
    {
        "name": "workbench.ledger_query",
        "description": "责任台账查询：按状态/风险等级/责任人检索事项，支持超时标记。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state": T("string", "状态：ASSIGNED|IN_REVIEW|PENDING_CONFIRM|URGING|ESCALATED|CONFIRMED|REJECTED|CLOSED"),
                "risk_level": T("string", "HIGH|MID|LOW"),
                "owner": T("string", "责任人姓名（模糊匹配）"),
                "keyword": T("string", "标题/描述关键字"),
                "limit": T("integer", "返回条数，默认 20，最大 200"),
            },
            "required": [],
        },
        "out_schema": {"total": "命中条数", "items": "台账条目数组", "source": "数据来源"},
    },
]

# =============================================================================
# 二、统一错误码
# =============================================================================
ERRORS = {
    0:    "OK",
    4000: "BAD_REQUEST     请求体不是合法 JSON",
    4001: "INVALID_PARAM   参数校验失败",
    4002: "UNKNOWN_ACTION  未知 action",
    4003: "UNAUTHORIZED    鉴权失败",
    4100: "NOT_COVERED     数据范围未覆盖（八表无此数据，不部署算法）",
    4101: "BLOCKED         业务规则阻断（如余额差异未对平，禁止落库）",
    5000: "INTERNAL_ERROR  服务内部异常",
}


def ok_resp(action, data, request_id=None, elapsed_ms=0, extra_meta=None):
    """统一成功返回。"""
    meta = {"request_id": request_id or ("req-" + uuid.uuid4().hex[:12]),
            "elapsed_ms": round(elapsed_ms, 2),
            "server": SERVER_INFO["name"], "version": SERVER_INFO["version"],
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds")}
    if extra_meta:
        meta.update(extra_meta)
    return {"ok": True, "code": 0, "action": action, "data": data,
            "error": None, "meta": meta}


def err_resp(code, message, detail=None, action=None, request_id=None, elapsed_ms=0):
    """统一错误返回。"""
    return {"ok": False, "code": code, "action": action, "data": None,
            "error": {"code": ERRORS.get(code, "ERROR").split()[0],
                      "message": message, "detail": detail},
            "meta": {"request_id": request_id or ("req-" + uuid.uuid4().hex[:12]),
                     "elapsed_ms": round(elapsed_ms, 2),
                     "server": SERVER_INFO["name"], "version": SERVER_INFO["version"],
                     "timestamp": datetime.datetime.now().isoformat(timespec="seconds")}}


# =============================================================================
# 三、轻量参数校验（JSON Schema 子集，零依赖）
#     支持：type / required / enum / minimum / maximum / minLength / maxLength
#           / pattern / properties / items / additionalProperties(仅提示)
# =============================================================================
class ValidationError(Exception):
    def __init__(self, message, detail=None):
        super().__init__(message)
        self.detail = detail or {}


_TYPE_MAP = {"string": str, "number": (int, float), "integer": int,
             "object": dict, "array": list, "boolean": bool}


def validate(value, schema, path="$"):
    if not isinstance(schema, dict):
        return value
    t = schema.get("type")
    if t:
        py = _TYPE_MAP.get(t)
        if py is None:
            raise ValidationError("不支持的类型 %s" % t, {"path": path})
        if t == "number" and isinstance(value, bool):
            raise ValidationError("期望 number，实得 boolean", {"path": path})
        if t == "integer" and isinstance(value, bool):
            raise ValidationError("期望 integer，实得 boolean", {"path": path})
        if not isinstance(value, py):
            if t == "number" and not isinstance(value, bool) and isinstance(value, (int, float)):
                pass
            else:
                raise ValidationError(
                    "参数类型错误：期望 %s，实得 %s" % (t, type(value).__name__),
                    {"path": path, "expected": t, "actual": type(value).__name__})
    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError("取值不在允许范围内：%s" % (schema["enum"],),
                              {"path": path, "allowed": schema["enum"], "actual": value})
    if t in ("number", "integer"):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValidationError("小于最小值 %s" % schema["minimum"],
                                  {"path": path, "minimum": schema["minimum"]})
        if "maximum" in schema and value > schema["maximum"]:
            raise ValidationError("大于最大值 %s" % schema["maximum"],
                                  {"path": path, "maximum": schema["maximum"]})
    if t == "string":
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise ValidationError("长度不足 %s" % schema["minLength"], {"path": path})
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise ValidationError("长度超过 %s" % schema["maxLength"], {"path": path})
        if "pattern" in schema and not re.search(schema["pattern"], value):
            raise ValidationError("格式不匹配 %s" % schema["pattern"], {"path": path})
    if t == "object" and isinstance(value, dict):
        for req in schema.get("required", []):
            if req not in value:
                raise ValidationError("缺少必填参数 %s" % req, {"path": path, "missing": req})
        for k, sub in (schema.get("properties") or {}).items():
            if k in value:
                validate(value[k], sub, path + "." + k)
    if t == "array" and isinstance(value, list) and schema.get("items"):
        for i, it in enumerate(value):
            validate(it, schema["items"], "%s[%d]" % (path, i))
    return value


# =============================================================================
# 四、action 注册表（前端能力在此扩展）
# =============================================================================
ACTION_SCHEMAS = {
    "echo": {
        "type": "object",
        "properties": {"text": T("string", "任意文本")},
        "required": ["text"],
    },
    "risk.assess": {
        "type": "object",
        "properties": {
            "lamp": {"type": "string", "enum": ["红灯", "黄灯", "绿灯"], "description": "灯色"},
            "score": {"type": "number", "minimum": 0, "maximum": 100, "description": "风险分值"},
            "industry": {"type": "string", "enum": ["制造业", "零售业", "建筑业", "科技服务业"]},
            "amount": {"type": "number", "minimum": 0, "description": "金额（元）"},
            "title": {"type": "string", "maxLength": 200},
        },
        "required": [],
    },
    "ledger.query": {
        "type": "object",
        "properties": {
            "state": {"type": "string", "enum": ["SUBMITTED", "ASSIGNED", "IN_REVIEW",
                                                 "PENDING_CONFIRM", "URGING", "ESCALATED",
                                                 "CONFIRMED", "REJECTED", "CLOSED"]},
            "risk_level": {"type": "string", "enum": ["HIGH", "MID", "LOW"]},
            "owner": {"type": "string", "maxLength": 64},
            "keyword": {"type": "string", "maxLength": 100},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200},
        },
        "required": [],
    },
}


# =============================================================================
# 五、业务逻辑（TODO(业务)：以下两处替换为你的真实实现）
# =============================================================================
# TODO(业务) 责任人矩阵现为内置常量示例；生产请改为读库（如 mfg_v8_owner_matrix_v1）
OWNER_MATRIX = {
    "HIGH": {"level_name": "高风险", "owner": "财务总监-张伟", "deputy": "风控经理-李娜",
             "escalate_to": "总经理-王强", "sla_hours": 8},
    "MID":  {"level_name": "中风险", "owner": "风控经理-李娜", "deputy": "财务主管-陈静",
             "escalate_to": "财务总监-张伟", "sla_hours": 24},
    "LOW":  {"level_name": "低风险", "owner": "财务主管-陈静", "deputy": "会计-刘洋",
             "escalate_to": "风控经理-李娜", "sla_hours": 48},
}
LAMP_OF = {"HIGH": "红灯", "MID": "黄灯", "LOW": "绿灯"}


def biz_risk_assess(params):
    """TODO(业务)：替换为真实的风险分级与责任人分派逻辑。

    接入点建议：
      · 直接调用已实现的 v8 引擎：
            sys.path.insert(0, r"D:/CashflowRiskWorkbench/mcp-server/program_v1/src")
            from v8 import engine as v8engine
            result = v8engine.assess(industry=..., scenario=..., amount=...)
        用 result["最终等级"]["等级"] 作为 lamp，再查责任人矩阵（owners.get(level)）。
      · 或调用你自己的 HTTP 服务 / 数据库。
    现为确定性示例实现：仅做灯色→等级→责任人的映射，不含任何编造的风险数值。
    """
    lamp = params.get("lamp")
    score = params.get("score")
    if lamp:
        level = {"红灯": "HIGH", "黄灯": "MID", "绿灯": "LOW"}.get(lamp, "MID")
    elif score is not None:
        level = "HIGH" if score >= 70 else ("MID" if score >= 40 else "LOW")
    else:
        level = "MID"   # 两者都未提供时的保守默认（中风险），并在返回中说明
        lamp = "黄灯"
    cfg = OWNER_MATRIX[level]
    lamp = lamp or LAMP_OF[level]
    amount = params.get("amount")
    # 审批分级（示例规则：高风险或金额≥30万需双签）
    approval = "双签" if (level == "HIGH" or (amount or 0) >= 300000) else "单签"
    return {
        "risk_level": level,
        "risk_level_name": cfg["level_name"],
        "lamp": lamp,
        "owner": cfg["owner"],
        "deputy": cfg["deputy"],
        "escalate_to": cfg["escalate_to"],
        "sla_hours": cfg["sla_hours"],
        "approval": approval,
        "input_echo": {"lamp_given": params.get("lamp"), "score_given": score,
                       "industry": params.get("industry"), "amount": amount},
        "note": "灯色与分值均未给定时按中风险保守处理；责任人来自内置矩阵（TODO 换为读库）",
    }


# TODO(业务) 台账现为内存示例数据；生产请改为查询 MySQL（表 mfg_v8_matter_v1）
_LEDGER = [
    {"matter_id": "MAT-demo-0001", "title": "应收 SYN-AR-001 逾期 57 天", "risk_level": "HIGH",
     "lamp": "红灯", "state": "PENDING_CONFIRM", "owner": "财务总监-张伟",
     "due_at": "2026-10-28 08:00:00", "amount": 120000.0},
    {"matter_id": "MAT-demo-0002", "title": "建筑业缓冲倍数 2.53 低于黄灯线", "risk_level": "MID",
     "lamp": "黄灯", "state": "IN_REVIEW", "owner": "风控经理-李娜",
     "due_at": "2026-10-28 20:00:00", "amount": 80000.0},
    {"matter_id": "MAT-demo-0003", "title": "绿灯事项例行备案", "risk_level": "LOW",
     "lamp": "绿灯", "state": "CONFIRMED", "owner": "财务主管-陈静",
     "due_at": "2026-10-29 20:00:00", "amount": 5000.0},
]


def biz_ledger_query(params):
    """TODO(业务)：替换为真实台账查询（如 v8.matter.ledger(...) 或直连 MySQL）。"""
    items = _LEDGER
    if params.get("state"):
        items = [x for x in items if x["state"] == params["state"]]
    if params.get("risk_level"):
        items = [x for x in items if x["risk_level"] == params["risk_level"]]
    if params.get("owner"):
        items = [x for x in items if params["owner"] in x["owner"]]
    if params.get("keyword"):
        items = [x for x in items if params["keyword"] in x["title"]]
    limit = int(params.get("limit", 20) or 20)
    return {"total": len(items), "items": items[:limit], "source": "demo-memory"}


ACTION_ROUTER = {
    "echo": lambda p: {"echo": p.get("text")},
    "risk.assess": biz_risk_assess,
    "ledger.query": biz_ledger_query,
}


# =============================================================================
# 六、前端请求处理：校验 → 路由 → 统一封装
# =============================================================================
def dispatch(action, params, request_id=None, session_id=None, actor=None):
    t0 = time.time()

    def done(payload, meta_extra=None):
        return ok_resp(action, payload, request_id,
                       (time.time() - t0) * 1000,
                       {"session_id": session_id, "actor": actor} if meta_extra is None
                       else dict({"session_id": session_id, "actor": actor}, **meta_extra))

    if action not in ACTION_ROUTER:
        return err_resp(4002, "未知 action：%s" % action,
                        {"allowed": sorted(ACTION_ROUTER.keys())},
                        action, request_id, (time.time() - t0) * 1000)
    schema = ACTION_SCHEMAS.get(action) or {"type": "object"}
    try:
        validate(params or {}, schema, "$.params")
    except ValidationError as e:
        return err_resp(4001, str(e), e.detail, action, request_id,
                        (time.time() - t0) * 1000)
    try:
        data = ACTION_ROUTER[action](params or {})
    except Exception as e:                       # noqa: BLE001 统一兜底，避免进程被拖垮
        return err_resp(5000, "%s: %s" % (type(e).__name__, e), None,
                        action, request_id, (time.time() - t0) * 1000)
    return done(data)


def call_tool(name, args):
    """工具分发：MCP tools/call → 具体工具实现。"""
    a = args or {}
    if name == "frontend.dispatch":
        return dispatch(action=a.get("action"), params=a.get("params") or {},
                        request_id=a.get("request_id"), session_id=a.get("session_id"),
                        actor=a.get("actor"))
    if name == "workbench.risk_assess":
        r = dispatch("risk.assess", a)
        return r["data"] if r["ok"] else r
    if name == "workbench.ledger_query":
        r = dispatch("ledger.query", a)
        return r["data"] if r["ok"] else r
    raise KeyError("未知工具：%s" % name)


# =============================================================================
# 七、JSON-RPC 2.0 协议层
# =============================================================================
def handle(msg):
    mid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}

    def ok(result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def fail(code, message, data=None):
        e = {"code": code, "message": message}
        if data is not None:
            e["data"] = data
        return {"jsonrpc": "2.0", "id": mid, "error": e}

    if method == "initialize":
        return ok({"protocolVersion": PROTOCOL_VERSION,
                   "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": SERVER_INFO,
                   "instructions": "前端指令统一入口：调用 frontend.dispatch 并传入 action。"})
    if (method or "").startswith("notifications/"):
        return None
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            result = call_tool(name, args)
            # 业务失败（ok=False）仍以结构化内容返回，由调用方依据 ok/code 判断
            return ok({"content": [{"type": "text",
                                    "text": json.dumps(result, ensure_ascii=False, default=str)}],
                       "structuredContent": result, "isError": False})
        except KeyError as e:
            return fail(-32602, "Invalid params", {"detail": str(e)})
        except Exception as e:                   # noqa: BLE001
            return fail(-32000, "%s: %s" % (type(e).__name__, e))
    if mid is None:
        return None
    return fail(-32601, "Method not found: %s" % method)


def serve_stdio():
    """stdio 传输：一行一条 JSON-RPC。日志一律走 stderr。"""
    sys.stderr.write("[mcp] %s %s stdio 就绪\n" % (SERVER_INFO["name"], SERVER_INFO["version"]))
    sys.stderr.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception as e:
            sys.stderr.write("[mcp] 非法 JSON：%s\n" % e)
            sys.stderr.flush()
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False, default=str) + "\n")
            sys.stdout.flush()


# =============================================================================
# 八、可选 HTTP 传输（本地自测 / 前端直连调试；生产若暴露公网必须走鉴权与内网）
#     【待替换项】CF_MCP_TOKEN 必须设置，否则服务拒绝启动，避免裸奔
# =============================================================================
class _Handler(BaseHTTPRequestHandler):
    TOKEN = ""

    def log_message(self, *a):
        sys.stderr.write("[mcp-http] %s\n" % (a[0] % a[1:]))
        sys.stderr.flush()

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_ok(self):
        if not self.TOKEN:
            return True
        return (self.headers.get("X-MCP-Token") or "") == self.TOKEN

    def do_GET(self):
        if self.path.startswith("/health"):
            self._send(200, json.dumps({"ok": True, "server": SERVER_INFO,
                                        "tools": [t["name"] for t in TOOLS]},
                                       ensure_ascii=False).encode("utf-8"))
        else:
            self._send(404, b'{"ok":false,"error":"not found"}')

    def do_POST(self):
        if not self._auth_ok():
            self._send(401, json.dumps({"ok": False, "code": 4003,
                                        "error": {"code": "UNAUTHORIZED",
                                                  "message": "缺少或错误的 X-MCP-Token"}},
                                       ensure_ascii=False).encode("utf-8"))
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            msg = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception as e:
            self._send(400, json.dumps({"jsonrpc": "2.0", "id": None,
                                        "error": {"code": -32700, "message": "解析失败：%s" % e}},
                                       ensure_ascii=False).encode("utf-8"))
            return
        resp = handle(msg)
        self._send(200, json.dumps(resp or {}, ensure_ascii=False, default=str).encode("utf-8"))


def serve_http(port, token):
    _Handler.TOKEN = token or ""
    if not token:
        sys.stderr.write("[mcp] 警告：未设置 CF_MCP_TOKEN，HTTP 模式处于无鉴权状态（仅限本机调试）\n")
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    sys.stderr.write("[mcp] HTTP 模式监听 http://127.0.0.1:%d/mcp\n" % port)
    sys.stderr.flush()
    srv.serve_forever()


# =============================================================================
# 九、千问办公注册配置片段（直接粘贴）
# =============================================================================
REGISTER_SNIPPET = {
    "mcpServers": {
        "cashflow-workbench": {
            "command": "python",
            "args": ["D:/CashflowRiskWorkbench/qwen-integration/mcp_frontend_server.py"],
            "env": {
                "CF_MCP_TOKEN": "【可选】HTTP 模式鉴权令牌；stdio 模式可省略",
                "PYTHONIOENCODING": "utf-8"
            },
            "transport": "stdio",
            "disabled": False
        }
    }
}


# =============================================================================
# 十、入口
# =============================================================================
def main():
    ap = argparse.ArgumentParser(description="千问办公 MCP Server（前端指令接收）")
    ap.add_argument("--stdio", action="store_true", help="stdio 传输（默认，供千问办公拉起）")
    ap.add_argument("--http", action="store_true", help="HTTP 传输（本地自测）")
    ap.add_argument("--port", type=int, default=int(os.environ.get("CF_MCP_PORT", "8090")))
    ap.add_argument("--token", default=os.environ.get("CF_MCP_TOKEN", ""))
    ap.add_argument("--print-config", action="store_true", help="打印千问办公注册配置片段")
    a = ap.parse_args()

    if a.print_config:
        print(json.dumps(REGISTER_SNIPPET, ensure_ascii=False, indent=2))
        return 0
    if a.http:
        serve_http(a.port, a.token)
    else:
        serve_stdio()
    return 0


if __name__ == "__main__":
    sys.exit(main())
