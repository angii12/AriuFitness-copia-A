import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROTATION_ANGLES = (-10.0, 10.0)


def rotate_keypoints(sequence, degrees):
    """
    Ruota i keypoint sul piano XY.

    sequence shape: (8, 36)
    I 36 valori rappresentano 12 keypoint x 3 coordinate (x, y, z).
    La rotazione viene applicata solo a x e y.
    """
    sequence = np.asarray(sequence, dtype=np.float32).copy()

    if sequence.ndim != 2 or sequence.shape[1] != 36:
        raise ValueError(
            f"Attesa sequenza keypoint con shape (T, 36), ricevuta {sequence.shape}"
        )

    points = sequence.reshape(sequence.shape[0], 12, 3)

    radians = np.deg2rad(degrees)
    cos_a = np.cos(radians)
    sin_a = np.sin(radians)

    x = points[:, :, 0].copy()
    y = points[:, :, 1].copy()

    points[:, :, 0] = cos_a * x - sin_a * y
    points[:, :, 1] = sin_a * x + cos_a * y

    return points.reshape(sequence.shape[0], 36).astype(np.float32)


def augment_dataset(dataset_dir, output_dir=None):
    dataset_dir = Path(dataset_dir)

    if output_dir is None:
        output_dir = dataset_dir.parent / f"{dataset_dir.name}_augmented"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    keypoints_path = dataset_dir / "keypoints.npy"
    angles_path = dataset_dir / "angles.npy"
    labels_path = dataset_dir / "labels.npy"
    metadata_path = dataset_dir / "windows_metadata.csv"

    for path in (
        keypoints_path,
        angles_path,
        labels_path,
        metadata_path,
    ):
        if not path.exists():
            raise FileNotFoundError(f"File richiesto non trovato: {path}")

    keypoints = np.load(keypoints_path)
    angles = np.load(angles_path)
    labels = np.load(labels_path)
    metadata = pd.read_csv(metadata_path)

    if not (
        len(keypoints)
        == len(angles)
        == len(labels)
        == len(metadata)
    ):
        raise ValueError(
            "Numero di esempi non coerente tra keypoints, angles, labels e metadata."
        )

    augmented_keypoints = []
    augmented_angles = []
    augmented_labels = []
    augmented_metadata = []

    for i in range(len(keypoints)):
        kp = keypoints[i]
        ang = angles[i]
        label = labels[i]
        meta = metadata.iloc[i].to_dict()

        # 1. Originale
        augmented_keypoints.append(kp)
        augmented_angles.append(ang)
        augmented_labels.append(label)

        original_meta = dict(meta)
        original_meta["augmentation"] = "original"
        original_meta["rotation_degrees"] = 0.0
        augmented_metadata.append(original_meta)

        # 2. Rotazioni
        for degrees in ROTATION_ANGLES:
            rotated_kp = rotate_keypoints(kp, degrees)

            augmented_keypoints.append(rotated_kp)

            # Gli angoli articolari restano invariati con una rotazione
            # rigida dell'intero corpo nel piano.
            augmented_angles.append(ang.copy())

            augmented_labels.append(label)

            rotated_meta = dict(meta)
            rotated_meta["augmentation"] = "rotation"
            rotated_meta["rotation_degrees"] = float(degrees)
            augmented_metadata.append(rotated_meta)

    X_keypoints = np.asarray(augmented_keypoints, dtype=np.float32)
    X_angles = np.asarray(augmented_angles, dtype=np.float32)
    y = np.asarray(augmented_labels, dtype=labels.dtype)

    metadata_aug = pd.DataFrame(augmented_metadata)

    np.save(output_dir / "keypoints.npy", X_keypoints)
    np.save(output_dir / "angles.npy", X_angles)
    np.save(output_dir / "labels.npy", y)

    metadata_aug.to_csv(
        output_dir / "windows_metadata.csv",
        index=False,
    )

    summary = {
        "original_samples": int(len(keypoints)),
        "augmentation_variants_per_sample": 3,
        "rotation_degrees": [-10, 10],
        "mirror_enabled": False,
        "augmented_samples": int(len(X_keypoints)),
        "keypoints_shape": list(X_keypoints.shape),
        "angles_shape": list(X_angles.shape),
        "labels_shape": list(y.shape),
    }

    (output_dir / "augmentation_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Augmentation del dataset LSTM."
    )

    parser.add_argument(
        "dataset_dir",
        type=Path,
        help="Cartella contenente keypoints.npy, angles.npy, labels.npy e windows_metadata.csv",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Cartella di output opzionale.",
    )

    args = parser.parse_args()

    summary = augment_dataset(
        args.dataset_dir,
        output_dir=args.output,
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()