import argparse
from pathlib import Path
import json

import numpy as np
import pandas as pd
import torch

from models_lstm import TwoBranchLSTM


def load_model(model_dir, device):
    model_dir = Path(model_dir)

    config = json.loads(
        (model_dir / "model_config.json").read_text(
            encoding="utf-8"
        )
    )

    model = TwoBranchLSTM(
        keypoint_input_size=int(config.get("keypoint_features", 36)),
        angle_input_size=int(config.get("angle_features", 8)),
        hidden_size_1=int(config["hidden_size_1"]),
        hidden_size_2=int(config["hidden_size_2"]),
        dense_size=int(config["dense_size"]),
        dropout=float(config["dropout"]),
    )

    model_path = model_dir / "best_model.pth"

    try:
        state = torch.load(
            model_path,
            map_location=device,
            weights_only=True,
        )
    except TypeError:
        state = torch.load(
            model_path,
            map_location=device,
        )

    model.load_state_dict(state)
    model.to(device)
    model.eval()

    return model


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--test",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--model-dir",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Filtra per test_source, es. ex1",
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Se omesso usa decision_threshold da model_config.json.",
    )

    args = parser.parse_args()

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    keypoints = np.load(
        args.test / "keypoints.npy"
    ).astype(np.float32)

    angles = np.load(
        args.test / "angles.npy"
    ).astype(np.float32)

    labels = np.load(
        args.test / "labels.npy"
    ).astype(np.int64)

    metadata = pd.read_csv(
        args.test / "windows_metadata.csv"
    )

    stats = np.load(
        args.model_dir
        / "normalization_stats.npz"
    )

    keypoints = (
        keypoints
        - stats["keypoints_mean"]
    ) / stats["keypoints_std"]

    angles = (
        angles
        - stats["angles_mean"]
    ) / stats["angles_std"]

    model = load_model(
        args.model_dir,
        device,
    )

    config = json.loads((args.model_dir / "model_config.json").read_text(encoding="utf-8"))
    threshold = float(config.get("decision_threshold", 0.5) if args.threshold is None else args.threshold)

    kp_tensor = torch.from_numpy(
        keypoints
    ).float().to(device)

    ang_tensor = torch.from_numpy(
        angles
    ).float().to(device)

    with torch.no_grad():
        logits = model(
            kp_tensor,
            ang_tensor,
        )

        probabilities = (
            torch.sigmoid(logits)
            .cpu()
            .numpy()
            .reshape(-1)
        )

    metadata = metadata.copy()
    metadata["true_label"] = labels
    metadata["probability_target"] = probabilities

    rep_rows = []

    for rep_uid, group in metadata.groupby(
        "rep_uid"
    ):
        true_label = int(
            group["true_label"].iloc[0]
        )

        mean_probability = float(
            group["probability_target"].mean()
        )

        min_probability = float(
            group["probability_target"].min()
        )

        max_probability = float(
            group["probability_target"].max()
        )

        predicted_label = int(
            mean_probability
            >= threshold
        )

        source = (
            group["test_source"].iloc[0]
            if "test_source" in group.columns
            else "unknown"
        )

        rep_rows.append({
            "rep_uid": rep_uid,
            "test_source": source,
            "true_label": true_label,
            "predicted_label": predicted_label,
            "mean_probability": mean_probability,
            "min_probability": min_probability,
            "max_probability": max_probability,
            "correct": (
                true_label
                == predicted_label
            ),
        })

    rep_df = pd.DataFrame(
        rep_rows
    )

    if args.source is not None:
        rep_df = rep_df[
            rep_df["test_source"]
            == args.source
        ].copy()

    rep_df = rep_df.sort_values(
        "rep_uid"
    )

    print()
    print("=== TUTTE LE REP ===")
    print()

    print(
        rep_df.to_string(
            index=False
        )
    )

    output_path = (
        args.model_dir
        / "test_all_reps.csv"
    )

    rep_df.to_csv(
        output_path,
        index=False,
    )

    print()
    print(
        f"Salvato in: {output_path}"
    )


if __name__ == "__main__":
    main()
    