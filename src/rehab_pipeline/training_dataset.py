import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from pose_preprocessing import process_angles, process_keypoints, shifted_rep_windows


ACCEPTED_VALUES = {"accepted", "accept", "yes", "y", "1", "true", "ok"}


def create_review_table(segments):
    rows = []
    for segment in segments:
        row = dict(segment)
        row["review_status"] = "pending"
        row["doctor_note"] = ""
        rows.append(row)
    return pd.DataFrame(rows)


def _is_accepted(value):
    return str(value).strip().lower() in ACCEPTED_VALUES


def _extract_subject_id(video_name):
    match = re.search(r"(PM_\d+)", str(video_name))
    return match.group(1) if match else Path(str(video_name)).stem


def build_dataset(run_dir, output_dir=None, accept_pending=False, exercise_label=1):
    run_dir = Path(run_dir)
    output_dir = Path(output_dir) if output_dir else run_dir / "training_dataset"
    output_dir.mkdir(parents=True, exist_ok=True)

    landmarks_path = run_dir / "pose_landmarks.npy"
    angles_path = run_dir / "angles.csv"
    review_path = run_dir / "rep_review.csv"
    metadata_path = run_dir / "metadata.json"

    for path in (landmarks_path, angles_path, review_path, metadata_path):
        if not path.exists():
            raise FileNotFoundError(f"File richiesto non trovato: {path}")

    landmarks = np.load(landmarks_path)
    angles_df = pd.read_csv(angles_path)
    review_df = pd.read_csv(review_path)
    run_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    total_frames = int(run_metadata.get("total_frames", len(landmarks)))
    if len(landmarks) != len(angles_df):
        raise ValueError(
            f"Timeline non coerente: {len(landmarks)} frame pose vs {len(angles_df)} frame angoli"
        )

    source_video = str(run_metadata.get("video", run_dir.name))
    source_video_id = Path(source_video).stem
    subject_id = _extract_subject_id(source_video)

    keypoints_frames = process_keypoints(landmarks)
    angles_frames = process_angles(angles_df)

    keypoint_windows = []
    angle_windows = []
    labels = []
    window_rows = []

    for _, segment in review_df.iterrows():
        status = str(segment.get("review_status", "pending")).strip().lower()
        if not (_is_accepted(status) or (accept_pending and status == "pending")):
            continue

        rep_number = int(segment["rep"])
        rep_uid = f"{source_video_id}__rep_{rep_number:03d}"

        for window in shifted_rep_windows(segment, total_frames=total_frames):
            idx = np.asarray(window["frame_indices"], dtype=int)
            keypoint_windows.append(keypoints_frames[idx])
            angle_windows.append(angles_frames[idx])
            labels.append(int(exercise_label))
            window_rows.append({
                "exercise_label": int(exercise_label),
                "source_video": source_video,
                "source_video_id": source_video_id,
                "subject_id": subject_id,
                "rep": rep_number,
                "rep_uid": rep_uid,
                "split_group": rep_uid,
                "shift": int(window["shift"]),
                "start_frame": int(window["start_frame"]),
                "end_frame": int(window["end_frame"]),
                "sampled_frames": ",".join(map(str, idx.tolist())),
                "segmentation_confidence": float(segment.get("confidence", np.nan)),
                "review_status": status,
            })

    if not keypoint_windows:
        raise RuntimeError(
            "Nessuna REP accettata. Modifica rep_review.csv impostando review_status=accepted "
            "oppure usa --accept-pending solo per test tecnici."
        )

    X_keypoints = np.asarray(keypoint_windows, dtype=np.float32)
    X_angles = np.asarray(angle_windows, dtype=np.float32)
    y = np.asarray(labels, dtype=np.int64)
    metadata_df = pd.DataFrame(window_rows)

    if not np.isfinite(X_keypoints).all() or not np.isfinite(X_angles).all():
        raise ValueError("Il dataset contiene NaN o inf dopo il preprocessing.")

    np.save(output_dir / "keypoints.npy", X_keypoints)
    np.save(output_dir / "angles.npy", X_angles)
    np.save(output_dir / "labels.npy", y)
    metadata_df.to_csv(output_dir / "windows_metadata.csv", index=False)

    summary = {
        "accepted_reps": int(metadata_df["rep_uid"].nunique()),
        "generated_windows": int(len(metadata_df)),
        "source_video": source_video,
        "source_video_id": source_video_id,
        "subject_id": subject_id,
        "keypoints_shape": list(X_keypoints.shape),
        "angles_shape": list(X_angles.shape),
        "labels_shape": list(y.shape),
        "exercise_label": int(exercise_label),
        "temporal_shift_policy": "-5..+5 frames when in video bounds",
        "window_size": int(X_keypoints.shape[1]),
        "split_group": "rep_uid",
    }
    (output_dir / "dataset_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Crea il dataset LSTM (keypoints + angles) dalle REP revisionate."
    )
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--exercise-label", type=int, default=1)
    parser.add_argument(
        "--accept-pending",
        action="store_true",
        help="Solo per test: considera accettate anche le REP ancora pending.",
    )
    args = parser.parse_args()

    summary = build_dataset(
        args.run_dir,
        output_dir=args.output,
        accept_pending=args.accept_pending,
        exercise_label=args.exercise_label,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
