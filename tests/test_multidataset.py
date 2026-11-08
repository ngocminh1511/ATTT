"""Kiểm thử pipeline multidataset_v1 bằng fixture nhỏ (kế hoạch mục 12). Không tải dữ liệu thật.

  .venv\\Scripts\\python.exe -m unittest discover -s tests -v
"""
import json
import shutil
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixtures_multidataset as fx  # noqa: E402
from fl_ddos import dataset_adapters as ad  # noqa: E402
from fl_ddos.multidataset_prep import dump_json, read_json  # noqa: E402
from fl_ddos import multidataset_prep as mp  # noqa: E402
from fl_ddos import paths  # noqa: E402


def prepare(root, cfg, profile="tiny", feature_set="das", out=None):
    return mp.prepare_multidataset(cfg, profile, root, out or root / f"out_{profile}_{feature_set}", feature_set)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.cfg = fx.base_config()

    def test_cic_labels_and_units(self):
        raw = pd.DataFrame({"Protocol": [6, 17, 0], "Flow Duration": [1_000_000, 500_000, 0],
                            "Total Fwd Packets": [3, 2, 1], "Total Backward Packets": [1, 0, 0],
                            "Label": ["Benign", "DrDoS_DNS", "Portmap"]})
        issues, drops = Counter(), Counter()
        df = ad.cic_frame(raw, "x", 0, self.cfg, issues, drops)
        self.assertEqual(df["y"].tolist(), [0, 1, 1])  # Portmap giữ nhãn gốc, thuộc DOS_DDOS, không thành PortScan
        self.assertEqual(df["duration_s"].tolist(), [1.0, 0.5, 0.0])
        self.assertEqual(df["protocol_group"].tolist(), ["tcp", "udp", "other"])
        feats = mp.derive(df)
        self.assertEqual(feats["flow_packets_s"].iloc[0], 4.0)  # gói/giây
        self.assertTrue(np.isnan(feats["flow_packets_s"].iloc[2]))  # duration = 0 -> rate missing, không Inf
        self.assertEqual(feats["duration_zero"].tolist(), [0, 0, 1])
        self.assertFalse(issues)

    def test_unknown_label_reported(self):
        raw = pd.DataFrame({"Protocol": [6], "Flow Duration": [1], "Total Fwd Packets": [1],
                            "Total Backward Packets": [1], "Label": ["PortScan"]})
        issues = Counter()
        df = ad.cic_frame(raw, "x", 0, self.cfg, issues, Counter())
        self.assertEqual(df["y"].tolist(), [ad.UNKNOWN])
        self.assertIn(("cicddos2019", "unknown_label:PortScan"), issues)

    def test_iot_label_rules(self):
        lab = pd.Series(["Benign", "Malicious", "Malicious", "Malicious", "Malicious", "Benign", "Malicious",
                         "Malicious"])
        det = pd.Series(["-", "DDoS", "PartOfAHorizontalPortScan", "C&C-HeartBeat-FileDownload", "Okiru-Attack",
                         "DDoS", "Weird", "-"])
        issues = Counter()
        y = ad.map_iot_labels(lab, det, self.cfg, issues)
        self.assertEqual(y.tolist(), [0, 1, 2, 2, 2, -1, -1, -1])
        self.assertEqual(set(k[1].split(":")[0] for k in issues),
                         {"benign_with_detailed", "unknown_detailed", "malicious_without_detailed"})

    def test_zeek_parser_both_layouts(self):
        rng = np.random.default_rng(0)
        for merged in (True, False):
            import io
            fh = io.BytesIO(fx.zeek_log(rng, 50, merged))
            issues, drops = Counter(), Counter()
            df = pd.concat(list(ad.iter_zeek_file(fh, "cap", self.cfg, issues, drops, chunksize=16)))
            self.assertEqual(len(df) + sum(drops.values()), 50)  # dòng '#close' không bị đọc thành dữ liệu
            self.assertFalse(issues)
            self.assertEqual(sorted(df["y"].unique()), [0, 1, 2])
            self.assertTrue(df["duration_s"].isna().any())  # '-' -> missing, không phải 0

    def test_unsw_html_and_bom(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.csv"
            p.write_bytes(b"<!DOCTYPE html><html><body>login</body></html>")
            with self.assertRaises(ValueError):
                ad.read_unsw_csv(p)
            fx.unsw_frame(np.random.default_rng(0), 10, 1).to_csv(p, index=False, encoding="utf-8-sig")
            self.assertEqual(ad.read_unsw_csv(p).columns[0], "id")


class UnitTests(unittest.TestCase):
    def test_class_weights_absent(self):
        w = mp.class_weights(np.array([0, 0, 0, 1]), 3)
        self.assertEqual(w[2], 0.0)
        self.assertAlmostEqual(np.mean(w[:2]), 1.0)

    def test_quota(self):
        q = mp.allocate_quota({0: 9000, 1: 990, 2: 10}, {0: 9000, 1: 990, 2: 10}, 100)
        self.assertEqual(sum(q.values()), 100)
        self.assertGreaterEqual(q[2], 1)
        q = mp.allocate_quota({0: 50, 1: 5}, {0: 50, 1: 5}, 100)
        self.assertEqual(q, {0: 50, 1: 5})  # ít hơn giới hạn -> giữ toàn bộ, không nhân bản
        q = mp.allocate_quota({0: 1000, 1: 1000}, {0: 1000, 1: 10}, 100)
        self.assertEqual(q, {0: 90, 1: 10})  # lớp thiếu ứng viên -> phần còn lại chuyển cho lớp khác

    def test_das_tie_break_and_redundancy(self):
        rng = np.random.default_rng(0)
        y = rng.integers(0, 2, 500)
        x = y + rng.normal(0, .5, 500)
        X = np.c_[x, x, rng.normal(size=500), np.ones(500)]
        st = [mp.das_stats(X, y, 3)]
        sel, tab = mp.das_select(st, ["b_dup", "a_dup", "noise", "const"], 0.001, 0.9, 8)
        self.assertEqual(sel[0], "a_dup")  # hòa relevance -> theo tên cột
        t = tab.set_index("feature")
        self.assertTrue(t.loc["b_dup", "reason"].startswith("redundant_with:a_dup"))
        self.assertEqual(t.loc["const", "reason"], "constant")
        self.assertEqual(sel, mp.das_select(st, ["b_dup", "a_dup", "noise", "const"], 0.001, 0.9, 8)[0])

    def test_afn_missing_counts(self):
        x = np.array([[1.0, np.nan], [3.0, np.nan], [5.0, 2.0]])
        g = np.array(["tcp", "tcp", "udp"])
        afn = mp.aggregate_afn([mp.afn_stats(x[:2], g[:2]), mp.afn_stats(x[2:], g[2:])], ["a", "b"])
        self.assertEqual(afn["groups"]["__all__"]["n_valid"], [3, 1])
        self.assertEqual(afn["groups"]["tcp"]["mean"][1], 2.0)  # nhóm không có quan sát -> tham số global
        z = mp.apply_afn(x, g, afn)
        self.assertTrue(np.isfinite(z).all())
        self.assertEqual(z[0, 1], 0.0)  # missing -> mean -> 0
        self.assertEqual(afn["groups"]["udp"]["scale"][0], 1.0)  # phương sai 0 -> scale 1


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="mds_"))
        cls.cfg = fx.build(cls.tmp)
        cls.res = prepare(cls.tmp, cls.cfg)
        cls.out = Path(cls.res["out"])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_artifacts_same_schema(self):
        feats = read_json(self.out / "features.json")
        self.assertEqual(feats["pipeline"], "multidataset_v1")
        self.assertEqual(feats["classes"], ad.CLASSES)
        F = len(feats["features"])
        self.assertTrue(7 <= F <= 14)
        self.assertEqual(feats["features"][-6:], mp.FIXED)
        for k in (1, 2, 3):
            for name in (f"client_{k}", f"val_client_{k}"):
                df = pd.read_parquet(self.out / "multidataset" / f"{name}.parquet")
                self.assertEqual(list(df.columns[:F]), feats["features"])
                self.assertTrue(np.isfinite(df[feats["features"]].values).all())
                self.assertEqual(df[feats["features"]].dtypes.unique().tolist(), [np.float32])
                for col in ("dataset_id", "row_id", "original_label"):
                    self.assertNotIn(col, feats["features"])
        ds = read_json(self.out / "dataset_manifest.json")
        self.assertEqual({c["partition_id"]: c["dataset_id"] for c in ds["clients"]},
                         {0: "cicddos2019", 1: "unsw_nb15", 2: "iot23"})

    def test_cic_absent_class_ok(self):
        w = read_json(self.out / "multidataset" / "class_weights.json")
        self.assertEqual(w["client_1"][2], 0.0)  # CIC không có OTHER_ATTACK
        val = pd.read_parquet(self.out / "multidataset" / "val_client_1.parquet")
        self.assertNotIn(2, set(val["y"]))

    def test_split_constraints_and_reproducible(self):
        sm = pd.read_parquet(self.out / "split_manifest.parquet")
        for ds, g in sm.groupby("dataset_id"):
            tr, va = set(g.loc[g.split == "train", "group"]), set(g.loc[g.split == "val", "group"])
            self.assertFalse(tr & va, ds)
        iot = sm[sm.dataset_id == "iot23"]
        self.assertTrue((iot.groupby("capture_id")["split"].nunique() == 1).all())
        res2 = prepare(self.tmp, self.cfg, out=self.tmp / "again")
        self.assertEqual(res2["hashes"], self.res["hashes"])
        sm2 = pd.read_parquet(self.tmp / "again" / "split_manifest.parquet")
        pd.testing.assert_frame_equal(sm[sm.selected][["row_id", "split"]].reset_index(drop=True),
                                      sm2[sm2.selected][["row_id", "split"]].reset_index(drop=True))

    def test_fit_independent_of_test(self):
        sources = mp.load_sources(self.cfg, self.tmp)
        sources["unsw_nb15"]["pools"]["test"]["fwd_packets"] *= 1000  # đổi test
        res = mp.prepare_multidataset(self.cfg, "tiny", self.tmp, self.tmp / "changed_test", sources=sources)
        self.assertEqual(res["hashes"]["preprocessor"], self.res["hashes"]["preprocessor"])
        self.assertEqual(res["features"], self.res["features"])

    def test_transform_reload(self):
        prep = read_json(self.out / "prep_params.json")
        sources = mp.load_sources(self.cfg, self.tmp, only={"unsw_nb15"})
        raw = sources["unsw_nb15"]["pools"]["test"].head(50)
        a = mp.transform_canonical(raw, prep).values
        b = pd.read_parquet(self.out / "test" / "unsw_nb15.parquet")
        sm = pd.read_parquet(self.out / "split_manifest.parquet")
        self.assertTrue(len(b))
        np.testing.assert_allclose(a, mp.transform_canonical(raw, json.loads(json.dumps(prep))).values,
                                   rtol=1e-6, atol=1e-6)
        sel = b.set_index("row_id")
        common = [r for r in raw["row_id"] if r in sel.index]
        if common:
            idx = [raw["row_id"].tolist().index(r) for r in common]
            np.testing.assert_allclose(a[idx], sel.loc[common, prep["features"]].values, rtol=1e-6, atol=1e-6)
        self.assertGreater(len(sm), 0)

    def test_all_features_variant(self):
        res = prepare(self.tmp, self.cfg, feature_set="all")
        self.assertGreaterEqual(len(res["features"]), len(self.res["features"]))
        self.assertEqual(res["hashes"]["split"], self.res["hashes"]["split"])

    def test_unknown_label_blocks_artifacts(self):
        tmp = Path(tempfile.mkdtemp(prefix="mds_bad_"))
        try:
            cfg = fx.build(tmp, iot_extra_labels=[("Malicious", "Mystery")])
            with self.assertRaises(mp.PrepError):
                prepare(tmp, cfg)
            out = tmp / "out_tiny_das"
            self.assertTrue((out / "quality_report.json").exists())
            self.assertFalse((out / "features.json").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_loader_and_evaluation(self):
        from fl_ddos import task
        from fl_ddos.multidataset_eval import evaluate_checkpoint
        paths.configure(str(self.out), str(self.tmp / "results"))
        self.assertTrue(task.is_multi())
        self.assertFalse(task.uses_scaler())
        tr, va = task.load_local(2, "multidataset", 32)
        self.assertEqual(len(tr.dataset), len(pd.read_parquet(self.out / "multidataset" / "client_3.parquet")))
        self.assertEqual(len(va.dataset), len(pd.read_parquet(self.out / "multidataset" / "val_client_3.parquet")))
        self.assertEqual(task.mtb_weights(0, "multidataset")[2], 0.0)
        model = task.make_model("mlp", 0.1)
        md = task.meta()
        ck = {"arch": "mlp", "dropout": 0.1, "state_dict": model.state_dict(), "pipeline": md["pipeline"],
              "classes": md["classes"], "features": md["features"], "round": 1, "val_score": 0.5, "seed": 0,
              "hashes": md["hashes"], "kind": "best"}
        f = self.tmp / "ck.pt"
        torch.save(ck, f)
        res = evaluate_checkpoint(f, self.out, self.tmp / "results")
        per = res[res.dataset_id.isin(["cicddos2019", "unsw_nb15", "iot23"])]
        self.assertEqual(len(per), 3)
        self.assertEqual(per["checkpoint_sha256"].nunique(), 1)
        self.assertEqual(per.set_index("dataset_id").loc["cicddos2019", "support_OTHER_ATTACK"], 0)
        self.assertTrue((self.tmp / "results" / "summary.md").exists())
        bad = dict(ck, hashes={**md["hashes"], "preprocessor": "x"})
        torch.save(bad, f)
        with self.assertRaises(ValueError):
            evaluate_checkpoint(f, self.out, self.tmp / "results", write=False)


class LegacyLoaderTests(unittest.TestCase):
    def test_old_pipelines_still_load(self):
        from fl_ddos import task
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            dump_json({"features": ["a", "b"]}, d / "features.json")
            dump_json({"mean": [0, 0], "std": [1, 1]}, d / "scaler.json")
            paths.configure(str(d))
            self.assertTrue(task.uses_scaler())
            self.assertEqual(task.classes(), ["BENIGN", "DDoS"])
            json.dump({"pipeline": "paper", "features": ["a"], "classes": ["BENIGN", "X", "Y"]},
                      open(d / "features.json", "w"))
            import os
            os.utime(d / "features.json", (1, 2))  # đổi mtime -> cache phải đọc lại
            self.assertTrue(task.is_paper())
            self.assertFalse(task.uses_scaler())


class MetricTests(unittest.TestCase):
    def test_undefined_metrics_are_none(self):
        from fl_ddos.multidataset_eval import source_metrics
        y = np.zeros(5, dtype=int)
        P = np.tile([0.9, 0.05, 0.05], (5, 1))
        m, per, cm = source_metrics(y, P)
        self.assertIsNone(m["attack_roc_auc"])
        self.assertIsNone(m["attack_recall"])
        self.assertEqual(m["attack_far_benign"], 0.0)
        self.assertEqual(m["f1_macro_present"], 1.0)
        self.assertIsNone(per[2]["f1"])
        self.assertEqual(cm.shape, (3, 3))


class ServerTests(unittest.TestCase):
    def _strategy(self):
        from fl_ddos.multidataset_server import MultiSourceFedAvg
        s = MultiSourceFedAvg(min_train_nodes=3, min_evaluate_nodes=3, min_available_nodes=3)
        s._check_and_log_replies = lambda replies, is_train, validate=True: (list(replies), [])
        return s

    @staticmethod
    def _reply(pid, rnd, f1=0.5):
        return SimpleNamespace(content={"metrics": {"partition-id": pid, "server-round": rnd,
                                                    "eval_f1_macro_present": f1, "eval_acc": 0.5}})

    def test_pid_checks(self):
        from fl_ddos.multidataset_server import FLRunError
        s = self._strategy()
        with self.assertRaises(FLRunError):
            s.aggregate_evaluate(1, [self._reply(0, 1), self._reply(1, 1)])  # thiếu PID 2
        with self.assertRaises(FLRunError):
            s.aggregate_evaluate(1, [self._reply(0, 1), self._reply(1, 1), self._reply(1, 1)])  # trùng PID
        with self.assertRaises(FLRunError):
            s.aggregate_evaluate(2, [self._reply(0, 1), self._reply(1, 2), self._reply(2, 2)])  # round lệch
        with self.assertRaises(FLRunError):
            s.aggregate_evaluate(1, [self._reply(0, 1), self._reply(1, 1), self._reply(2, 1, float("nan"))])
        m = s.aggregate_evaluate(1, [self._reply(0, 1, .3), self._reply(1, 1, .6), self._reply(2, 1, .9)])
        self.assertAlmostEqual(m["val_score"], 0.6)
        self.assertAlmostEqual(s.val_by_round[1]["val_score"], 0.6)


if __name__ == "__main__":
    unittest.main()
