import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


SEED = 42


def ensure_rep_uid(meta: pd.DataFrame, dataset_dir: Path) -> pd.DataFrame:
    meta = meta.copy()
    if "rep_uid" in meta.columns and meta["rep_uid"].notna().all():
        meta["rep_uid"] = meta["rep_uid"].astype(str)
        return meta
    if "rep" not in meta.columns:
        raise ValueError(f"{dataset_dir}: manca rep_uid e non è possibile ricostruirlo")
    source = (
        meta["source_video_id"].fillna(dataset_dir.parent.name).astype(str)
        if "source_video_id" in meta.columns
        else pd.Series([dataset_dir.parent.name] * len(meta), index=meta.index)
    )
    reps = pd.to_numeric(meta["rep"], errors="raise").astype(int)
    meta["rep_uid"] = [f"{s}__rep_{r:03d}" for s, r in zip(source, reps)]
    return meta


def load_dataset(path: Path):
    path = Path(path)
    kp = np.load(path / "keypoints.npy").astype(np.float32)
    ang = np.load(path / "angles.npy").astype(np.float32)
    meta = pd.read_csv(path / "windows_metadata.csv")

    if not (len(kp) == len(ang) == len(meta)):
        raise ValueError(f"Dataset incoerente: {path}")
    if kp.ndim != 3 or kp.shape[1:] != (8, 36):
        raise ValueError(f"{path}: shape keypoints non valida {kp.shape}")
    if ang.ndim != 3 or ang.shape[1:] != (8, 8):
        raise ValueError(f"{path}: shape angles non valida {ang.shape}")
    if not np.isfinite(kp).all() or not np.isfinite(ang).all():
        raise ValueError(f"{path}: NaN/inf nel dataset")

    return kp, ang, ensure_rep_uid(meta, path)


def parse_negative_pairs(values):
    result = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"Negativo non valido '{value}'. Usa nome=percorso")
        name, raw_path = value.split("=", 1)
        name = name.strip().lower()
        raw_path = raw_path.strip()
        if not name or not raw_path:
            raise ValueError(f"Negativo non valido '{value}'. Usa nome=percorso")
        if name in result:
            raise ValueError(f"Negativo duplicato: {name}")
        result[name] = Path(raw_path)
    return result


def select_reps(kp, ang, meta, n_reps, seed):
    rep_uids = meta["rep_uid"].astype(str).unique()
    if len(rep_uids) < n_reps:
        raise ValueError(f"Richieste {n_reps} REP, ma disponibili {len(rep_uids)}")

    rng = np.random.default_rng(seed)
    chosen = rng.choice(rep_uids, size=n_reps, replace=False)
    mask = meta["rep_uid"].astype(str).isin(chosen).to_numpy()
    return kp[mask], ang[mask], meta.loc[mask].copy(), sorted(map(str, chosen))


def main():
    parser = argparse.ArgumentParser(
        description="Costruisce un test multi-negativo bilanciato per qualsiasi esercizio target."
    )
    parser.add_argument("--target", required=True, help="Nome/ID esercizio target")
    parser.add_argument("--positive", type=Path, required=True)
    parser.add_argument(
        "--negative",
        action="append",
        required=True,
        metavar="NOME=PERCORSO",
        help="Ripetibile, es. --negative ex2=output/ex2_test/training_dataset",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Default: output/binary_<target>_multinegative/test",
    )
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    target = args.target.strip().lower()
    negatives = parse_negative_pairs(args.negative)
    if target in negatives:
        raise ValueError("L'esercizio target non può comparire anche tra i negativi.")
    output = args.output or Path(f"output/binary_{target}_multinegative/test")

    pos_kp, pos_ang, pos_meta = load_dataset(args.positive)
    positive_reps = pos_meta["rep_uid"].astype(str).unique()
    n_positive_reps = len(positive_reps)
    if n_positive_reps == 0:
        raise ValueError("Il dataset positivo non contiene REP.")

    print(f"REP positive {target}: {n_positive_reps}")

    negative_names = list(negatives.keys())
    base = n_positive_reps // len(negative_names)
    remainder = n_positive_reps % len(negative_names)
    reps_per_negative = {
        name: base + (1 if i < remainder else 0)
        for i, name in enumerate(negative_names)
    }
    print("Distribuzione REP negative:", reps_per_negative)

    pos_meta = pos_meta.copy()
    pos_meta["binary_label"] = 1
    pos_meta["binary_class"] = f"positive_{target}"
    pos_meta["target_exercise"] = target
    pos_meta["test_source"] = target

    all_kp = [pos_kp]
    all_ang = [pos_ang]
    all_y = [np.ones(len(pos_kp), dtype=np.int64)]
    all_meta = [pos_meta]

    summary = {
        "target": target,
        "positive": {
            "source": str(args.positive),
            "reps": int(n_positive_reps),
            "windows": int(len(pos_kp)),
        },
        "negatives": {},
    }

    for i, (name, path) in enumerate(negatives.items()):
        n_reps = reps_per_negative[name]
        if n_reps == 0:
            summary["negatives"][name] = {
                "source": str(path),
                "selected_reps": 0,
                "selected_windows": 0,
                "rep_uids": [],
            }
            continue

        kp, ang, meta = load_dataset(path)
        kp, ang, meta, chosen = select_reps(
            kp, ang, meta, n_reps=n_reps, seed=args.seed + i
        )
        meta["binary_label"] = 0
        meta["binary_class"] = f"negative_non_{target}"
        meta["target_exercise"] = target
        meta["test_source"] = name

        all_kp.append(kp)
        all_ang.append(ang)
        all_y.append(np.zeros(len(kp), dtype=np.int64))
        all_meta.append(meta)

        summary["negatives"][name] = {
            "source": str(path),
            "selected_reps": int(len(chosen)),
            "selected_windows": int(len(kp)),
            "rep_uids": chosen,
        }

    kp = np.concatenate(all_kp, axis=0)
    ang = np.concatenate(all_ang, axis=0)
    y = np.concatenate(all_y, axis=0)
    meta = pd.concat(all_meta, ignore_index=True)

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

    summary.update(
        {
            "total_windows": int(len(y)),
            "positive_windows": int(np.sum(y == 1)),
            "negative_windows": int(np.sum(y == 0)),
            "positive_reps": int(meta.loc[meta["binary_label"] == 1, "rep_uid"].nunique()),
            "negative_reps": int(meta.loc[meta["binary_label"] == 0, "rep_uid"].nunique()),
            "keypoints_shape": list(kp.shape),
            "angles_shape": list(ang.shape),
            "labels_shape": list(y.shape),
            "seed": int(args.seed),
            "balancing_unit": "complete_rep_uid",
        }
    )
    (output / "test_dataset_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print("\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
