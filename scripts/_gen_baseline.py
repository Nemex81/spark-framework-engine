"""Generate baseline-verify-workspace.json via live MCP stdio call."""
import subprocess
import json
import sys
import pathlib

msgs = [
    json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "baseline-gen", "version": "1.0"}
        }
    }),
    json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}),
    json.dumps({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "scf_verify_workspace", "arguments": {}}
    }),
]
stdin_data = "\n".join(msgs) + "\n"

proc = subprocess.run(
    [sys.executable, "spark-framework-engine.py"],
    input=stdin_data, capture_output=True, text=True, timeout=30
)

lines = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
result_json = None
for line in lines:
    try:
        obj = json.loads(line)
        if obj.get("id") == 2:
            result_json = obj
            break
    except Exception:
        pass

if result_json is None:
    print("ERRORE: risposta id=2 non trovata")
    print("stdout:", proc.stdout[:800])
    print("stderr:", proc.stderr[-400:])
    sys.exit(1)

content = result_json.get("result", {}).get("content", [])
if content and isinstance(content, list):
    text = content[0].get("text", "")
else:
    text = str(result_json.get("result", result_json))

try:
    payload = json.loads(text)
except Exception:
    payload = {"raw": text}

out = pathlib.Path("docs/reports/baseline-verify-workspace.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"OK: scritto {out} ({out.stat().st_size} bytes)")
print(f"Chiavi top-level: {list(payload.keys())[:8]}")
