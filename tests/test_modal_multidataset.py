"""Kiểm thử lệnh chạy, smoke gate inputs và tính toàn vẹn bundle; không gọi Modal."""
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fl_ddos import modal_multidataset_jobs as jobs

ROOT = Path(__file__).resolve().parent.parent


class ModalJobTests(unittest.TestCase):
    def setUp(self):
        self.cfg = jobs.read_json(ROOT / "configs/multidataset.json")

    def test_matrix_and_training_budget(self):
        main = jobs.make_specs(self.cfg, "main")
        smoke = jobs.make_specs(self.cfg, "smoke")
        self.assertEqual(len(main), 4)
        self.assertEqual(len(smoke), 4)
        self.assertEqual(len({s["name"] for s in main}), 4)
        self.assertEqual({(s["variant"], s["seed"]) for s in main if s["kind"] == "fl"},
                         {(v, seed) for v in ("das", "all") for seed in (0,)})
        self.assertTrue(all(s["rounds"] == 30 and s["epochs"] == 5 for s in main))
        self.assertEqual({s["baseline_epochs"] for s in main if s["kind"] != "fl"}, {150})
        self.assertEqual({s["baseline_epochs"] for s in smoke if s["kind"] != "fl"}, {2})

    def test_commands_select_correct_pipeline_and_best_checkpoint(self):
        for spec in jobs.make_specs(self.cfg, "main"):
            cmds = jobs.commands(spec, "/vol/data", "/tmp/output", "python")
            if spec["kind"] == "fl":
                self.assertIn("scenario='multidataset'", cmds[0][-1])
                self.assertIn("num-clients=2", cmds[0][-1])
                self.assertIn("num-supernodes=2", cmds[0][-3])
                self.assertEqual(cmds[1][-1], "/tmp/output/fl/*_best.pt")
                self.assertNotIn("*_last.pt", " ".join(cmds[1]))
            else:
                self.assertEqual(cmds[0][1], "baselines/multidataset_baselines.py")
                self.assertIn("150", cmds[0])

    def test_artifact_paths(self):
        for name in ("../secret", "/secret", "D:/secret", "a\\b"):
            with self.assertRaises(ValueError):
                jobs.safe_relative(name)
        self.assertEqual(jobs.data_name("main", "all"), "main_all")

    def test_bundle_detects_corruption_and_split_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for profile in ("smoke", "main"):
                for variant in ("das", "all"):
                    folder = root / jobs.data_name(profile, variant)
                    folder.mkdir()
                    hashes = {"schema": variant, "preprocessor": profile + variant, "split": profile}
                    clients = [{"partition_id": i, "dataset_id": ds, "train_file": f"multidataset/train{i}.parquet",
                                "val_file": f"multidataset/val{i}.parquet", "test_file": f"test/{ds}.parquet"}
                               for i, ds in jobs.DATASETS.items()]
                    metadata = {"pipeline": "multidataset_v1", "sampling_policy": jobs.POLICY,
                                "profile": profile, "feature_set": variant, "hashes": hashes}
                    manifest = {"hashes": hashes, "clients": clients}
                    quality = {"independence": {}}
                    for name, body in (("features.json", metadata), ("dataset_manifest.json", manifest),
                                       ("quality_report.json", quality)):
                        (folder / name).write_text(json.dumps(body), encoding="utf-8")
                    extras = ["prep_params.json", "split_manifest.parquet", "sampling_report.md",
                              "feature_selection.csv", "multidataset/class_weights.json"]
                    extras += [c[k] for c in clients for k in ("train_file", "val_file", "test_file")]
                    for name in extras:
                        path = folder / name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(b"test artifact")
            bundle = jobs.build_bundle(root)
            jobs.verify_bundle(root, bundle)
            self.assertEqual(bundle, jobs.build_bundle(root))
            tampered = copy.deepcopy(bundle)
            tampered["policy"] = "different"
            with self.assertRaises(ValueError):
                jobs.verify_bundle(root, tampered)
            artifact = root / "main/test/unsw_nb15.parquet"
            artifact.write_bytes(b"corruption")
            with self.assertRaises(ValueError):
                jobs.verify_bundle(root, bundle)
            f = root / "main_all/features.json"
            md = jobs.read_json(f)
            md["hashes"]["split"] = "different"
            f.write_text(json.dumps(md), encoding="utf-8")
            with self.assertRaises(ValueError):
                jobs.build_bundle(root)


@unittest.skipUnless(importlib.util.find_spec("modal"), "Modal SDK là dependency cloud tùy chọn")
class SmokeGateTests(unittest.TestCase):
    def run_controller(self, fail_smoke):
        import modal_multidataset as cloud
        calls = []

        def mapped(specs, **kwargs):
            calls.append(specs[0]["profile"])
            for i, spec in enumerate(specs):
                yield {**spec, "state": "failed" if fail_smoke and i == 0 else "completed"}

        with tempfile.TemporaryDirectory() as tmp, patch.object(cloud, "VOL", tmp), \
                patch.object(cloud, "vol", SimpleNamespace(reload=lambda: None, commit=lambda: None)), \
                patch.object(cloud, "verify_bundle", lambda *args: None), \
                patch.object(cloud, "experiment", SimpleNamespace(map=mapped)), \
                patch.object(cloud, "report", SimpleNamespace(remote=lambda *args: None)):
            cfg = jobs.read_json(ROOT / "configs/multidataset.json")
            result = cloud.run_all.local({"bundle_id": "test"}, cfg, "test_run")
        return result, calls

    def test_failed_smoke_prevents_main(self):
        result, calls = self.run_controller(True)
        self.assertEqual(result["state"], "failed")
        self.assertEqual(calls, ["smoke"])

    def test_completed_smoke_starts_main(self):
        result, calls = self.run_controller(False)
        self.assertEqual(result["state"], "completed")
        self.assertEqual(calls, ["smoke", "main"])
        self.assertEqual(len(result["jobs"]), 8)


if __name__ == "__main__":
    unittest.main()
