"""Costruisce un test binario semplice (un positivo + un negativo).

Per test con piu esercizi negativi usare prepare_multinegative_test.py.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def load_dataset(dataset_dir):
    dataset_dir = Path(dataset_dir)
    kp = np.load(dataset_dir / "keypoints.npy").astype(np.float32)
    ang = np.load(dataset_dir / "angles.npy").astype(np.float32)
    meta_path = dataset_dir / "windows_metadata.csv"
    meta = pd.read_csv(meta_path) if meta_path.exists() else pd.DataFrame({"sample_index": range(len(kp))})
    if not (len(kp) == len(ang) == len(meta)):
        raise ValueError(f"Dataset incoerente: {dataset_dir}")
    return kp, ang, meta


def main():
    parser = argparse.ArgumentParser(description="Costruisce un test binario semplice per qualsiasi target.")
    parser.add_argument("--target", required=True)
    parser.add_argument("--positive", required=True, type=Path)
    parser.add_argument("--negative", required=True, type=Path)
    parser.add_argument("--negative-name", default="negative")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    target = args.target.strip().lower()
    output = args.output or Path(f"output/binary_{target}/test")

    pos_kp, pos_ang, pos_meta = load_dataset(args.positive)
    neg_kp, neg_ang, neg_meta = load_dataset(args.negative)
    pos_y = np.ones(len(pos_kp), dtype=np.int64)
    neg_y = np.zeros(len(neg_kp), dtype=np.int64)

    pos_meta = pos_meta.copy()
    neg_meta = neg_meta.copy()
    pos_meta["binary_label"] = 1
    pos_meta["binary_class"] = f"positive_{target}"
    pos_meta["target_exercise"] = target
    pos_meta["test_source"] = target
    neg_meta["binary_label"] = 0
    neg_meta["binary_class"] = f"negative_non_{target}"
    neg_meta["target_exercise"] = target
    neg_meta["test_source"] = args.negative_name

    kp = np.concatenate([pos_kp, neg_kp], axis=0)
    ang = np.concatenate([pos_ang, neg_ang], axis=0)
    y = np.concatenate([pos_y, neg_y], axis=0)
    meta = pd.concat([pos_meta, neg_meta], ignore_index=True)

    rng = np.random.default_rng(args.seed)
    idx = np.arange(len(y))
    rng.shuffle(idx)
    kp, ang, y = kp[idx], ang[idx], y[idx]
    meta = meta.iloc[idx].reset_index(drop=True)

    output.mkdir(parents=True, exist_ok=True)
    np.save(output / "keypoints.npy", kp)
    np.save(output / "angles.npy", ang)
    np.save(output / "labels.npy", y)
    meta.to_csv(output / "windows_metadata.csv", index=False)

    summary = {
        "target": target,
        "positive_samples": int((y == 1).sum()),
        "negative_samples": int((y == 0).sum()),
        "total_samples": int(len(y)),
        "keypoints_shape": list(kp.shape),
        "angles_shape": list(ang.shape),
        "labels_shape": list(y.shape),
        "seed": int(args.seed),
    }
    (output / "test_dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
