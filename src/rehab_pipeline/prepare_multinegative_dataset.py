import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


SEED = 42
DEFAULT_NEGATIVE_REPS_PER_EXERCISE = 5


def _ensure_rep_uid(metadata: pd.DataFrame, dataset_dir: Path) -> pd.DataFrame:
    """Garantisce un identificatore stabile per ogni REP."""
    metadata = metadata.copy()

    if "rep_uid" in metadata.columns and metadata["rep_uid"].notna().all():
        metadata["rep_uid"] = metadata["rep_uid"].astype(str)
        if "split_group" not in metadata.columns:
            metadata["split_group"] = metadata["rep_uid"]
        return metadata

    if "rep" not in metadata.columns:
        raise ValueError(
            f"{dataset_dir}: mancano sia rep_uid sia rep; impossibile raggruppare "
            "le finestre per REP. Rigenera questo training_dataset.py."
        )

    if "source_video_id" in metadata.columns and metadata["source_video_id"].notna().any():
        source_ids = metadata["source_video_id"].fillna(dataset_dir.parent.name).astype(str)
    else:
        source_ids = pd.Series(
            [dataset_dir.parent.name] * len(metadata), index=metadata.index, dtype=str
        )

    reps = pd.to_numeric(metadata["rep"], errors="raise").astype(int)
    metadata["rep_uid"] = [
        f"{source}__rep_{rep:03d}" for source, rep in zip(source_ids, reps)
    ]
    metadata["split_group"] = metadata["rep_uid"]
    metadata["rep_uid_reconstructed"] = True
    return metadata


def load_dataset(dataset_dir: Path):
    dataset_dir = Path(dataset_dir)
    required = [
        dataset_dir / "keypoints.npy",
        dataset_dir / "angles.npy",
        dataset_dir / "windows_metadata.csv",
    ]
    for path in required:
        if not path.exists():
            raise FileNotFoundError(f"File richiesto non trovato: {path}")

    keypoints = np.load(required[0]).astype(np.float32)
    angles = np.load(required[1]).astype(np.float32)
    metadata = pd.read_csv(required[2])

    if not (len(keypoints) == len(angles) == len(metadata)):
        raise ValueError(
            f"Dataset incoerente: {dataset_dir} "
            f"(keypoints={len(keypoints)}, angles={len(angles)}, metadata={len(metadata)})"
        )

    if keypoints.ndim != 3 or keypoints.shape[1:] != (8, 36):
        raise ValueError(f"{dataset_dir}: shape keypoints non valida {keypoints.shape}")
    if angles.ndim != 3 or angles.shape[1:] != (8, 8):
        raise ValueError(f"{dataset_dir}: shape angles non valida {angles.shape}")
    if not np.isfinite(keypoints).all() or not np.isfinite(angles).all():
        raise ValueError(f"{dataset_dir}: NaN/inf nel dataset")

    metadata = _ensure_rep_uid(metadata, dataset_dir)
    return keypoints, angles, metadata


def choose_complete_reps(keypoints, angles, metadata, n_reps, seed):
    rep_uids = metadata["rep_uid"].dropna().astype(str).unique()
    if len(rep_uids) < n_reps:
        raise ValueError(
            f"Richieste {n_reps} REP ma disponibili soltanto {len(rep_uids)}."
        )

    rng = np.random.default_rng(seed)
    selected_rep_uids = rng.choice(rep_uids, size=n_reps, replace=False)
    mask = metadata["rep_uid"].astype(str).isin(selected_rep_uids).to_numpy()

    return (
        keypoints[mask],
        angles[mask],
        metadata.loc[mask].copy(),
        sorted(map(str, selected_rep_uids)),
    )


def prepare_split(
    split_name,
    target,
    positive_dir,
    negative_dirs,
    output_dir,
    n_negative_reps,
    seed,
):
    all_keypoints = []
    all_angles = []
    all_labels = []
    all_metadata = []

    pos_kp, pos_ang, pos_meta = load_dataset(positive_dir)
    pos_rep_uids = pos_meta["rep_uid"].astype(str).unique()

    pos_meta = pos_meta.copy()
    pos_meta["binary_label"] = 1
    pos_meta["binary_class"] = f"positive_{target}"
    pos_meta["target_exercise"] = target
    pos_meta["negative_source"] = ""
    pos_meta["split"] = split_name
    pos_meta["source_dataset"] = str(positive_dir)

    all_keypoints.append(pos_kp)
    all_angles.append(pos_ang)
    all_labels.append(np.ones(len(pos_kp), dtype=np.int64))
    all_metadata.append(pos_meta)

    summary = {
        "split": split_name,
        "target": target,
        "positive": {
            "dataset": str(positive_dir),
            "reps": int(len(pos_rep_uids)),
            "windows": int(len(pos_kp)),
        },
        "negatives": {},
    }

    for index, (exercise_name, dataset_dir) in enumerate(negative_dirs.items()):
        kp, ang, meta = load_dataset(dataset_dir)
        kp, ang, meta, selected_rep_uids = choose_complete_reps(
            kp,
            ang,
            meta,
            n_reps=n_negative_reps,
            seed=seed + index,
        )

        meta["binary_label"] = 0
        meta["binary_class"] = f"negative_non_{target}"
        meta["target_exercise"] = target
        meta["negative_source"] = exercise_name
        meta["split"] = split_name
        meta["source_dataset"] = str(dataset_dir)

        all_keypoints.append(kp)
        all_angles.append(ang)
        all_labels.append(np.zeros(len(kp), dtype=np.int64))
        all_metadata.append(meta)

        summary["negatives"][exercise_name] = {
            "dataset": str(dataset_dir),
            "selected_reps": int(len(selected_rep_uids)),
            "selected_windows": int(len(kp)),
            "rep_uids": selected_rep_uids,
        }

    keypoints = np.concatenate(all_keypoints, axis=0)
    angles = np.concatenate(all_angles, axis=0)
    labels = np.concatenate(all_labels, axis=0)
    metadata = pd.concat(all_metadata, ignore_index=True)

    rng = np.random.default_rng(seed)
    indices = np.arange(len(labels))
    rng.shuffle(indices)
    keypoints = keypoints[indices]
    angles = angles[indices]
    labels = labels[indices]
    metadata = metadata.iloc[indices].reset_index(drop=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    np.save(output_dir / "keypoints.npy", keypoints)
    np.save(output_dir / "angles.npy", angles)
    np.save(output_dir / "labels.npy", labels)
    metadata.to_csv(output_dir / "windows_metadata.csv", index=False)

    positive_reps = metadata.loc[
        metadata["binary_label"] == 1, "rep_uid"
    ].astype(str).nunique()
    negative_reps = metadata.loc[
        metadata["binary_label"] == 0, "rep_uid"
    ].astype(str).nunique()

    summary.update(
        {
            "total_windows": int(len(labels)),
            "positive_windows": int(np.sum(labels == 1)),
            "negative_windows": int(np.sum(labels == 0)),
            "positive_reps": int(positive_reps),
            "negative_reps": int(negative_reps),
            "keypoints_shape": list(keypoints.shape),
            "angles_shape": list(angles.shape),
            "labels_shape": list(labels.shape),
            "seed": int(seed),
            "negative_reps_per_exercise": int(n_negative_reps),
            "balancing_unit": "complete_rep_uid",
        }
    )

    (output_dir / "dataset_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(f"\n=== {split_name.upper()} ===")
    print(json.dumps(summary, indent=2))
    return summary


def parse_negative_pairs(values):
    result = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"Negativo non valido '{value}'. Usa nome=percorso")
        name, path = value.split("=", 1)
        name = name.strip().lower()
        path = path.strip()
        if not name or not path:
            raise ValueError(f"Negativo non valido '{value}'. Usa nome=percorso")
        if name in result:
            raise ValueError(f"Negativo duplicato: {name}")
        result[name] = Path(path)
    return result


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Costruisce train/validation per un qualsiasi esercizio target "
            "vs multi-negativi, bilanciando REP intere."
        )
    )
    parser.add_argument("--target", required=True, help="Nome/ID esercizio target, es. ex1 o squat")
    parser.add_argument("--train-positive", type=Path, required=True)
    parser.add_argument("--val-positive", type=Path, required=True)
    parser.add_argument(
        "--train-negative",
        action="append",
        required=True,
        metavar="NOME=PERCORSO",
        help="Ripetibile, es. --train-negative ex2=output/ex2_pm115/training_dataset",
    )
    parser.add_argument(
        "--val-negative",
        action="append",
        required=True,
        metavar="NOME=PERCORSO",
    )
    parser.add_argument(
        "--negative-reps-per-exercise",
        type=int,
        default=DEFAULT_NEGATIVE_REPS_PER_EXERCISE,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Default: output/binary_<target>_multinegative",
    )
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    target = args.target.strip().lower()
    if not target:
        raise ValueError("--target non può essere vuoto")
    if args.negative_reps_per_exercise < 1:
        raise ValueError("--negative-reps-per-exercise deve essere >= 1")

    train_negatives = parse_negative_pairs(args.train_negative)
    val_negatives = parse_negative_pairs(args.val_negative)

    if set(train_negatives) != set(val_negatives):
        raise ValueError("Train e validation devono contenere gli stessi tipi di esercizi negativi.")
    if target in train_negatives:
        raise ValueError("L'esercizio target non può comparire anche tra i negativi.")

    output_root = args.output or Path(f"output/binary_{target}_multinegative")

    train_summary = prepare_split(
        "train",
        target,
        args.train_positive,
        train_negatives,
        output_root / "train",
        args.negative_reps_per_exercise,
        args.seed,
    )
    val_summary = prepare_split(
        "validation",
        target,
        args.val_positive,
        val_negatives,
        output_root / "validation",
        args.negative_reps_per_exercise,
        args.seed + 1000,
    )

    summary = {
        "problem_type": "binary_multinegative",
        "target": target,
        "train": train_summary,
        "validation": val_summary,
    }
    (output_root / "binary_dataset_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
