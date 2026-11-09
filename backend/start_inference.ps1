param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8099
)

# Servidor de inferencia compartido: CLIP + VadCLIP + VideoMAE en la GPU, sin base de datos ni cámaras.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Falta .venv en la raiz del repo. Ejecutar: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r backend/requirements-gpu.txt'
}
$env:SENTRIX_ROLE = 'inference'
$env:SENTRIX_PROVIDER = 'cuda'
# VideoMAE en FP16 si existe modelo/fp16 (fuera de git): ocupa cerca de la mitad de VRAM y da las mismas alertas.
$fp16 = Join-Path $projectRoot 'modelo/fp16'
if (Test-Path -LiteralPath (Join-Path $fp16 'videomae_crime5_continuous.onnx.data')) {
    $env:SENTRIX_MODEL_ROOT = $fp16
    $env:SENTRIX_VADCLIP_ROOT = Join-Path $projectRoot 'modelo/vadclip'
    Write-Host 'VideoMAE en FP16 (modelo/fp16)'
} else {
    Write-Host 'No existe modelo/fp16: se usa VideoMAE en FP32'
}
Push-Location $PSScriptRoot
try {
    & $pythonPath (Join-Path $PSScriptRoot 'run_server.py') --host $BindHost --port $Port
} finally {
    Pop-Location
    Remove-Item Env:SENTRIX_ROLE, Env:SENTRIX_MODEL_ROOT, Env:SENTRIX_VADCLIP_ROOT -ErrorAction SilentlyContinue
}
if ($LASTEXITCODE -ne 0) { throw "El servidor de inferencia finalizo con codigo $LASTEXITCODE" }
