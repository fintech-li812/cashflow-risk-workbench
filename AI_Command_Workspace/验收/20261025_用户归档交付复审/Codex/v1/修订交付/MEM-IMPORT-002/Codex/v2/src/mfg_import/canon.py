"""规范 JSON 与哈希：统一接口 v1 规定的唯一序列化方式，不另起一套。"""
import hashlib
import json


def canonical_bytes(obj) -> bytes:
    """统一接口规定的规范 JSON 字节串。"""
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_canonical(obj) -> str:
    return sha256_hex(canonical_bytes(obj))


def compute_source_revision(sources, mapping_sha256: str) -> str:
    """source_revision=SHA256(规范JSON({"sources":[{logical_name,sha256}...],"mapping_sha256":...})).

    sources 按 logical_name 排序；不含绝对路径、扫描时间和输出路径。
    """
    items = [
        {"logical_name": s["logical_name"], "sha256": s["sha256"]} for s in sources
    ]
    items.sort(key=lambda x: x["logical_name"])
    return sha256_canonical({"mapping_sha256": mapping_sha256, "sources": items})


def compute_record_key(source_file_sha256: str, sheet: str, row: int) -> str:
    """source_record_key=SHA256(规范JSON({"source_file_sha256":...,"sheet":...,"row":整数}))."""
    return sha256_canonical(
        {"source_file_sha256": source_file_sha256, "row": row, "sheet": sheet}
    )
