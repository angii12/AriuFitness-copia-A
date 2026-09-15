import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from models_lstm import TwoBranchLSTM


def load_test_dataset(test_dir):
    test_dir = Path(test_dir)
    keypoints = np.load(test_dir / "keypoints.npy").astype(np.float32)
    angles = np.load(test_dir / "angles.npy").astype(np.float32)
    labels = np.load(test_dir / "labels.npy").astype(np.int64)
    metadata_path = test_dir / "windows_metadata.csv"
    metadata = pd.read_csv(metadata_path) if metadata_path.exists() else pd.DataFrame(index=range(len(labels)))

    if not (len(keypoints) == len(angles) == len(labels) == len(metadata)):
        raise ValueError("Dataset di test incoerente.")
    return keypoints, angles, labels, metadata


def load_normalization(stats_path):
    stats = np.load(stats_path)
    return (
        stats["keypoints_mean"],
        stats["keypoints_std"],
        stats["angles_mean"],
        stats["angles_std"],
    )


def normalize(keypoints, angles, stats):
    kp_mean, kp_std, ang_mean, ang_std = stats
    return (keypoints - kp_mean) / kp_std, (angles - ang_mean) / ang_std


def compute_metrics(labels, predictions):
    labels = np.asarray(labels).astype(int)
    predictions = np.asarray(predictions).astype(int)

    tp = int(np.sum((labels == 1) & (predictions == 1)))
    tn = int(np.sum((labels == 0) & (predictions == 0)))
    fp = int(np.sum((labels == 0) & (predictions == 1)))
    fn = int(np.sum((labels == 1) & (predictions == 0)))
    total = max(1, tp + tn + fp + fn)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    specificity = tn / max(1, tn + fp)
    f1 = 2 * precision * recall / max(1e-12, precision + recall)

    return {
        "accuracy": (tp + tn) / total,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
    }


def build_model(config):
    return TwoBranchLSTM(
        keypoint_input_size=int(config.get("keypoint_features", 36)),
        angle_input_size=int(config.get("angle_features", 8)),
        hidden_size_1=int(config["hidden_size_1"]),
        hidden_size_2=int(config["hidden_size_2"]),
        dense_size=int(config["dense_size"]),
        dropout=float(config["dropout"]),
    )


def main():
    parser = argparse.ArgumentParser(description="Valuta il modello LSTM binario su un test set separato.")
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()

    config = json.loads((args.model_dir / "model_config.json").read_text(encoding="utf-8"))
    threshold = float(config.get("decision_threshold", 0.5) if args.threshold is None else args.threshold)

    keypoints, angles, labels, metadata = load_test_dataset(args.test)
    stats = load_normalization(args.model_dir / "normalization_stats.npz")
    keypoints, angles = normalize(keypoints, angles, stats)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(config).to(device)

    model_path = args.model_dir / "best_model.pth"
    try:
        state_dict = torch.load(model_path, map_location=device, weights_only=True)
    except TypeError:
        state_dict = torch.load(model_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()

    with torch.no_grad():
        logits = model(
            torch.from_numpy(keypoints).float().to(device),
            torch.from_numpy(angles).float().to(device),
        )
        probabilities = torch.sigmoid(logits).cpu().numpy()

    predictions = (probabilities >= threshold).astype(np.int64)
    window_metrics = compute_metrics(labels, predictions)
    window_metrics.update({
        "threshold": threshold,
        "samples": int(len(labels)),
        "positive_samples": int(np.sum(labels == 1)),
        "negative_samples": int(np.sum(labels == 0)),
        "mean_positive_probability": float(probabilities[labels == 1].mean()) if np.any(labels == 1) else None,
        "mean_negative_probability": float(probabilities[labels == 0].mean()) if np.any(labels == 0) else None,
    })

    pred_df = metadata.copy()
    pred_df["true_label"] = labels
    pred_df["probability"] = probabilities
    pred_df["predicted_label"] = predictions
    pred_df["correct"] = labels == predictions
    pred_df.to_csv(args.model_dir / "test_predictions.csv", index=False)

    target = str(config.get("target_exercise", "target"))
    result = {"target_exercise": target, "window_level": window_metrics}

    if "rep_uid" in pred_df.columns and pred_df["rep_uid"].notna().any():
        rep_df = (
            pred_df.dropna(subset=["rep_uid"])
            .groupby("rep_uid", as_index=False)
            .agg(
                true_label=("true_label", "first"),
                probability=("probability", "mean"),
                windows=("probability", "size"),
            )
        )
        rep_df["predicted_label"] = (rep_df["probability"] >= threshold).astype(int)
        rep_df["correct"] = rep_df["true_label"] == rep_df["predicted_label"]
        rep_metrics = compute_metrics(rep_df["true_label"].to_numpy(), rep_df["predicted_label"].to_numpy())
        rep_metrics.update({"threshold": threshold, "reps": int(len(rep_df))})
        result["rep_level"] = rep_metrics
        rep_df.to_csv(args.model_dir / "test_predictions_by_rep.csv", index=False)

    source_column = None
    if "test_source" in pred_df.columns:
        source_column = "test_source"
    elif "negative_source" in pred_df.columns:
        source_column = "negative_source"

    if source_column is not None:
        per_source_window = {}
        for source, group in pred_df.groupby(source_column, dropna=False):
            key = str(source) if str(source).strip() and str(source) != "nan" else "positive_or_unspecified"
            metrics = compute_metrics(group["true_label"].to_numpy(), group["predicted_label"].to_numpy())
            metrics["samples"] = int(len(group))
            per_source_window[key] = metrics
        result["per_source_window_level"] = per_source_window

        if "rep_uid" in pred_df.columns and pred_df["rep_uid"].notna().any():
            source_rep_df = (
                pred_df.dropna(subset=["rep_uid"])
                .groupby([source_column, "rep_uid"], as_index=False, dropna=False)
                .agg(true_label=("true_label", "first"), probability=("probability", "mean"))
            )
            source_rep_df["predicted_label"] = (source_rep_df["probability"] >= threshold).astype(int)
            per_source_rep = {}
            for source, group in source_rep_df.groupby(source_column, dropna=False):
                key = str(source) if str(source).strip() and str(source) != "nan" else "positive_or_unspecified"
                metrics = compute_metrics(group["true_label"].to_numpy(), group["predicted_label"].to_numpy())
                metrics["reps"] = int(len(group))
                per_source_rep[key] = metrics
            result["per_source_rep_level"] = per_source_rep

    (args.model_dir / "test_metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
