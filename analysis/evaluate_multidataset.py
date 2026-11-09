"""Đánh giá cuối multidataset_v1: một best checkpoint -> hai tập test (CIC / UNSW).

  python analysis/evaluate_multidataset.py --data-dir data_paper_multi/smoke \
      --results-dir results_multidataset/smoke --checkpoint results_multidataset/smoke/fl/multidataset_resvgg_swin_seed0_best.pt
  python analysis/evaluate_multidataset.py --data-dir data_paper_multi/main --results-dir results_multidataset/main \
      --checkpoint "results_multidataset/main/fl/*_best.pt"          # nhiều checkpoint (glob)

Ghi (ghi đè dòng của cùng checkpoint hash): evaluation_by_dataset.csv, per_class.csv, per_original_label.csv,
confusion.csv, figures/confusion_*.png, summary.md.
"""
import argparse
import glob
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fl_ddos.multidataset_eval import evaluate_checkpoint  # noqa: E402


def main():
    for s in (sys.stdout, sys.stderr):  # console Windows (cp1252) không in được tiếng Việt
        s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--checkpoint", required=True, help="đường dẫn hoặc glob tới *_best.pt")
    ap.add_argument("--threshold", type=float, default=0.5, help="cố định trong v1, không chọn theo test")
    a = ap.parse_args()
    files = sorted(glob.glob(a.checkpoint)) or [a.checkpoint]
    for f in files:
        if not Path(f).exists():
            sys.exit(f"Không thấy checkpoint {f}")
        res = evaluate_checkpoint(f, Path(a.data_dir).resolve(), Path(a.results_dir).resolve(), a.threshold)
        cols = ["dataset_id", "n", "acc", "f1_macro_present", "attack_f1", "attack_far_benign", "dos_f1"]
        print(f"\n{Path(f).name} (vòng {res['selected_round'].iloc[0]}):")
        print(res[cols].to_string(index=False))
    print(f"\n-> {Path(a.results_dir) / 'summary.md'}")


if __name__ == "__main__":
    main()
