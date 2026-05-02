"""Smoke test: avvio server MCP via stdio e verifica risposta initialize.

Abilitato solo se la variabile d'ambiente SPARK_SMOKE_TEST=1 è impostata,
per non bloccare la CI standard.
"""
import json
import os
import subprocess
import sys

import pytest

SMOKE_ENABLED = os.environ.get("SPARK_SMOKE_TEST", "0") == "1"

_INITIALIZE_MSG = json.dumps(
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "smoke-test", "version": "0.1"},
        },
    }
)


@pytest.mark.skipif(not SMOKE_ENABLED, reason="Set SPARK_SMOKE_TEST=1 to enable")
def test_mcp_initialize_via_stdio(tmp_path: pytest.TempPathFactory) -> None:
    """Verifica che il server MCP risponda correttamente a initialize via stdio."""
    engine_script = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "spark-framework-engine.py")
    )

    proc = subprocess.Popen(
        [sys.executable, engine_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(tmp_path),
        env={**os.environ, "WORKSPACE_FOLDER": str(tmp_path)},
    )
    try:
        payload = (_INITIALIZE_MSG + "\n").encode("utf-8")
        # Invia messaggio initialize e attendi risposta con timeout 5s.
        stdout_data, stderr_data = proc.communicate(input=payload, timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout_data, stderr_data = proc.communicate()
        pytest.fail(
            "Server MCP non ha risposto entro 5 secondi. "
            f"stderr: {stderr_data.decode('utf-8', errors='replace')[:500]}"
        )
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()

    stderr_text = stderr_data.decode("utf-8", errors="replace")

    # Nessuna eccezione non gestita deve apparire su stderr.
    assert "Traceback" not in stderr_text, (
        f"Eccezione non gestita rilevata su stderr:\n{stderr_text[:1000]}"
    )

    # La risposta deve contenere almeno una riga JSON valida.
    stdout_text = stdout_data.decode("utf-8", errors="replace").strip()
    assert stdout_text, (
        f"stdout vuoto. stderr:\n{stderr_text[:500]}"
    )

    # Cerca la riga di risposta JSON-RPC con id=1.
    response: dict = {}
    for line in stdout_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and candidate.get("id") == 1:
            response = candidate
            break

    assert response, (
        f"Nessuna risposta JSON-RPC con id=1 trovata in stdout:\n{stdout_text[:500]}"
    )
    assert response.get("jsonrpc") == "2.0", f"jsonrpc atteso '2.0': {response}"
    assert response.get("id") == 1, f"id atteso 1: {response}"
    assert "result" in response, f"Campo 'result' mancante: {response}"
    assert "protocolVersion" in response["result"], (
        f"Campo 'protocolVersion' mancante in result: {response['result']}"
    )
