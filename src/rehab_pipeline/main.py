import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from config import MODEL_PATH
from extract_clips import extract_clips
from fixed_count_segmenter import segment_fixed_count
from hybrid_segmenter import segment_repetitions
from joint_selection import AVAILABLE_JOINTS, normalize_selected_joints, selected_joints_to_angles
from training_dataset import create_review_table
from video_features import extract_pose_data_from_video


def _load_exercise_profile(path):
    if path is None:
        return {
            "guide_signals": None,
            "guide_angle": None,
            "direction": None,
            "signal_selection_mode": None,
            "doctor_selected_joints": [],
        }

    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "guide_signals": data.get("guide_signals"),
        "guide_angle": data.get("guide_angle"),
        "direction": data.get("direction"),
        "signal_selection_mode": data.get("signal_selection_mode"),
        "doctor_selected_joints": data.get("doctor_selected_joints") or [],
    }


def _doctor_validate_segments(segments, angles_df, selected_angles):
    """Valida le REP senza modificare start/end/peak trovati dall'AUTO.

    La selezione del medico e' quindi informazione clinica aggiuntiva, non un
    vincolo di segmentazione. Una REP e' confermata quando almeno uno degli
    angoli scelti mostra una escursione significativa durante quel segmento.
    """
    if not selected_angles:
        return [dict(s) for s in segments], 0, 0

    frames = angles_df["frame"].to_numpy() if "frame" in angles_df.columns else np.arange(len(angles_df))

    # Soglia adattiva per ogni angolo: 12% del range robusto dell'intero video,
    # con un minimo di 5 gradi per evitare conferme dovute solo al rumore.
    thresholds = {}
    for angle in selected_angles:
        if angle not in angles_df.columns:
            continue
        values = pd.to_numeric(angles_df[angle], errors="coerce").to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        if len(finite) == 0:
            continue
        q05, q95 = np.percentile(finite, [5, 95])
        thresholds[angle] = max(5.0, 0.12 * float(q95 - q05))

    validated = []
    confirmed = 0
    unconfirmed = 0

    for seg in segments:
        out = dict(seg)
        start = int(seg["start_frame"])
        end = int(seg["end_frame"])
        mask = (frames >= start) & (frames <= end)

        supporting = []
        amplitudes = {}
        for angle, threshold in thresholds.items():
            vals = pd.to_numeric(angles_df.loc[mask, angle], errors="coerce").to_numpy(dtype=float)
            vals = vals[np.isfinite(vals)]
            if len(vals) < 3:
                continue
            amp = float(np.percentile(vals, 95) - np.percentile(vals, 5))
            amplitudes[angle] = round(amp, 3)
            if amp >= threshold:
                supporting.append(angle)

        is_confirmed = len(supporting) > 0
        out["doctor_validation"] = "confirmed" if is_confirmed else "not_confirmed"
        out["doctor_validation_angles"] = ",".join(selected_angles)
        out["doctor_supporting_angles"] = ",".join(supporting)
        out["doctor_motion_amplitudes"] = json.dumps(amplitudes, separators=(",", ":"))

        if is_confirmed:
            confirmed += 1
        else:
            unconfirmed += 1
        validated.append(out)

    return validated, confirmed, unconfirmed


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Segmentazione REP: AUTO/FIXED originale. In doctor_guided la scelta "
            "del medico valida le REP ma NON modifica i confini temporali."
        )
    )

    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, default=Path("output/run"))
    parser.add_argument("--clips", action="store_true", help="Esporta un MP4 per ogni REP usata.")
    parser.add_argument("--guide-angle", type=str, default=None)
    parser.add_argument("--direction", choices=["increase", "decrease"], default=None)
    parser.add_argument("--exercise-config", type=Path, default=None)
    parser.add_argument(
        "--signal-selection-mode",
        choices=["auto", "doctor_guided"],
        default=None,
        help="AUTO puro oppure AUTO + validazione delle articolazioni indicate dal medico.",
    )
    parser.add_argument(
        "--selected-joints",
        nargs="+",
        choices=AVAILABLE_JOINTS,
        default=None,
        help="Articolazioni selezionate dal medico. Non cambiano start/end delle REP.",
    )
    parser.add_argument(
        "--expected-reps",
        type=int,
        default=None,
        help="Se omesso: AUTO. Se inserito: FIXED con N cicli completi validi.",
    )

    args = parser.parse_args()
    if args.expected_reps is not None and args.expected_reps < 1:
        raise ValueError("expected-reps deve essere >= 1")

    profile = _load_exercise_profile(args.exercise_config)

    if args.exercise_config is not None:
        signal_selection_mode = profile["signal_selection_mode"] or "auto"
        doctor_selected_joints = normalize_selected_joints(profile["doctor_selected_joints"])
    else:
        signal_selection_mode = args.signal_selection_mode or "auto"
        doctor_selected_joints = normalize_selected_joints(args.selected_joints)

    if signal_selection_mode == "doctor_guided" and not doctor_selected_joints:
        raise ValueError("In doctor_guided devi selezionare almeno una articolazione.")
    if signal_selection_mode == "auto" and args.selected_joints:
        raise ValueError("--selected-joints e' valido solo in doctor_guided.")

    # IMPORTANTE: doctor_guided NON restringe la segmentazione.
    # Il motore riceve esattamente gli stessi input dell'AUTO originale.
    if signal_selection_mode == "doctor_guided":
        seg_guide_signals = None
        seg_guide_angle = None
        seg_direction = None
    else:
        seg_guide_signals = profile["guide_signals"]
        seg_guide_angle = profile["guide_angle"] if profile["guide_angle"] is not None else args.guide_angle
        seg_direction = profile["direction"] if profile["direction"] is not None else args.direction

    args.output.mkdir(parents=True, exist_ok=True)

    angles_df, pose_landmarks, fps, total_frames, detection_rate = extract_pose_data_from_video(
        args.video,
        MODEL_PATH,
    )
    if angles_df.empty:
        raise RuntimeError("MediaPipe non ha rilevato pose utilizzabili.")

    angles_df.to_csv(args.output / "angles.csv", index=False)
    np.save(args.output / "pose_landmarks.npy", pose_landmarks)

    if args.expected_reps is None:
        rep_mode = "auto"
        all_segments, used_segments, metadata, candidates = segment_repetitions(
            angles_df,
            fps,
            guide_angle=seg_guide_angle,
            direction=seg_direction,
            guide_signals=seg_guide_signals,
            expected_reps=None,
        )
        metadata["rep_mode"] = "auto"
    else:
        rep_mode = "fixed"
        all_segments, used_segments, metadata, candidates = segment_fixed_count(
            angles_df,
            fps,
            args.expected_reps,
            guide_angle=seg_guide_angle,
            direction=seg_direction,
            guide_signals=seg_guide_signals,
        )

    doctor_angles = selected_joints_to_angles(doctor_selected_joints)
    doctor_confirmed = 0
    doctor_unconfirmed = 0

    if signal_selection_mode == "doctor_guided":
        all_segments, doctor_confirmed, doctor_unconfirmed = _doctor_validate_segments(
            all_segments, angles_df, doctor_angles
        )
        used_segments, _, _ = _doctor_validate_segments(
            used_segments, angles_df, doctor_angles
        )

    pd.DataFrame(all_segments).to_csv(args.output / "segments_all.csv", index=False)
    pd.DataFrame(used_segments).to_csv(args.output / "segments_used.csv", index=False)

    review_df = create_review_table(used_segments)
    review_df.to_csv(args.output / "rep_review.csv", index=False)

    metadata.update({
        "video": str(args.video),
        "fps": fps,
        "total_frames": total_frames,
        "pose_detection_rate": detection_rate,
        "rep_mode": rep_mode,
        "doctor_provided_rep_count": args.expected_reps is not None,
        "signal_selection_mode": signal_selection_mode,
        "doctor_selected_joints": doctor_selected_joints,
        "doctor_validation_angles": doctor_angles,
        "doctor_confirmed_reps": doctor_confirmed if signal_selection_mode == "doctor_guided" else None,
        "doctor_unconfirmed_reps": doctor_unconfirmed if signal_selection_mode == "doctor_guided" else None,
        "doctor_guided_segmentation": False,
        "doctor_guided_strategy": (
            "original_auto_boundaries_plus_posthoc_joint_validation"
            if signal_selection_mode == "doctor_guided" else None
        ),
    })

    # Segnala chiaramente che non stiamo usando le patch v6-v10.
    if signal_selection_mode == "doctor_guided":
        metadata["segmentation_mode_with_doctor"] = "original_auto_unchanged_plus_validation_v11"

    (args.output / "metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    serializable_candidates = []
    for c in candidates:
        serializable_candidates.append({
            k: v for k, v in c.items()
            if k not in {"normalized", "smoothed", "cycles"}
        })
    try:
        (args.output / "candidates.json").write_text(
            json.dumps(serializable_candidates, indent=2, default=float),
            encoding="utf-8",
        )
    except TypeError:
        pass

    if args.clips:
        extract_clips(args.video, used_segments, args.output / "repetitions")

    print(f"Pose rilevata: {detection_rate:.2f}%")
    print(f"Modalita REP: {rep_mode.upper()}")
    print(f"REP rilevate valide: {metadata.get('detected_reps', len(all_segments))}")
    print(f"REP proposte al medico: {len(used_segments)}")
    if signal_selection_mode == "doctor_guided":
        print(f"Articolazioni medico: {', '.join(doctor_selected_joints)}")
        print(f"Confermate dal distretto scelto: {doctor_confirmed}/{len(all_segments)}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
