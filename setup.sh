#!/usr/bin/env bash
# setup.sh — Configura SPARK Framework Engine per un nuovo progetto (Unix/macOS).
#
# Uso:
#   ./setup.sh                          # progetto = cartella corrente
#   ./setup.sh /percorso/mio-progetto   # progetto esplicito
#
# Deve essere eseguito dalla cartella del repo spark-framework-engine.

set -euo pipefail

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_PY="$ENGINE_ROOT/spark-framework-engine.py"
INIT_PY="$ENGINE_ROOT/spark-init.py"
VENV_DIR="$ENGINE_ROOT/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

# ---------------------------------------------------------------------------
# Sanity check
# ---------------------------------------------------------------------------
if [[ ! -f "$ENGINE_PY" ]]; then
    echo "[SPARK] ERRORE: spark-framework-engine.py non trovato in: $ENGINE_ROOT"
    echo "        Esegui lo script dalla cartella del repo spark-framework-engine."
    exit 1
fi
if [[ ! -f "$INIT_PY" ]]; then
    echo "[SPARK] ERRORE: spark-init.py non trovato in: $ENGINE_ROOT"
    exit 1
fi

# ---------------------------------------------------------------------------
# Cartella progetto target
# ---------------------------------------------------------------------------
PROJECT="${1:-$(pwd)}"
PROJECT="$(cd "$PROJECT" && pwd)"

echo "[SPARK] Motore  : $ENGINE_ROOT"
echo "[SPARK] Progetto: $PROJECT"
echo ""

# ---------------------------------------------------------------------------
# Verifica Python 3.10+
# ---------------------------------------------------------------------------
PYTHON_CMD=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2>/dev/null || true)
        major=$(echo "$ver" | awk '{print $1}')
        minor=$(echo "$ver" | awk '{print $2}')
        if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
            PYTHON_CMD="$candidate"
            break
        fi
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    echo ""
    echo "[SPARK] ERRORE: Python 3.10 o superiore non trovato nel PATH."
    echo ""
    echo " Come risolvere:"
    echo "   1. Installa Python da: https://python.org/downloads"
    echo "      oppure usa il package manager del tuo sistema:"
    echo "        macOS : brew install python3"
    echo "        Ubuntu: sudo apt install python3"
    echo "   2. Verifica con: python3 --version"
    echo "   3. Riesegui questo script."
    echo ""
    exit 1
fi

echo "[SPARK] Python trovato: $($PYTHON_CMD --version) ($PYTHON_CMD)"

# ---------------------------------------------------------------------------
# Creazione venv
# ---------------------------------------------------------------------------
if [[ ! -f "$VENV_PYTHON" ]]; then
    echo ""
    echo "[SPARK] E' necessario creare un ambiente virtuale Python in:"
    echo "        $VENV_DIR"
    echo ""
    echo "        L'ambiente contiene solo la dipendenza 'mcp' richiesta"
    echo "        dal server SPARK. Non modifica il tuo progetto."
    echo ""
    read -r -p "[SPARK] Premi INVIO per continuare o digita N per annullare: " confirm
    if [[ "$confirm" =~ ^[Nn] ]]; then
        echo "[SPARK] Operazione annullata dall'utente."
        exit 0
    fi
fi

if [[ ! -f "$VENV_PYTHON" ]]; then
    echo "[SPARK] Creazione ambiente virtuale .venv ..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    echo "[SPARK] .venv creato in: $VENV_DIR"
else
    echo "[SPARK] .venv gia presente: $VENV_DIR"
fi

# ---------------------------------------------------------------------------
# Upgrade pip + installa mcp
# ---------------------------------------------------------------------------
echo "[SPARK] Installazione dipendenze (mcp) ..."
"$VENV_PYTHON" -m pip install --quiet --upgrade pip
"$VENV_PYTHON" -m pip install --quiet --upgrade mcp
echo "[SPARK] Dipendenze installate."

# ---------------------------------------------------------------------------
# Esegui spark-init.py dalla cartella del progetto
# ---------------------------------------------------------------------------
echo "[SPARK] Configurazione workspace in: $PROJECT"
echo ""

cd "$PROJECT"
"$VENV_PYTHON" "$INIT_PY"

# ---------------------------------------------------------------------------
# Riepilogo finale
# ---------------------------------------------------------------------------
echo ""
echo "=========================================="
echo " Setup completato con successo."
echo ""
echo " Prossimi passi:"
echo "   1. Apri il progetto in VS Code:"
echo "        code \"$PROJECT\""
echo "   2. VS Code avviera il server SPARK automaticamente."
echo "   3. Apri la chat Copilot (Agent mode) e scrivi:"
echo "        @spark-assistant ciao"
echo "=========================================="
