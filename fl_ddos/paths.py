"""Đường dẫn tuyệt đối dùng chung cho toàn dự án.

Có thể ghi đè bằng biến môi trường:
  FL_DDOS_DATA        thư mục data/ (chứa features.json, scaler.json, S*/, test_day2.parquet)
  FL_DDOS_RESULTS     thư mục results/
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("FL_DDOS_DATA", ROOT / "data"))
RESULTS = Path(os.environ.get("FL_DDOS_RESULTS", ROOT / "results"))

FEATURES_JSON = DATA / "features.json"
SCALER_JSON = DATA / "scaler.json"
TRAIN_POOL = DATA / "train_pool.parquet"
TEST_DAY2 = DATA / "test_day2.parquet"


def configure(data_dir: str = "", results_dir: str = "") -> None:
    """Ghi đè thư mục data/results lúc chạy (run-config `data-dir` của Flower)."""
    global DATA, RESULTS, FEATURES_JSON, SCALER_JSON, TRAIN_POOL, TEST_DAY2
    if data_dir:
        DATA = Path(data_dir)
        FEATURES_JSON, SCALER_JSON = DATA / "features.json", DATA / "scaler.json"
        TRAIN_POOL, TEST_DAY2 = DATA / "train_pool.parquet", DATA / "test_day2.parquet"
    if results_dir:
        RESULTS = Path(results_dir)


def client_file(scenario: str, pid: int) -> Path:
    """pid bắt đầu từ 0 (partition-id của Flower), file đặt tên client_1..K."""
    return DATA / scenario / f"client_{pid + 1}.parquet"


def val_file(scenario: str, pid: int) -> Path:
    """Validation chia sẵn của pipeline multidataset_v1: val_client_1..K.parquet."""
    return DATA / scenario / f"val_client_{pid + 1}.parquet"


def multi_test_file(dataset_id: str) -> Path:
    return DATA / "test" / f"{dataset_id}.parquet"
