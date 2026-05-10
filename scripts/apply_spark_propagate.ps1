param(
    [string]$workspace = 'C:\Users\nemex\OneDrive\Documenti\GitHub\uno-ultra-v68',
    [string]$engine = 'C:\Users\nemex\OneDrive\Documenti\GitHub\spark-framework-engine'
)

$ws = $workspace
$engineRoot = $engine
$time = Get-Date -Format yyyyMMddHHmmss
$bk = Join-Path $ws ".github-backup-$time"

Write-Host "[SPARK-PROP] Creating backup: $bk"
Copy-Item -Path (Join-Path $ws ".github") -Destination $bk -Recurse -Force
Write-Host "[SPARK-PROP] Backup created in: $bk"

Set-Location $engineRoot
Write-Host "[SPARK-PROP] Running spark-init.py in engine root: $engineRoot"
& ".\.venv\Scripts\python.exe" ".\spark-init.py" --workspace $ws
Write-Host "[SPARK-PROP] spark-init.py finished"
