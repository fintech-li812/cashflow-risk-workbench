"""Public-facing HTTP service: serves the page and the API from one origin.

This is NOT a rewrite of anything. Every number on the page is produced by
program_workbench / program_service; this file only exposes them over HTTP.

Kept from the loopback QA server: bounded body, CSRF token, CSP, Origin check,
and the rule that a failed database write never reports success.
Changed: listen address, allowed hosts and token are configurable, so the same
binary can run behind Nginx on the server instead of only on loopback.
"""
from __future__ import annotations

import json
import os
import platform
import secrets
import socket
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pymysql
from pymysql.cursors import DictCursor

from config import Config
from program_service import ProgramService
from program_workbench import project_status, list_sources, calculate, readiness, data_audit
from service import strict_result
from notify import push, channels

PORT = int(os.environ.get("WORKBENCH_PORT", "18767"))
HOST = os.environ.get("WORKBENCH_HOST", "127.0.0.1")
# Derived from this file's location so the same code works on Windows and Linux.
# src -> program_v1 -> mcp-server -> project root
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WEB = Path(os.environ.get("WORKBENCH_WEB") or (_ROOT / "web" / "工作台_程序计算版.html"))
CONSOLE = Path(os.environ.get("WORKBENCH_CONSOLE") or (_ROOT / "web" / "后端控制台.html"))
TOKEN = (os.environ.get("WORKBENCH_TOKEN") or "").strip() or secrets.token_urlsafe(32)
START = time.time()

_HOSTS = (os.environ.get("WORKBENCH_ALLOWED_HOSTS") or "").strip()
ALLOWED_HOSTS = {h.strip() for h in _HOSTS.split(",") if h.strip()} or {
    "127.0.0.1:{}".format(PORT),
    "localhost:{}".format(PORT),
}

MAX_BODY = 512_000

# ---------- read-only backend console ----------
# Everything below only observes. It never calculates, writes or pushes; the
# point is to let an operator see what is actually running, not what is claimed.

SERVICES = (
    ("cf-workbench", "cf-workbench", "页面 + HTTP API（本进程）"),
    ("cf-mcp-http", "mcp", "MCP over HTTP，供千问调用"),
    ("nginx", "nginx", "TLS 入口，反代到上面两个"),
    ("mysql", "mysql", "MySQL，只绑回环"),
)

ENDPOINTS = (
    ("GET", "/", "工作台页面", True),
    ("GET", "/console", "本页（后端控制台）", True),
    ("GET", "/api/console", "后端聚合状态，本页数据源", True),
    ("GET", "/api/status", "能力与架构清单", True),
    ("GET", "/api/sources", "已登记数据来源与可用性", True),
    ("GET", "/api/calculate?source_id=…", "现场读取输入并计算，不写库", True),
    ("GET", "/api/readiness?source_id=…", "输入就绪检查", True),
    ("GET", "/api/audit?source_id=…", "原始八表只读检查", True),
    ("GET", "/api/notify-channels", "推送通道是否配置", True),
    ("POST", "/api/save", "写入隔离库（需会话令牌）", False),
    ("POST", "/api/query", "按请求编号回查（需会话令牌）", False),
    ("POST", "/api/notify", "推送钉钉/企业微信（需会话令牌）", False),
    ("POST", "/mcp", "MCP JSON-RPC 端点，走 8123", False),
)

MCP_TOOLS = (
    ("get_workbench_status", "架构、来源画像、数据库连通性"),
    ("list_manufacturing_sources", "列出固定的原始样例与合成输入"),
    ("inspect_manufacturing_source", "只读查看某个来源，不改原表"),
    ("get_manufacturing_readiness", "输入就绪检查，问题仍为阻塞项"),
    ("get_manufacturing_data_audit", "原始八表或合成八表的只读审计"),
    ("calculate_manufacturing_cashflow", "用 Decimal 现场计算，标注 SYNTHETIC，不写库"),
    ("read_cashflow_result", "重算并返回来源与算法摘要"),
    ("save_cashflow_result", "只允许精确重算结果入隔离库"),
    ("query_cashflow_result", "按请求编号精确回查"),
)


def _listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.35):
            return True
    except OSError:
        return False


def _service_ports() -> dict:
    mcp_port = os.environ.get("MCP_HTTP_PORT") or "8123"
    return {
        "cf-workbench": PORT,
        "mcp": int(mcp_port) if str(mcp_port).isdigit() else 8123,
        "nginx": 443,
        "mysql": 3306,
    }


def _db_report() -> dict:
    try:
        cfg = Config.from_env()
    except Exception as exc:
        return {"connected": False, "detail": "配置不完整（{}）".format(type(exc).__name__)}
    try:
        conn = pymysql.connect(
            host=cfg.host,
            port=cfg.port,
            user=cfg.user,
            password=cfg.password,
            database=cfg.database,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=True,
            connect_timeout=4,
            read_timeout=6,
            write_timeout=6,
            init_command="SET time_zone='+00:00'",
        )
    except Exception as exc:
        return {"connected": False, "detail": "连接失败（{}）".format(type(exc).__name__)}
    base = {
        "connected": True,
        "engine": "MySQL",
        "name": cfg.database,
        "table": "mfg_cashflow_runs_v1",
        "host": cfg.host,
        "port": cfg.port,
        "user": cfg.user,
        "rows": None,
        "recent": [],
    }
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM mfg_cashflow_runs_v1")
            base["rows"] = int(cur.fetchone()["n"])
            cur.execute(
                "SELECT record_id,request_id,period,operation,stored_at,"
                "COALESCE(JSON_UNQUOTE(JSON_EXTRACT(payload,'$.amounts.closing')),"
                "JSON_UNQUOTE(JSON_EXTRACT(payload,'$.result.amounts.closing'))) AS closing "
                "FROM mfg_cashflow_runs_v1 ORDER BY stored_at DESC LIMIT 5"
            )
            for row in cur.fetchall():
                base["recent"].append(
                    {
                        "record_id": row["record_id"],
                        "request_id": row["request_id"],
                        "period": row["period"],
                        "operation": row["operation"],
                        "closing": row["closing"],
                        "stored_at": row["stored_at"].strftime("%Y-%m-%d %H:%M:%S") if row["stored_at"] else "",
                    }
                )
    except Exception as exc:
        base["detail"] = "查询失败（{}）".format(type(exc).__name__)
    finally:
        conn.close()
    return base


def console_report() -> dict:
    now = datetime.now().astimezone()
    started = datetime.fromtimestamp(START).astimezone()
    ports = _service_ports()
    services = [
        {"name": name, "port": ports[alias], "listening": _listening(ports[alias]), "note": note}
        for name, alias, note in SERVICES
    ]
    public = [
        h.split(":")[0]
        for h in sorted(ALLOWED_HOSTS)
        if not h.startswith(("127.0.0.1", "localhost")) and h[0].isalpha()
    ]
    mcp_host = public[0] if public else "127.0.0.1"
    return {
        "schema_version": "workbench-console.v1",
        "checked_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "runtime": {
            "app": "cf-workbench",
            "pid": os.getpid(),
            "bind": "{}:{}".format(HOST, PORT),
            "python": platform.python_version(),
            "uptime_seconds": int(time.time() - START),
            "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "services": services,
        "database": _db_report(),
        "endpoints": [
            {"method": m, "path": p, "note": n, "probe": b} for m, p, n, b in ENDPOINTS
        ],
        "mcp": {
            "url": "https://{}/mcp".format(mcp_host),
            "transport": "streamable-http（JSON-RPC 2.0）",
            "auth": "Host 白名单 + DNS 重绑定防护",
            "tools": [{"name": n, "note": d} for n, d in MCP_TOOLS],
        },
        "notify": dict(channels(), policy="失败即报错，不假装成功"),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "workbench"

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *args):
        pass

    def respond(self, data, code=200, typ="application/json; charset=utf-8"):
        raw = (
            data.encode("utf-8")
            if isinstance(data, str)
            else json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        )
        self.send_response(code)
        headers = {
            "Content-Type": typ,
            "Content-Length": str(len(raw)),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; "
            "frame-ancestors 'none'; base-uri 'none'",
        }
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)

    def trusted(self) -> bool:
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        if host not in ALLOWED_HOSTS:
            return False
        if origin is None:
            return True
        scheme = "https" if host.split(":")[0] not in {"127.0.0.1", "localhost"} else "http"
        return origin in {"{}://{}".format(scheme, h) for h in ALLOWED_HOSTS}

    def do_GET(self):
        if not self.trusted():
            return self.respond({"error": "host_not_allowed"}, 403)
        path = urlparse(self.path)
        params = parse_qs(path.query)
        try:
            if path.path in ("/", "/index.html"):
                return self.respond(
                    WEB.read_text(encoding="utf-8").replace("__CSRF_TOKEN__", TOKEN),
                    typ="text/html; charset=utf-8",
                )
            if path.path in ("/console", "/console/"):
                return self.respond(
                    CONSOLE.read_text(encoding="utf-8").replace("__CSRF_TOKEN__", TOKEN),
                    typ="text/html; charset=utf-8",
                )
            if path.path == "/api/console":
                return self.respond(console_report())
            if path.path == "/api/status":
                try:
                    return self.respond(project_status())
                except ValueError as exc:
                    # Storage is a real gap, not something to hide. Degrade loudly
                    # so the page still loads and says "database unavailable"
                    # instead of claiming a connection that does not exist.
                    return self.respond(
                        {
                            "status": "degraded",
                            "detail": str(exc),
                            "components": {"database": "unavailable"},
                            "note": "数据库未配置或不可用；计算仍可运行，保存与回查不可用。",
                        }
                    )
            if path.path == "/api/sources":
                return self.respond(list_sources())
            if path.path == "/api/calculate":
                return self.respond(calculate(params.get("source_id", ["program_demo_v1"])[0]))
            if path.path == "/api/readiness":
                return self.respond(readiness(params.get("source_id", ["manufacturing_sample_v1"])[0]))
            if path.path == "/api/audit":
                return self.respond(data_audit(params.get("source_id", ["manufacturing_sample_v1"])[0]))
            if path.path == "/api/notify-channels":
                return self.respond({"channels": channels()})
            return self.respond({"error": "not_found"}, 404)
        except (ValueError, OSError) as exc:
            return self.respond({"error": type(exc).__name__, "detail": str(exc)}, 422)
        except Exception:
            return self.respond(
                {"error": "operation_failed", "detail": "操作失败；未确认数据库提交时请使用同一请求编号回查。"}, 503
            )

    def do_POST(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 1 or size > MAX_BODY:
                return self.respond({"error": "request_size_invalid"}, 413)
            raw = self.rfile.read(size)
            if len(raw) != size:
                return self.respond({"error": "incomplete_request_body"}, 400)
        except (ValueError, TimeoutError):
            return self.respond({"error": "request_body_invalid"}, 400)

        if (
            not self.trusted()
            or not secrets.compare_digest(self.headers.get("X-Workbench-Token", ""), TOKEN)
        ):
            return self.respond({"error": "session_required"}, 403)

        try:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.respond({"error": "json_required"}, 415)
            data = strict_result(raw)
            route = urlparse(self.path).path

            if route == "/api/notify":
                # Push only what the engine returns right now. The caller supplies a
                # source id, never the amounts, so a client cannot fabricate the text.
                # No database needed here: notification must survive a storage outage.
                if not isinstance(data, dict) or set(data) != {"source_id"}:
                    raise ValueError("notify_fields_invalid")
                source_id = data["source_id"]
                if not isinstance(source_id, str) or not source_id:
                    raise ValueError("source_id_invalid")
                payload = dict(calculate(source_id))
                payload["source_id"] = source_id
                return self.respond({"pushed": True, "detail": push(payload)})

            service = ProgramService(Config.from_env())

            if route == "/api/save":
                if not isinstance(data, dict) or set(data) != {"result", "request_id"}:
                    raise ValueError("save_fields_invalid")
                return self.respond(service.save(data["result"], data["request_id"]))

            if route == "/api/query":
                if not isinstance(data, dict) or set(data) != {"request_id", "period", "source_revision", "run_id"}:
                    raise ValueError("query_fields_invalid")
                return self.respond(service.query(**data))

            return self.respond({"error": "not_found"}, 404)
        except (ValueError, TypeError, OSError) as exc:
            return self.respond({"error": type(exc).__name__, "detail": str(exc)}, 422)
        except Exception:
            return self.respond(
                {"error": "operation_failed", "detail": "操作失败；请使用同一请求编号回查，不要更换编号重复保存。"}, 503
            )


def main():
    server = HTTPServer((HOST, PORT), Handler)
    print("Workbench public server: http://{}:{}".format(HOST, PORT), flush=True)
    print("allowed hosts: {}".format(", ".join(sorted(ALLOWED_HOSTS))), flush=True)
    print("notify channels: {}".format(json.dumps(channels(), ensure_ascii=False)), flush=True)
    if not os.environ.get("WORKBENCH_TOKEN"):
        print("session token (shown once, not persisted): {}".format(TOKEN), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
