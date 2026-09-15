import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from models_lstm import TwoBranchLSTM


def load_model(model_dir, device):
    config = json.loads((model_dir / "model_config.json").read_text(encoding="utf-8"))
    model = TwoBranchLSTM(
        keypoint_input_size=int(config.get("keypoint_features", 36)),
        angle_input_size=int(config.get("angle_features", 8)),
        hidden_size_1=int(config["hidden_size_1"]),
        hidden_size_2=int(config["hidden_size_2"]),
        dense_size=int(config["dense_size"]),
        dropout=float(config["dropout"]),
    )
    try:
        state = torch.load(model_dir / "best_model.pth", map_location=device, weights_only=True)
    except TypeError:
        state = torch.load(model_dir / "best_model.pth", map_location=device)
    model.load_state_dict(state)
    model.to(device)
    model.eval()
    return model


def main():
    parser = argparse.ArgumentParser(description="Ispeziona gli shift di una REP specifica senza confonderla con REP omonime.")
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--rep-uid", help="rep_uid completo, metodo consigliato")
    group.add_argument("--rep", type=int, help="Numero REP; usare anche --source per disambiguare")
    parser.add_argument("--source", help="test_source o prefisso sorgente, es. ex1 o PM_001")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    kp = np.load(args.test / "keypoints.npy").astype(np.float32)
    ang = np.load(args.test / "angles.npy").astype(np.float32)
    meta = pd.read_csv(args.test / "windows_metadata.csv")
    if "rep_uid" not in meta.columns:
        raise ValueError("windows_metadata.csv non contiene rep_uid")

    stats = np.load(args.model_dir / "normalization_stats.npz")
    kp = (kp - stats["keypoints_mean"]) / stats["keypoints_std"]
    ang = (ang - stats["angles_mean"]) / stats["angles_std"]
    model = load_model(args.model_dir, device)

    with torch.no_grad():
        logits = model(
            torch.from_numpy(kp).float().to(device),
            torch.from_numpy(ang).float().to(device),
        )
        probs = torch.sigmoid(logits).cpu().numpy().reshape(-1)

    meta = meta.copy()
    meta["probability_target"] = probs

    if args.rep_uid:
        rows = meta[meta["rep_uid"].astype(str) == args.rep_uid].copy()
    else:
        suffix = f"__rep_{args.rep:03d}"
        rows = meta[meta["rep_uid"].astype(str).str.endswith(suffix)].copy()
        if args.source:
            source_lower = args.source.lower()
            source_mask = rows["rep_uid"].astype(str).str.lower().str.contains(source_lower, regex=False)
            if "test_source" in rows.columns:
                source_mask |= rows["test_source"].astype(str).str.lower().eq(source_lower)
            rows = rows[source_mask].copy()
        if rows["rep_uid"].nunique() > 1:
            choices = sorted(rows["rep_uid"].astype(str).unique())
            raise ValueError(
                "REP ambigua. Usa --rep-uid oppure --source. Candidati: " + ", ".join(choices)
            )

    if rows.empty:
        raise ValueError("Nessuna finestra trovata per la REP richiesta.")

    shift_column = next(
        (name for name in ["temporal_shift", "shift", "frame_shift", "boundary_shift"] if name in rows.columns),
        None,
    )
    if shift_column:
        rows = rows.sort_values(shift_column)
        print(rows[["rep_uid", shift_column, "probability_target"]].to_string(index=False))
    else:
        print(rows[["rep_uid", "probability_target"]].to_string(index=False))
        print("\nColonna shift non trovata. Colonne disponibili:")
        print(list(meta.columns))


if __name__ == "__main__":
    main()
