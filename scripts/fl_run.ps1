# Bọc `flwr run` cho Windows (Flower 1.40):
#  - đưa .venv\Scripts vào PATH (flwr cần gọi flower-superlink),
#  - tắt cài dependency theo từng run (dùng luôn venv có torch CUDA),
#  - truyền đường dẫn tuyệt đối data/ và results/ (app chạy từ bản sao trong ~/.flwr/apps).
# Ví dụ:
#   .\scripts\fl_run.ps1 "num-server-rounds=3 scenario='S3' proximal-mu=0.1"
#   .\scripts\fl_run.ps1 "scenario='S1'" -Clients 5
#   .\scripts\fl_run.ps1 "scenario='S1'" -Clients 3 -DataDir data_eve -ResultsDir results_eve   # Nhánh B
# -Actors: số ClientApp chạy song song (mỗi actor nạp torch ~0,5 GB RAM; máy 16 GB nên để 2–4).
param([string]$RunConfig = "", [int]$Clients = 5, [int]$Actors = 3, [string]$DataDir = "data", [string]$ResultsDir = "results")
$ErrorActionPreference = "Continue"   # log của flwr trên stderr không phải lỗi
$root = Split-Path -Parent $PSScriptRoot
$env:PATH = "$root\.venv\Scripts;$env:PATH"
$env:FLWR_DISABLE_RUNTIME_DEPENDENCY_INSTALLATION = "1"
$env:PYTHONIOENCODING = "utf-8"
$data = ((Join-Path $root $DataDir) -replace '\\', '/')
$results = ((Join-Path $root $ResultsDir) -replace '\\', '/')
$cfg = "data-dir='$data' results-dir='$results' num-clients=$Clients $RunConfig".Trim()
Push-Location $root
try {
    flwr run . --stream --federation-config "num-supernodes=$Clients client-resources-num-cpus=2 init-args-num-cpus=$(2 * $Actors)" --run-config $cfg
    exit $LASTEXITCODE
} finally { Pop-Location }
