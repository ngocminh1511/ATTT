"""Build the offline deck; --refresh-data reads only the agreed experiment artifacts."""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_AVG = "20261109_161229_a7ff36"
RUN_PROX = "20261109_193340_f712a4"
SOURCES = ["cicddos2019", "unsw_nb15"]
CLASSES = ["BENIGN", "DOS_DDOS", "OTHER_ATTACK"]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def csv_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key, val in row.items():
            if val == "":
                row[key] = None
            elif val is not None:
                try:
                    row[key] = float(val) if any(c in val.lower() for c in ".e") else int(val)
                except ValueError:
                    pass
    return rows


def method_id(name):
    if name.startswith("Local-only[cic"):
        return "local_cic"
    if name.startswith("Local-only[unsw"):
        return "local_unsw"
    if name.startswith("Centralized"):
        return "central"
    if "FedProx" in name:
        return "prox"
    return "all" if "all-continuous" in name else "das"


def training_histogram(prep):
    """Recover log1p duration from saved AFN train inputs, without opening raw data."""
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("--refresh-data cần pandas: chạy bằng .venv/Scripts/python.exe") from exc
    col = prep["afn"]["columns"].index("duration_s")
    values = []
    for client in (1, 2):
        frame = pd.read_parquet(ROOT / f"data_paper_multi/main/multidataset/client_{client}.parquet")
        group_names = ["tcp", "udp", "icmp", "other"]
        groups = frame[[f"proto_{g}" for g in group_names]].values.argmax(axis=1)
        for z, group, missing in zip(frame.duration_s, groups, frame.duration_missing):
            if missing:
                continue
            stats = prep["afn"]["groups"][group_names[group]]
            values.append(max(0.0, float(z) * stats["scale"][col] + stats["mean"][col]))
    raw = [math.expm1(x) for x in values]

    def histogram(xs):
        maximum = max(xs) or 1
        bins = [0] * 20
        for x in xs:
            bins[min(19, int(x / maximum * 20))] += 1
        return {"counts": bins, "max": maximum, "n": len(xs)}

    return {"raw": histogram(raw), "log": histogram(values), "feature": "duration_s",
            "note": "200.000 mẫu train đã chọn. Tái dựng log1p(duration_s) từ AFN lưu sẵn; có sai số float32. Không đọc test."}


def collect_snapshot():
    used_files = []

    def load(rel):
        used_files.append(rel)
        return read_json(ROOT / rel)

    das = load("data_paper_multi/main/features.json")
    all_features = load("data_paper_multi/main_all/features.json")
    quality = load("data_paper_multi/main/quality_report.json")
    prep = load("data_paper_multi/main/prep_params.json")
    manifest = load("data_paper_multi/main/dataset_manifest.json")
    weights = load("data_paper_multi/main/multidataset/class_weights.json")
    dataset_catalog = load("presentation/data/datasets.json")
    states = [load(f"results_modal_multidataset/{run}/status_snapshot.json") for run in (RUN_AVG, RUN_PROX)]
    if any(s["state"] != "completed" for s in states):
        raise ValueError("Chỉ dùng run completed")
    if states[0]["bundle_id"] != states[1]["bundle_id"]:
        raise ValueError("FedAvg/FedProx không cùng bundle")
    if das["hashes"]["split"] != all_features["hashes"]["split"]:
        raise ValueError("ALL/DAS khác subset")
    methods = {}
    for run, variant in [(RUN_AVG, "das"), (RUN_AVG, "all"), (RUN_PROX, "das")]:
        base = f"results_modal_multidataset/{run}/main/{variant}"
        for file, destination in [("evaluation_by_dataset.csv", "evaluation"), ("per_class.csv", "per_class"),
                                  ("confusion.csv", "confusion"), ("per_original_label.csv", "original_labels")]:
            rel = f"{base}/{file}"
            used_files.append(rel)
            for row in csv_rows(ROOT / rel):
                key = method_id(row["method"])
                method = methods.setdefault(key, {"run": run, "variant": variant, "label": row["method"],
                                                  "evaluation": [], "per_class": [], "confusion": [],
                                                  "original_labels": [], "rounds": []})
                method[destination].append(row)
        for file in sorted((ROOT / base / "fl").glob("*_rounds.csv")):
            rel = file.relative_to(ROOT).as_posix()
            used_files.append(rel)
            key = "prox" if run == RUN_PROX else variant
            methods[key]["rounds"] = csv_rows(file)
    feature_file = "data_paper_multi/main/feature_selection.csv"
    used_files.append(feature_file)
    # Record the two train inputs used only for the duration histogram.
    used_files += [f"data_paper_multi/main/multidataset/client_{k}.parquet" for k in (1, 2)]
    evidence = [{"path": rel, "sha256": hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()}
                for rel in used_files]
    snapshot = {"version": 1, "pipeline": das["pipeline"], "bundle_id": states[0]["bundle_id"],
                "sources": SOURCES, "classes": CLASSES, "features": {"das": das, "all": all_features},
                "quality": quality, "clients": manifest["clients"], "class_weights": weights,
                "dataset_catalog": dataset_catalog,
                "das_config": prep["das"], "afn": prep["afn"], "label_map": prep["label_map"],
                "feature_ranking": csv_rows(ROOT / feature_file), "methods": methods,
                "runs": [{"run_id": s["run_id"], "state": s["state"], "bundle_id": s["bundle_id"],
                          "jobs": s["jobs"]} for s in states],
                "histogram": training_histogram(prep), "evidence": evidence,
                "references": [{"title": "FedAvg · McMahan et al. (2017)",
                                "url": "https://proceedings.mlr.press/v54/mcmahan17a.html"},
                               {"title": "FedProx · Li et al. (2020)", "url": "https://arxiv.org/abs/1812.06127"},
                               {"title": "Phương pháp tham khảo · Alshdadi et al. (2025)",
                                "url": "https://doi.org/10.3390/fi17020088"}]}
    validate_snapshot(snapshot)
    return snapshot


def validate_snapshot(data):
    catalog = data["dataset_catalog"]
    cic, unsw = catalog["cicddos2019"], catalog["unsw_nb15"]
    if sum(day["rows"] for day in cic["days"]) != cic["local_rows"]:
        raise ValueError("Tổng mẫu CIC hai ngày không khớp")
    if any(sum(cic["label_counts"][day["date"]].values()) != day["rows"] for day in cic["days"]):
        raise ValueError("Số mẫu nhãn CIC không khớp ngày")
    if sum(split["rows"] for split in unsw["splits"]) != unsw["local_rows"]:
        raise ValueError("Tổng mẫu hai CSV UNSW không khớp")
    if any(sum(split["labels"].values()) != split["rows"] for split in unsw["splits"]):
        raise ValueError("Số mẫu nhãn UNSW không khớp tập")
    if (cic["local_measurements"] + 1 != cic["local_columns"] or
            unsw["local_measurements"] + 3 != unsw["local_columns"]):
        raise ValueError("Số trường đo / nhãn không khớp header")
    if len(data["runs"]) != 2 or any(run["state"] != "completed" or run["bundle_id"] != data["bundle_id"]
                                    for run in data["runs"]):
        raise ValueError("Hai run phải completed và cùng bundle")
    if any(job["state"] != "completed" for run in data["runs"] for job in run["jobs"] if job["profile"] == "main"):
        raise ValueError("Không sử dụng main job chưa completed")
    if set(data["methods"]) != {"local_cic", "local_unsw", "central", "all", "das", "prox"}:
        raise ValueError("Cần đủ 6 mô hình đối chứng")
    if data["features"]["das"]["hashes"]["split"] != data["features"]["all"]["hashes"]["split"]:
        raise ValueError("ALL/DAS phải cùng split")
    expected = {"all": (0.4804425104354843, 24), "das": (0.5570728655285542, 4),
                "prox": (0.6920483367469703, 18), "central": (0.6079110395083358, 111)}
    for key, method in data["methods"].items():
        index = {r["dataset_id"]: r for r in method["evaluation"]}
        if len(index) != 5:
            raise ValueError(f"{key}: thiếu hoặc trùng nguồn đánh giá")
        for source in SOURCES:
            row = index[source]
            cm = [[next(r["n"] for r in method["confusion"] if r["dataset_id"] == source
                        and r["true"] == a and r["pred"] == b) for b in CLASSES] for a in CLASSES]
            total = sum(map(sum, cm))
            if total != row["n"] or total != 50000:
                raise ValueError(f"{key}/{source}: số mẫu confusion không khớp")
            f1s = []
            for i, label in enumerate(CLASSES):
                support, predictions = sum(cm[i]), sum(r[i] for r in cm)
                per = next(r for r in method["per_class"] if r["dataset_id"] == source and r["class"] == label)
                if support != per["support"]:
                    raise ValueError("Support từng lớp không khớp")
                if support:
                    f1 = 2 * cm[i][i] / (support + predictions)
                    f1s.append(f1)
                    if not math.isclose(f1, per["f1"], abs_tol=1e-12):
                        raise ValueError("F1 từng lớp không khớp confusion")
                elif per["f1"] is not None:
                    raise ValueError("Lớp vắng phải là N/A")
            if not math.isclose(sum(f1s) / len(f1s), row["f1_macro_present"], abs_tol=1e-12):
                raise ValueError("Macro F1 không khớp confusion")
            if not math.isclose(sum(cm[i][i] for i in range(3)) / total, row["acc"], abs_tol=1e-12):
                raise ValueError("Accuracy không khớp confusion")
        for metric in ("acc", "f1_macro_present", "dos_f1", "attack_far_benign"):
            mean = sum(index[s][metric] for s in SOURCES) / 2
            if not math.isclose(mean, index["mean_over_sources"][metric], abs_tol=1e-12):
                raise ValueError("Trung bình nguồn không khớp")
        if key in expected:
            score, selected = expected[key]
            if not math.isclose(index["mean_over_sources"]["f1_macro_present"], score, abs_tol=1e-12):
                raise ValueError(f"{key}: kết quả đã thay đổi; rà lại diễn giải trước khi cập nhật")
            if index["mean_over_sources"]["selected_round"] != selected:
                raise ValueError(f"{key}: checkpoint đã thay đổi")
        if method["rounds"]:
            if [r["round"] for r in method["rounds"]] != list(range(1, 31)):
                raise ValueError("Cần đủ 30 vòng")
            best = max(method["rounds"], key=lambda r: r["val_score"])
            if best["round"] != index["mean_over_sources"]["selected_round"]:
                raise ValueError("Best checkpoint không khớp validation")
    return True


def validate_content(content):
    slides, stages = content["slides"], content["stages"]
    if len(stages) != 9 or len(slides) != 39:
        raise ValueError("Cần 9 giai đoạn, 33 trang chính và 6 phụ lục")
    if len({s["id"] for s in slides}) != len(slides):
        raise ValueError("ID slide bị trùng")
    known = {s["id"] for s in stages} | {"home", "appendix"}
    for slide in slides:
        if slide["stage"] not in known:
            raise ValueError("Giai đoạn không tồn tại")
        for field in ("title", "message", "view", "goal", "speech", "point", "transition", "sources"):
            if not slide.get(field):
                raise ValueError(f"{slide['id']}: thiếu {field}")


def script_markdown(content, data):
    lines = ["# Kịch bản thuyết trình — Học liên kết phát hiện tấn công mạng", "",
             "Sinh từ `src/slides.json`; chỉnh nguồn rồi chạy `python presentation/build.py`.", "",
             "Pipeline: dữ liệu → làm sạch → chia tập → tạo đặc trưng → chuẩn hóa → DAS → huấn luyện → kết quả → kết luận.", "",
             "Các giá trị thực nghiệm: profile main, seed 0; F1 tổng hợp là trung bình đều F1-macro-present hai nguồn, trừ khi ghi khác.", ""]
    stage_names = {s["id"]: s["title"] for s in content["stages"]} | {"home": "Pipeline", "appendix": "Phụ lục"}
    for slide in content["slides"]:
        lines += [f"## {slide['number']} · {slide['title']}", "",
                  f"**Giai đoạn:** {stage_names[slide['stage']]} · **Trạng thái:** {'Đang bật' if slide.get('enabled', True) else 'Đã tắt'}", "",
                  f"**Thông điệp:** {slide['message']}", "", f"**Mục tiêu:** {slide['goal']}", "",
                  "**Nội dung trên slide:**", ""]
        lines += [f"- {point}" for point in slide.get("bullets", [])]
        lines += ["", "**Lời trình bày:**", "", slide["speech"], "",
                  f"**Chỉ vào hình:** {slide['point']}", "", f"**Chuyển ý:** {slide['transition']}", ""]
        if slide.get("defense"):
            lines += [f"**Nếu thầy hỏi:** {slide['defense']}", ""]
        lines += ["**Nguồn:** " + "; ".join(slide["sources"]), ""]
    lines += ["## Tài liệu phương pháp", ""] + [f"- [{r['title']}]({r['url']})" for r in data["references"]]
    return "\n".join(lines) + "\n"


def build(refresh=False, check=False):
    snapshot_path = HERE / "data/snapshot.json"
    data = collect_snapshot() if refresh else read_json(snapshot_path)
    validate_snapshot(data)
    content = read_json(HERE / "src/slides.json")
    validate_content(content)
    if check:
        return len(content["slides"])
    if refresh:
        write_json(snapshot_path, data)
    # The projected deck contains audience content only. Speaker directions stay in kich_ban.md.
    visible_fields = ("id", "number", "stage", "enabled", "view", "title", "message")
    projected = {"title": content["title"],
                 "stages": [{k: v for k, v in stage.items() if k != "output"} for stage in content["stages"]],
                 "slides": [{k: slide[k] for k in visible_fields} for slide in content["slides"]]}
    image_path = HERE / "assets/federated-network.png"
    assets = {"network": "data:image/png;base64," + base64.b64encode(image_path.read_bytes()).decode("ascii")}
    payload = json.dumps({"content": projected, "data": data, "assets": assets}, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    html = (HERE / "src/shell.html").read_text(encoding="utf-8")
    replacements = {"/* STYLES */": (HERE / "src/styles.css").read_text(encoding="utf-8"),
                    "__PAYLOAD__": payload,
                    "/* VISUALS */": (HERE / "src/visuals.js").read_text(encoding="utf-8"),
                    "/* APP */": (HERE / "src/app.js").read_text(encoding="utf-8")}
    for token, value in replacements.items():
        if html.count(token) != 1:
            raise ValueError(f"Template cần đúng một {token}")
        html = html.replace(token, value)
    (HERE / "index.html").write_text(html, encoding="utf-8")
    (HERE / "kich_ban.md").write_text(script_markdown(content, data), encoding="utf-8")
    return len(content["slides"])


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-data", action="store_true")
    parser.add_argument("--check", action="store_true", help="Kiểm tra nội dung và dữ liệu, không ghi file")
    args = parser.parse_args()
    count = build(args.refresh_data, args.check)
    print(f"OK: {count} trang (33 chính + 6 phụ lục); {'kiểm tra' if args.check else 'đã tạo index.html và kich_ban.md'}")
