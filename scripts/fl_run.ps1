# Bọc `flwr run` cho Windows (Flower 1.40):
#  - đưa .venv\Scripts vào PATH (flwr cần gọi flower-superlink),
#  - tắt cài dependency theo từng run (dùng luôn venv có torch CUDA),
#  - truyền đường dẫn tuyệt đối data/ và results/ (app chạy từ bản sao trong ~/.flwr/apps).
# Ví dụ:
#   .\scripts\fl_run.ps1 "num-server-rounds=3"           # pipeline paper: data_paper/, 3 client, ResVGG-SwinNet
#   .\scripts\fl_run.ps1 "arch='resnet'"                 # một biến thể ablation
#   .\scripts\fl_run.ps1 "scenario='S3' arch='mlp' local-epochs=2 batch-size=256" -Clients 5 -DataDir data -ResultsDir results   # pipeline cũ
# -Actors: số ClientApp chạy song song (mỗi actor nạp torch ~0,5 GB RAM; máy 16 GB nên để 2–4).
# -Gpus: phần GPU cho mỗi ClientApp (vd. 1 = mỗi lúc một client dùng GPU). 0 = Ray không cấp GPU,
#        client chạy CPU. Ray chỉ cho actor thấy GPU khi được cấp, nên mô hình lớn (ResVGG-SwinNet) cần -Gpus.
param([string]$RunConfig = "", [int]$Clients = 3, [int]$Actors = 3, [double]$Gpus = 0,
      [string]$DataDir = "data_paper", [string]$ResultsDir = "results_paper")
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
    $fed = "num-supernodes=$Clients client-resources-num-cpus=2 init-args-num-cpus=$(2 * $Actors)"
    if ($Gpus -gt 0) { $fed += " client-resources-num-gpus=$Gpus init-args-num-gpus=1" }
    flwr run . --stream --federation-config $fed --run-config $cfg
    exit $LASTEXITCODE
} finally { Pop-Location }
