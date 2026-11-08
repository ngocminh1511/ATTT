"""CLI mỏng cho pipeline multidataset_v1 (logic nằm trong fl_ddos/multidataset_prep.py).

  python prepare/multidataset_pipeline.py --config configs/multidataset.json --profile smoke
  python prepare/multidataset_pipeline.py --profile main
  python prepare/multidataset_pipeline.py --profile main --feature-set all     # đối chứng không DAS -> main_all/

Output: data_paper_multi/{profile}[_all]/ (features.json, prep_params.json, dataset_manifest.json,
split_manifest.parquet, quality_report.json, feature_selection.csv, multidataset/, test/).
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fl_ddos.multidataset_prep import PrepError, load_config, prepare_multidataset  # noqa: E402


def main():
    for s in (sys.stdout, sys.stderr):  # console Windows (cp1252) không in được tiếng Việt
        s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/multidataset.json")
    ap.add_argument("--profile", choices=["smoke", "main"], default="smoke")
    ap.add_argument("--feature-set", choices=["das", "all"], default="das")
    ap.add_argument("--out", default="", help="mặc định data_paper_multi/{profile}[_all]")
    a = ap.parse_args()
    cfg_path = Path(a.config) if Path(a.config).is_absolute() else ROOT / a.config
    try:
        res = prepare_multidataset(load_config(cfg_path), a.profile, ROOT, a.out or None, a.feature_set)
    except PrepError as e:
        sys.exit(f"[multidataset] DỪNG: {e}")
    print(f"\nF = {len(res['features'])} cột: {res['features']}")
    for c in res["clients"]:
        print(f"  client {c['client']} ({c['dataset_id']}): train {c['n_train']}, val {c['n_val']}, test {c['n_test']}")


if __name__ == "__main__":
    main()
