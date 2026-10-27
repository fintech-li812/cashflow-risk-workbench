"""verify：独立核对导入包与真实源。

不止比哈希：用包内 mapping/例外快照从真实源重新推导 records/issues，
与包内文件逐字节比对。即便攻击者改了字段并重算 manifest 哈希，
也会因与真实源推导结果不符而失败，并指出源地址。
"""
import json
import os
import tempfile

from . import SCHEMA
from .canon import compute_source_revision, sha256_file
from .scanner import ScanError, check_safe_relpath, scan


class VerifyFailure(Exception):
    pass


def _load_json(path):
    with open(path, "rb") as f:
        return json.loads(f.read().decode("utf-8"))


def verify(package_dir, source_dir, printer=print):
    errors = []

    def fail(msg):
        errors.append(msg)
        printer(f"[FAIL] {msg}")

    def ok(msg):
        printer(f"[OK] {msg}")

    if not os.path.isdir(package_dir):
        raise ScanError(f"包目录不存在: {package_dir}")
    if not os.path.isdir(source_dir):
        raise ScanError(f"源目录不存在: {source_dir}")

    manifest_path = os.path.join(package_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        fail("缺少 manifest.json")
        raise VerifyFailure("no manifest")
    manifest = _load_json(manifest_path)

    # 1. manifest 结构与五字段
    if manifest.get("kind") != "import_package" or manifest.get("schema") != SCHEMA:
        fail("manifest kind/schema 不符 mfg-import.v1")
    for k in ("tenant_id", "company_id", "period", "source_revision", "run_id"):
        if not manifest.get(k):
            fail(f"manifest 缺五字段: {k}")
    if manifest.get("unit") != "CNY":
        fail("manifest unit 不是 CNY")

    # 2. files 清单：路径安全、无重复、哈希与记录数核对（清单不含自身）
    seen = set()
    listed = {}
    for entry in manifest.get("files", []):
        p = entry.get("path", "")
        try:
            check_safe_relpath(p)
        except ScanError as e:
            fail(f"manifest files 含非法路径: {e}")
            continue
        if p in seen:
            fail(f"manifest files 路径重复: {p}")
        seen.add(p)
        listed[p] = entry
        if p == "manifest.json":
            fail("manifest files 不应包含自身")
        fp = os.path.join(package_dir, p)
        if not os.path.isfile(fp):
            fail(f"包内文件缺失: {p}")
            continue
        actual = sha256_file(fp)
        if actual != entry.get("sha256"):
            fail(f"包内文件哈希不符: {p}")
        if p == "records.jsonl" and entry.get("record_count") is not None:
            with open(fp, "rb") as f:
                n = sum(1 for _ in f if _.strip())
            if n != entry["record_count"]:
                fail(f"records.jsonl 记录数不符: 清单 {entry['record_count']} 实际 {n}")
    if not errors:
        ok("manifest 结构与文件哈希/记录数一致")

    # 3. 从真实源重算 source_revision
    mapping_snap = os.path.join(package_dir, "mapping.snapshot.json")
    if "mapping.snapshot.json" not in listed or not os.path.isfile(mapping_snap):
        fail("缺少 mapping.snapshot.json，无法独立重导")
        raise VerifyFailure("no mapping snapshot")
    with open(mapping_snap, "rb") as f:
        mapping_sha = sha256_file(mapping_snap)
    ex_snap = os.path.join(package_dir, "unit_exceptions.snapshot.json")
    exceptions_arg = ex_snap if os.path.isfile(ex_snap) else None

    sources = []
    for fname in sorted(os.listdir(source_dir)):
        if fname.lower().endswith(".xlsx") and not fname.startswith("~$"):
            sources.append({"logical_name": fname,
                            "sha256": sha256_file(os.path.join(source_dir, fname))})
    recomputed_rev = compute_source_revision(sources, mapping_sha)
    if recomputed_rev != manifest.get("source_revision"):
        fail(f"source_revision 与真实源不符（源可能已改变）: 包 {manifest.get('source_revision')} "
             f"!= 重算 {recomputed_rev}")
    else:
        ok("source_revision 与真实源一致")

    # 4. 用真实源独立重导，逐字节比对确定性输出
    with tempfile.TemporaryDirectory(prefix="mfg_verify_") as tmp:
        out = os.path.join(tmp, "reimport")
        scan(source_dir, out, mapping_snap, manifest.get("tenant_id"),
             manifest.get("company_id"), manifest.get("period"),
             manifest.get("run_id"), exceptions_path=exceptions_arg)
        for name in ("records.jsonl", "issues.jsonl", "inventory.json"):
            pkg_file = os.path.join(package_dir, name)
            new_file = os.path.join(out, name)
            if not os.path.isfile(pkg_file):
                fail(f"包内缺少 {name}")
                continue
            with open(pkg_file, "rb") as f:
                a = f.read()
            with open(new_file, "rb") as f:
                b = f.read()
            if a == b:
                ok(f"{name} 与真实源重导结果逐字节一致")
            else:
                _locate_diff(name, a, b, fail)

    if errors:
        printer(f"verify 失败: {len(errors)} 项不符")
        return 1
    printer("verify 通过: 包结构与真实源逐字段一致")
    return 0


def _locate_diff(name, a, b, fail):
    """指出第一处不符的记录及其来源地址（帮助定位被篡改字段）。"""
    if not name.endswith(".jsonl"):
        fail(f"{name} 与真实源重导结果不一致")
        return
    # 定位差异时统一换行符，避免因 CRLF 变化掩盖字段级定位
    la = [l for l in a.replace(b"\r\n", b"\n").split(b"\n") if l.strip()]
    lb = [l for l in b.replace(b"\r\n", b"\n").split(b"\n") if l.strip()]
    fail(f"{name} 与真实源重导结果不一致: 包 {len(la)} 行 vs 重导 {len(lb)} 行")
    for i, (x, y) in enumerate(zip(la, lb)):
        if x != y:
            try:
                rec_a = json.loads(x.decode("utf-8"))
                rec_b = json.loads(y.decode("utf-8"))
                loc = f"{rec_a.get('sheet')}!行{rec_a.get('row')}"
                for fname, nv in rec_b.get("normalized", {}).items():
                    ov = rec_a.get("normalized", {}).get(fname, {})
                    if ov != nv:
                        fail(
                            f"第 {i + 1} 行记录字段 {fname} 被篡改: "
                            f"包内值={ov.get('value')!r} 真实源 {loc} {nv.get('address')} "
                            f"重导值={nv.get('value')!r}"
                        )
            except Exception:
                fail(f"第 {i + 1} 行记录与真实源重导不符")
            return
    if len(la) != len(lb):
        fail(f"{name} 行数不一致")
