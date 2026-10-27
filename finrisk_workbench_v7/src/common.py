"""公共层：配置装载、结果口径、输入哈希、日志、审计落库。

对齐 config.json 的两条硬性约束：
- reproducibility.require_input_hash=true  -> 缺输入哈希清单一律拒绝跑
- reproducibility.result_round_decimals=4  -> 所有对外结果统一 4 位小数
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
INPUT = ROOT / "input"
OUTPUT = ROOT / "output"
LOGS = ROOT / "logs"
CHANGES = ROOT / "changes"

AUDIT_DB_REL = None  # 运行时从 config.audit.local_store 解析


def load_config() -> dict:
    with open(DATA / "config.json", encoding="utf-8") as f:
        return json.load(f)


def load_templates() -> dict:
    with open(DATA / "industry_templates.json", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- 结果口径
_DP = 4


def set_precision(config: dict) -> None:
    global _DP
    _DP = int(config.get("reproducibility", {}).get("result_round_decimals", 4))


def r(x):
    """统一结果口径：None 原样返回，浮点按配置位数四舍五入。"""
    if x is None:
        return None
    if isinstance(x, bool):
        return x
    if isinstance(x, int):
        return x
    return round(float(x), _DP)


def rmap(d: dict) -> dict:
    return {k: (r(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
            for k, v in d.items()}


# ---------------------------------------------------------------- 日期工具
def parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def week_start(base: date, week: int) -> date:
    """第 k 周（1 起）的周一。"""
    return base + timedelta(days=(week - 1) * 7)


# ---------------------------------------------------------------- 哈希
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(obj) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_input_manifest() -> dict:
    """给 input/ 下全部文件打指纹，写 output/hashes/input_manifest.json。"""
    files = sorted(p for p in INPUT.iterdir() if p.is_file())
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "algorithm": "sha256",
        "files": {p.name: {"sha256": sha256_file(p), "bytes": p.stat().st_size} for p in files},
    }
    manifest["manifest_hash"] = canonical_hash(
        {k: v["sha256"] for k, v in manifest["files"].items()}
    )
    out = OUTPUT / "hashes" / "input_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest


def load_csv(name: str) -> list[dict]:
    path = INPUT / name
    if not path.exists():
        raise FileNotFoundError(f"缺少输入台账：{path}")
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
                for row in csv.DictReader(f)]


# ---------------------------------------------------------------- 日志
def get_logger() -> logging.Logger:
    LOGS.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("finrisk")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s")
    fh = logging.FileHandler(LOGS / "pipeline.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


# ---------------------------------------------------------------- 审计落库
SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(
  run_id TEXT PRIMARY KEY, started_at TEXT, finished_at TEXT, status TEXT,
  schema_version TEXT, base_date TEXT, industry TEXT,
  config_hash TEXT, input_hash TEXT);
CREATE TABLE IF NOT EXISTS events(
  run_id TEXT, seq INTEGER, ts TEXT, module TEXT, entity TEXT, action TEXT,
  severity TEXT, actor TEXT, detail TEXT, prev_hash TEXT, row_hash TEXT,
  PRIMARY KEY(run_id, seq));
CREATE TABLE IF NOT EXISTS rule_gate(
  run_id TEXT, ts TEXT, target_key TEXT, current_value REAL, proposed_value REAL,
  change_request TEXT, signer_a TEXT, signer_b TEXT, decision TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS approvals(
  run_id TEXT, ts TEXT, item_id TEXT, amount_wan REAL, required_level TEXT,
  approver TEXT, result TEXT, reason TEXT, reason_len INTEGER);
CREATE TABLE IF NOT EXISTS predictions(
  run_id TEXT, period_type TEXT, period TEXT, metric TEXT, value REAL, level TEXT);
"""


class Audit:
    """SQLite 留痕 + 哈希链，防篡改；同时导出 CSV 供外部落库（config.audit.mcp_fallback）。"""

    def __init__(self, config: dict, run_id: str):
        self.config = config
        self.run_id = run_id
        rel = config["audit"].get("local_store", "output/audit.db")
        self.db_path = (ROOT / rel).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(SCHEMA)
        self._seq = 0
        self._prev_hash = "GENESIS"

    def start(self, config_hash: str, input_hash: str) -> None:
        c = self.config
        self.conn.execute(
            "INSERT OR REPLACE INTO runs VALUES(?,?,?,?,?,?,?,?,?,?)",
            (self.run_id, datetime.now().isoformat(timespec="seconds"), None, "running",
             c["schema_version"], c["base_date"], c["company"]["industry_code"],
             config_hash, input_hash),
        )
        self.conn.commit()

    def finish(self, status: str = "success") -> None:
        self.conn.execute(
            "UPDATE runs SET finished_at=?, status=? WHERE run_id=?",
            (datetime.now().isoformat(timespec="seconds"), status, self.run_id),
        )
        self.conn.commit()

    def event(self, module: str, entity: str, action: str, detail,
              severity: str = "info", actor: str = "system") -> None:
        self._seq += 1
        ts = datetime.now().isoformat(timespec="seconds")
        payload = json.dumps(detail, ensure_ascii=False, sort_keys=True)
        row_hash = hashlib.sha256(
            f"{self._prev_hash}|{self.run_id}|{self._seq}|{payload}".encode("utf-8")
        ).hexdigest()
        self.conn.execute(
            "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (self.run_id, self._seq, ts, module, entity, action, severity, actor,
             payload, self._prev_hash, row_hash),
        )
        self.conn.commit()
        self._prev_hash = row_hash

    def rule_gate(self, row: dict) -> None:
        self.conn.execute(
            "INSERT INTO rule_gate VALUES(?,?,?,?,?,?,?,?,?,?)",
            (self.run_id, datetime.now().isoformat(timespec="seconds"), row["target_key"],
             r(row.get("current_value")), r(row.get("proposed_value")),
             row.get("change_request"), row.get("signer_a"), row.get("signer_b"),
             row["decision"], row["reason"]),
        )
        self.conn.commit()

    def approval(self, row: dict) -> None:
        self.conn.execute(
            "INSERT INTO approvals VALUES(?,?,?,?,?,?,?,?,?)",
            (self.run_id, datetime.now().isoformat(timespec="seconds"), row["item_id"],
             r(row.get("amount_wan")), row.get("required_level"), row.get("approver"),
             row["result"], row.get("reason"), row.get("reason_len")),
        )
        self.conn.commit()

    def prediction(self, period_type: str, period: str, metric: str, value, level=None) -> None:
        self.conn.execute(
            "INSERT INTO predictions VALUES(?,?,?,?,?,?)",
            (self.run_id, period_type, period, metric, r(value), level),
        )
        self.conn.commit()

    def export_csv(self) -> list[Path]:
        """按 config.audit.csv_export_dir 导出，供外部脚本落 MySQL。"""
        outdir = ROOT / self.config["audit"].get("csv_export_dir", "output/audit_export")
        outdir.mkdir(parents=True, exist_ok=True)
        written = []
        for table in ("runs", "events", "rule_gate", "approvals", "predictions"):
            rows = self.conn.execute(f"SELECT * FROM {table} WHERE run_id=?",
                                     (self.run_id,)).fetchall()
            cols = [d[0] for d in self.conn.execute(f"SELECT * FROM {table} LIMIT 1").description]
            path = outdir / f"{table}_{self.run_id}.csv"
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(cols)
                w.writerows(rows)
            written.append(path)
        return written

    def close(self) -> None:
        self.conn.close()


def write_json(path: Path, obj) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path


def write_csv(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return path
