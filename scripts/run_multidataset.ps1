# Ma trận thí nghiệm multidataset_v1: 2 client (CIC-DDoS2019, UNSW-NB15) × 3 lớp.
#   .\scripts\run_multidataset.ps1 -Profile smoke                # 2 vòng × 1 epoch, seed 0, kiểm tra tích hợp
#   .\scripts\run_multidataset.ps1 -Profile main                 # 30 × 5, seed 0/1/2, DAS và đối chứng toàn bộ cột
#   .\scripts\run_multidataset.ps1 -Profile main -Steps prep     # chỉ chuẩn bị dữ liệu
# -Steps: prep, fl, fl_all, baselines, eval (mặc định tất cả). -Gpus: phần GPU cho mỗi ClientApp (0 = CPU).
# Yêu cầu: đã chạy prepare/download_datasets.py (CIC, UNSW).
param([ValidateSet("smoke", "main")][string]$Profile = "smoke",
      [string[]]$Steps = @("prep", "fl", "fl_all", "baselines", "eval"),
      [int]$Actors = 1, [double]$Gpus = 0)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"
$cfg = Get-Content (Join-Path $root "configs\multidataset.json") -Raw | ConvertFrom-Json
$p = $cfg.profiles.$Profile
$seeds = $p.seeds
$rounds, $epochs = $p.rounds, $p.local_epochs
$baseEpochs = if ($Profile -eq "smoke") { $rounds * $epochs } else { $cfg.fl.baseline_epochs }

function Invoke-Step([string]$what, [scriptblock]$block) {
    Write-Host "`n=== $what ===" -ForegroundColor Cyan
    & $block
    if ($LASTEXITCODE) { throw "$what thất bại (exit $LASTEXITCODE)" }
}

Push-Location $root
try {
    $variants = @(@{ Name = "das"; Data = "data_paper_multi/$Profile"; Res = "results_multidataset/$Profile" })
    if ($Steps -contains "fl_all") {
        $variants += @{ Name = "all"; Data = "data_paper_multi/${Profile}_all"; Res = "results_multidataset/${Profile}_all" }
    }
    if ($Steps -contains "prep") {
        foreach ($v in $variants) {
            Invoke-Step "prep $Profile ($($v.Name))" { & $py prepare/multidataset_pipeline.py --profile $Profile --feature-set $v.Name }
        }
    }
    foreach ($v in $variants) {
        $want = if ($v.Name -eq "das") { "fl" } else { "fl_all" }
        if ($Steps -notcontains $want) { continue }
        foreach ($s in $seeds) {
            $rc = "scenario='multidataset' arch='$($cfg.fl.arch)' num-server-rounds=$rounds local-epochs=$epochs seed=$s"
            Invoke-Step "FL $($v.Name) seed $s" { & (Join-Path $PSScriptRoot "fl_run.ps1") $rc -Clients $cfg.clients.Count -Actors $Actors -Gpus $Gpus -DataDir $v.Data -ResultsDir $v.Res }
        }
    }
    $main = $variants[0]
    if ($Steps -contains "baselines") {
        foreach ($mode in @("local", "centralized")) {
            Invoke-Step "baseline $mode seed 0" { & $py baselines/multidataset_baselines.py --mode $mode --data-dir $main.Data --results-dir $main.Res --epochs $baseEpochs --seed 0 }
        }
    }
    if ($Steps -contains "eval") {
        foreach ($v in $variants) {
            $ck = Join-Path $v.Res "fl/*_best.pt"
            if (Get-ChildItem $ck -ErrorAction SilentlyContinue) {
                Invoke-Step "eval $($v.Name)" { & $py analysis/evaluate_multidataset.py --data-dir $v.Data --results-dir $v.Res --checkpoint $ck }
            }
        }
    }
} finally { Pop-Location }
