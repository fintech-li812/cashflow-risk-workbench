import os, json, subprocess

CFG = r"C:\Users\33847\.qwenworkcn\mcp.json"
cfg = json.load(open(CFG, encoding="utf-8"))
name = "制造业现金流_隔离联调_v2"
srv = cfg["mcpServers"][name]
cmd, args = srv["command"], srv["args"]

def uq(p):
    return p[1:-1] if len(p) >= 2 and p[0] == '"' and p[-1] == '"' else p

py, script = uq(cmd), uq(args[0])

print("== existence check ==")
for label, p in [("python.exe", py), ("qa_entry.py", script)]:
    print("  %-11s exists=%-5s  %s" % (label, os.path.exists(p), p))

def run(argv, shell):
    try:
        r = subprocess.run(argv, shell=shell, capture_output=True, timeout=8,
                           stdin=subprocess.DEVNULL,
                           executable="cmd.exe" if shell else None)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired as e:
        return "TIMEOUT(launched OK, still running)", e.stdout or b"", e.stderr or b""
    except OSError as e:
        return "OSError: %s" % e, b"", b""

def show(tag, argv, shell, cmdlinestr=None):
    print("\n== %s ==" % tag)
    print("  line :", cmdlinestr if cmdlinestr else argv)
    rc, so, se = run(argv, shell)
    print("  exit :", rc)
    if so.strip(): print("  out  :", so.decode("gbk", "replace").strip()[:300])
    if se.strip(): print("  err  :", se.decode("gbk", "replace").strip()[:300])

show("REPRO A: as-configured string (literal quotes kept) via cmd shell",
     " ".join([cmd] + args), True)
show("REPRO B: same string with embedded quotes stripped via cmd shell",
     " ".join([py, "-B", "-u", script, "stdio"]), True)
show("REPRO C: as-configured argv array, direct CreateProcess",
     [cmd] + args, False)
show("REPRO D: unquoted argv array, direct CreateProcess",
     [py, "-B", "-u", script, "stdio"], False)
