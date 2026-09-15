import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from models_lstm import TwoBranchLSTM


def load_model(model_dir, device):
    model_dir = Path(model_dir)
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
    return model, config


def main():
    parser = argparse.ArgumentParser(description="Mostra le REP classificate male da un modello binario generico.")
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    keypoints = np.load(args.test / "keypoints.npy").astype(np.float32)
    angles = np.load(args.test / "angles.npy").astype(np.float32)
    labels = np.load(args.test / "labels.npy").astype(np.int64)
    metadata = pd.read_csv(args.test / "windows_metadata.csv")
    if "rep_uid" not in metadata.columns:
        raise ValueError("windows_metadata.csv non contiene rep_uid")

    stats = np.load(args.model_dir / "normalization_stats.npz")
    keypoints = (keypoints - stats["keypoints_mean"]) / stats["keypoints_std"]
    angles = (angles - stats["angles_mean"]) / stats["angles_std"]

    model, config = load_model(args.model_dir, device)
    threshold = float(config.get("decision_threshold", 0.5) if args.threshold is None else args.threshold)
    target = str(config.get("target_exercise", "target"))

    with torch.no_grad():
        logits = model(
            torch.from_numpy(keypoints).float().to(device),
            torch.from_numpy(angles).float().to(device),
        )
        probabilities = torch.sigmoid(logits).cpu().numpy().reshape(-1)

    metadata = metadata.copy()
    metadata["true_label"] = labels
    metadata["probability_target"] = probabilities
    metadata["predicted_label"] = (probabilities >= threshold).astype(int)

    rep_rows = []
    for rep_uid, group in metadata.groupby("rep_uid"):
        true_label = int(group["true_label"].iloc[0])
        mean_probability = float(group["probability_target"].mean())
        predicted_label = int(mean_probability >= threshold)
        source = group["test_source"].iloc[0] if "test_source" in group.columns else "unknown"
        rep_rows.append(
            {
                "rep_uid": rep_uid,
                "test_source": source,
                "target_exercise": target,
                "true_label": true_label,
                "predicted_label": predicted_label,
                "probability_target": mean_probability,
                "correct": true_label == predicted_label,
            }
        )

    rep_df = pd.DataFrame(rep_rows)
    errors = rep_df[~rep_df["correct"]].copy().sort_values("probability_target", ascending=False)

    print(f"\n=== REP SBAGLIATE | target={target} | threshold={threshold:.3f} ===\n")
    print("Nessun errore." if len(errors) == 0 else errors.to_string(index=False))

    output_path = args.model_dir / "test_rep_errors.csv"
    errors.to_csv(output_path, index=False)
    print(f"\nSalvato in: {output_path}")


if __name__ == "__main__":
    main()
