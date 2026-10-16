# Ma trận thí nghiệm E1–E5 (mục 6.6 + 8.2), mỗi cấu hình 3 seed. Chạy từ thư mục gốc dự án:
#   .\scripts\run_all.ps1                 # đầy đủ (30 vòng)
#   .\scripts\run_all.ps1 -Rounds 3 -Seeds 0 -Epochs 2   # chạy thử nhanh
param(
    [int]$Rounds = 30,
    [int[]]$Seeds = @(0, 1, 2),
    [int]$Epochs = 60,
    [string[]]$Scenarios = @("S1", "S2a", "S2b", "S3", "S4"),
    [double[]]$Mus = @(0.0, 0.01, 0.1)
)
$ErrorActionPreference = "Continue"   # flwr ghi log ra stderr; lỗi được kiểm tra bằng $LASTEXITCODE
$env:PYTHONIOENCODING = "utf-8"
$py = ".\.venv\Scripts\python.exe"
New-Item -ItemType Directory -Force results | Out-Null

foreach ($seed in $Seeds) {
    foreach ($sc in $Scenarios) {
        foreach ($mu in $Mus) {
            Write-Host "=== FL scenario=$sc mu=$mu seed=$seed ===" -ForegroundColor Cyan
            & .\scripts\fl_run.ps1 "num-server-rounds=$Rounds scenario='$sc' proximal-mu=$mu seed=$seed"
            if ($LASTEXITCODE -ne 0) { throw "flwr run thất bại ($sc, mu=$mu, seed=$seed)" }
        }
    }
    & $py baselines/centralized.py --scenario S1 --epochs $Epochs --seed $seed
    foreach ($sc in @("S1", "S3")) { & $py baselines/local_only.py --scenario $sc --epochs $Epochs --seed $seed }
}

# E7 (tuỳ chọn): client 1 bị chiếm và đảo nhãn, so sánh FedAvg với FedTrimmedAvg
# & .\scripts\fl_run.ps1 "scenario='S1' poison-clients='0' strategy='fedavg'"
# & .\scripts\fl_run.ps1 "scenario='S1' poison-clients='0' strategy='trimmed'"

& $py analysis/plots.py
