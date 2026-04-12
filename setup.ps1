<#
.SYNOPSIS
    Configura SPARK Framework Engine per un nuovo progetto.

.DESCRIPTION
    Crea il venv locale nel repo engine, installa mcp e lancia spark-init.py
    nella cartella del progetto indicata.
    Deve essere eseguito dalla cartella del repo spark-framework-engine.

.PARAMETER Project
    Percorso assoluto o relativo alla cartella del progetto da inizializzare.
    Default: cartella corrente al momento dell'invocazione.

.EXAMPLE
    .\setup.ps1
    .\setup.ps1 -Project "C:\Users\me\mio-progetto"
    .\setup.ps1 -Project "..\mio-progetto"
#>
param(
    [string]$Project = ""
)

$ErrorActionPreference = "Stop"

$EngineRoot  = $PSScriptRoot
$EnginePy    = Join-Path $EngineRoot "spark-framework-engine.py"
$InitPy      = Join-Path $EngineRoot "spark-init.py"
$VenvDir     = Join-Path $EngineRoot ".venv"
$VenvPython  = Join-Path $VenvDir "Scripts\python.exe"

# ---------------------------------------------------------------------------
# Sanity check: siamo nella cartella giusta?
# ---------------------------------------------------------------------------
if (-not (Test-Path $EnginePy)) {
    Write-Error "[SPARK] spark-framework-engine.py non trovato in: $EngineRoot`nEsegui lo script dalla cartella del repo spark-framework-engine."
    exit 1
}
if (-not (Test-Path $InitPy)) {
    Write-Error "[SPARK] spark-init.py non trovato in: $EngineRoot"
    exit 1
}

# ---------------------------------------------------------------------------
# Cartella progetto target
# ---------------------------------------------------------------------------
if ($Project -eq "") {
    $Project = (Get-Location).Path
}

try {
    $resolved = Resolve-Path -LiteralPath $Project -ErrorAction Stop
    $Project = $resolved.Path
} catch {
    Write-Error "[SPARK] Cartella progetto non trovata: $Project"
    exit 1
}

Write-Host "[SPARK] Motore  : $EngineRoot"
Write-Host "[SPARK] Progetto: $Project"
Write-Host ""

# ---------------------------------------------------------------------------
# Verifica Python 3.10+
# ---------------------------------------------------------------------------
$pythonCmd = $null
foreach ($candidate in @("python", "python3", "py")) {
    try {
        $ver = & $candidate -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2>$null
        if ($ver) {
            $parts = $ver.Trim().Split(" ")
            if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 10) {
                $pythonCmd = $candidate
                break
            }
        }
    } catch { }
}

if (-not $pythonCmd) {
    Write-Error "[SPARK] Python 3.10+ non trovato nel PATH.`nInstalla Python da https://python.org e riprova."
    exit 1
}

$fullVer = & $pythonCmd --version 2>&1
Write-Host "[SPARK] Python trovato: $fullVer ($pythonCmd)"

# ---------------------------------------------------------------------------
# Creazione venv (se non esiste o incompleto)
# ---------------------------------------------------------------------------
if (-not (Test-Path $VenvPython)) {
    Write-Host "[SPARK] Creazione ambiente virtuale .venv ..."
    & $pythonCmd -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Error "[SPARK] Creazione .venv fallita."
        exit 1
    }
    Write-Host "[SPARK] .venv creato in: $VenvDir"
} else {
    Write-Host "[SPARK] .venv gia presente: $VenvDir"
}

# ---------------------------------------------------------------------------
# Upgrade pip + installa mcp
# ---------------------------------------------------------------------------
Write-Host "[SPARK] Installazione dipendenze (mcp) ..."
& $VenvPython -m pip install --quiet --upgrade pip
& $VenvPython -m pip install --quiet --upgrade mcp
if ($LASTEXITCODE -ne 0) {
    Write-Error "[SPARK] Installazione mcp fallita."
    exit 1
}
Write-Host "[SPARK] Dipendenze installate."

# ---------------------------------------------------------------------------
# Esegui spark-init.py dalla cartella del progetto (usa il venv python!)
# ---------------------------------------------------------------------------
Write-Host "[SPARK] Configurazione workspace in: $Project"
Write-Host ""

Push-Location $Project
try {
    & $VenvPython $InitPy
    if ($LASTEXITCODE -ne 0) {
        Write-Error "[SPARK] spark-init.py ha restituito un errore."
        exit 1
    }
} finally {
    Pop-Location
}

# ---------------------------------------------------------------------------
# Riepilogo finale
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=========================================="
Write-Host " Setup completato con successo."
Write-Host ""
Write-Host " Prossimi passi:"
Write-Host "   1. Apri il progetto in VS Code:"
Write-Host "        code `"$Project`""
Write-Host "   2. VS Code avviera il server SPARK automaticamente."
Write-Host "   3. Apri la chat Copilot (Agent mode) e scrivi:"
Write-Host "        @spark-assistant ciao"
Write-Host "=========================================="
