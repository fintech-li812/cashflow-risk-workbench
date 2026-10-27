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
import secrets
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

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
TOKEN = (os.environ.get("WORKBENCH_TOKEN") or "").strip() or secrets.token_urlsafe(32)

_HOSTS = (os.environ.get("WORKBENCH_ALLOWED_HOSTS") or "").strip()
ALLOWED_HOSTS = {h.strip() for h in _HOSTS.split(",") if h.strip()} or {
    "127.0.0.1:{}".format(PORT),
    "localhost:{}".format(PORT),
}

MAX_BODY = 512_000


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
