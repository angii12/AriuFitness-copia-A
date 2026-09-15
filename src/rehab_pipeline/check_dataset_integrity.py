import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def load_split(path: Path):
    kp = np.load(path / "keypoints.npy")
    ang = np.load(path / "angles.npy")
    y = np.load(path / "labels.npy")
    meta = pd.read_csv(path / "windows_metadata.csv")

    if not (len(kp) == len(ang) == len(y) == len(meta)):
        raise ValueError(f"Dataset incoerente: {path}")
    if "rep_uid" not in meta.columns:
        raise ValueError(f"{path}: manca rep_uid")
    return kp, ang, y, meta


def main():
    parser = argparse.ArgumentParser(description="Controlla coerenza e leakage train/validation.")
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()

    _, _, train_y, train_meta = load_split(args.root / "train")
    _, _, val_y, val_meta = load_split(args.root / "validation")

    train_reps = set(train_meta["rep_uid"].astype(str))
    val_reps = set(val_meta["rep_uid"].astype(str))
    overlap_reps = sorted(train_reps & val_reps)

    train_subjects = set(train_meta.get("subject_id", pd.Series(dtype=str)).dropna().astype(str))
    val_subjects = set(val_meta.get("subject_id", pd.Series(dtype=str)).dropna().astype(str))
    overlap_subjects = sorted(train_subjects & val_subjects)

    train_sources = set(train_meta.get("source_video_id", pd.Series(dtype=str)).dropna().astype(str))
    val_sources = set(val_meta.get("source_video_id", pd.Series(dtype=str)).dropna().astype(str))
    overlap_sources = sorted(train_sources & val_sources)

    result = {
        "root": str(args.root),
        "train_windows": int(len(train_y)),
        "validation_windows": int(len(val_y)),
        "train_positive_windows": int(np.sum(train_y == 1)),
        "train_negative_windows": int(np.sum(train_y == 0)),
        "validation_positive_windows": int(np.sum(val_y == 1)),
        "validation_negative_windows": int(np.sum(val_y == 0)),
        "train_reps": int(len(train_reps)),
        "validation_reps": int(len(val_reps)),
        "rep_uid_overlap": overlap_reps,
        "source_video_overlap": overlap_sources,
        "subject_overlap": overlap_subjects,
        "rep_uid_leakage_free": len(overlap_reps) == 0,
        "source_video_leakage_free": len(overlap_sources) == 0,
        "subject_leakage_free": len(overlap_subjects) == 0,
    }
    print(json.dumps(result, indent=2))
    if overlap_reps or overlap_sources or overlap_subjects:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
