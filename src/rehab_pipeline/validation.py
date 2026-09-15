import argparse
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment


import os

DEFAULT_DATASET_ROOT = Path(os.environ.get("REHAB_DATASET_ROOT", "data/videos"))
DEFAULT_ANNOTATIONS = Path("data/annotations/Segmentation.csv")
DEFAULT_OUTPUT_ROOT = Path("output/validation")
MAIN_SCRIPT = Path("src/main.py")


def temporal_iou(a_start, a_end, b_start, b_end):
    intersection = max(
        0,
        min(a_end, b_end) - max(a_start, b_start) + 1
    )

    union = (
        (a_end - a_start + 1)
        + (b_end - b_start + 1)
        - intersection
    )

    if union <= 0:
        return 0.0

    return intersection / union


def parse_video_info(video_path):
    """
    Esempio:
    .../Ex3/PM_010-Camera17-30fps.mp4
    -> video_id = PM_010
    -> exercise_id = 3
    """
    match_ex = re.fullmatch(
        r"Ex(\d+)",
        video_path.parent.name,
        flags=re.IGNORECASE
    )

    if not match_ex:
        raise ValueError(
            f"Impossibile ricavare exercise_id dalla cartella: "
            f"{video_path.parent.name}"
        )

    exercise_id = int(match_ex.group(1))

    name = video_path.stem

    marker = "-Camera17"

    if marker not in name:
        raise ValueError(
            f"Nome video Camera17 non riconosciuto: {video_path.name}"
        )

    video_id = name.split(marker, 1)[0]

    return video_id, exercise_id


def load_annotations(path):
    df = pd.read_csv(
        path,
        sep=";"
    )

    required = {
        "video_id",
        "exercise_id",
        "repetition_number",
        "first_frame",
        "last_frame",
        "correctness",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            "Nel CSV delle annotazioni mancano le colonne: "
            + ", ".join(sorted(missing))
        )

    return df


def ground_truth_for_video(
    annotations,
    video_id,
    exercise_id
):
    gt = annotations[
        (annotations["video_id"].astype(str) == str(video_id))
        &
        (
            pd.to_numeric(
                annotations["exercise_id"],
                errors="coerce"
            )
            == exercise_id
        )
    ].copy()

    gt["first_frame"] = pd.to_numeric(
        gt["first_frame"],
        errors="coerce"
    )

    gt["last_frame"] = pd.to_numeric(
        gt["last_frame"],
        errors="coerce"
    )

    gt = gt.dropna(
        subset=[
            "first_frame",
            "last_frame"
        ]
    )

    gt["first_frame"] = gt[
        "first_frame"
    ].astype(int)

    gt["last_frame"] = gt[
        "last_frame"
    ].astype(int)

    gt = gt.sort_values(
        [
            "first_frame",
            "last_frame"
        ]
    ).reset_index(
        drop=True
    )

    return gt


def load_predictions(predictions_path):
    if not predictions_path.exists():
        raise FileNotFoundError(
            f"File predizioni non trovato: {predictions_path}"
        )

    df = pd.read_csv(
        predictions_path
    )

    required = {
        "start_frame",
        "end_frame",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            "Nel file delle predizioni mancano le colonne: "
            + ", ".join(sorted(missing))
        )

    df["start_frame"] = pd.to_numeric(
        df["start_frame"],
        errors="coerce"
    )

    df["end_frame"] = pd.to_numeric(
        df["end_frame"],
        errors="coerce"
    )

    df = df.dropna(
        subset=[
            "start_frame",
            "end_frame"
        ]
    )

    df["start_frame"] = df[
        "start_frame"
    ].astype(int)

    df["end_frame"] = df[
        "end_frame"
    ].astype(int)

    df = df.sort_values(
        [
            "start_frame",
            "end_frame"
        ]
    ).reset_index(
        drop=True
    )

    return df


def hungarian_match(gt, pred):
    n_gt = len(gt)
    n_pred = len(pred)

    if n_gt == 0 or n_pred == 0:
        return [], list(range(n_gt)), list(range(n_pred))

    iou_matrix = np.zeros(
        (n_gt, n_pred),
        dtype=float
    )

    for i in range(n_gt):
        for j in range(n_pred):
            iou_matrix[i, j] = temporal_iou(
                int(gt.loc[i, "first_frame"]),
                int(gt.loc[i, "last_frame"]),
                int(pred.loc[j, "start_frame"]),
                int(pred.loc[j, "end_frame"]),
            )

    cost_matrix = 1.0 - iou_matrix

    rows, cols = linear_sum_assignment(
        cost_matrix
    )

    matches = []
    used_gt = set()
    used_pred = set()

    for gt_idx, pred_idx in zip(rows, cols):
        iou = float(
            iou_matrix[
                gt_idx,
                pred_idx
            ]
        )

        # Come nel confronto PM_010:
        # accettiamo solo coppie con sovrapposizione reale.
        if iou <= 0.0:
            continue

        gt_row = gt.loc[gt_idx]
        pred_row = pred.loc[pred_idx]

        start_error = (
            int(pred_row["start_frame"])
            - int(gt_row["first_frame"])
        )

        end_error = (
            int(pred_row["end_frame"])
            - int(gt_row["last_frame"])
        )

        matches.append({
            "gt_index": int(gt_idx),
            "pred_index": int(pred_idx),
            "gt_rep": int(
                gt_row["repetition_number"]
            )
            if pd.notna(gt_row["repetition_number"])
            else int(gt_idx + 1),
            "correctness": str(
                gt_row["correctness"]
            ),
            "gt_start": int(
                gt_row["first_frame"]
            ),
            "gt_end": int(
                gt_row["last_frame"]
            ),
            "pred_start": int(
                pred_row["start_frame"]
            ),
            "pred_end": int(
                pred_row["end_frame"]
            ),
            "iou": iou,
            "start_error": int(
                start_error
            ),
            "end_error": int(
                end_error
            ),
            "abs_start_error": abs(
                int(start_error)
            ),
            "abs_end_error": abs(
                int(end_error)
            ),
        })

        used_gt.add(
            int(gt_idx)
        )
        used_pred.add(
            int(pred_idx)
        )

    unmatched_gt = [
        i
        for i in range(n_gt)
        if i not in used_gt
    ]

    unmatched_pred = [
        i
        for i in range(n_pred)
        if i not in used_pred
    ]

    return (
        matches,
        unmatched_gt,
        unmatched_pred
    )


def summarize_video(
    video_id,
    exercise_id,
    gt,
    pred,
    matches
):
    n_gt = len(gt)
    n_pred = len(pred)
    n_match = len(matches)

    if matches:
        ious = np.asarray(
            [
                m["iou"]
                for m in matches
            ],
            dtype=float
        )

        abs_start = np.asarray(
            [
                m["abs_start_error"]
                for m in matches
            ],
            dtype=float
        )

        abs_end = np.asarray(
            [
                m["abs_end_error"]
                for m in matches
            ],
            dtype=float
        )

        mean_iou = float(
            np.mean(ious)
        )

        mean_start = float(
            np.mean(abs_start)
        )

        mean_end = float(
            np.mean(abs_end)
        )

        match_iou_50 = int(
            np.sum(
                ious >= 0.50
            )
        )

        match_iou_75 = int(
            np.sum(
                ious >= 0.75
            )
        )

    else:
        mean_iou = np.nan
        mean_start = np.nan
        mean_end = np.nan
        match_iou_50 = 0
        match_iou_75 = 0

    return {
        "video_id": video_id,
        "exercise_id": exercise_id,
        "gt_reps": n_gt,
        "pred_reps": n_pred,
        "matched_reps": n_match,
        "count_error": n_pred - n_gt,
        "abs_count_error": abs(
            n_pred - n_gt
        ),
        "mean_iou": mean_iou,
        "mean_abs_start_error": mean_start,
        "mean_abs_end_error": mean_end,
        "matches_iou_50": match_iou_50,
        "matches_iou_75": match_iou_75,
        "recall_any_overlap": (
            n_match / n_gt
            if n_gt > 0
            else np.nan
        ),
        "recall_iou_50": (
            match_iou_50 / n_gt
            if n_gt > 0
            else np.nan
        ),
        "precision_iou_50": (
            match_iou_50 / n_pred
            if n_pred > 0
            else np.nan
        ),
    }


def run_segmentation(
    video_path,
    output_dir,
    clips=False,
    exercise_config=None
):
    command = [
        sys.executable,
        str(MAIN_SCRIPT),
        str(video_path),
        "--output",
        str(output_dir),
    ]

    if exercise_config is not None:
        command.extend([
            "--exercise-config",
            str(exercise_config),
        ])

    if clips:
        command.append(
            "--clips"
        )

    print(
        "\n"
        + "=" * 80
    )

    print(
        f"SEGMENTAZIONE: {video_path.name}"
    )

    print(
        "=" * 80
    )

    result = subprocess.run(
        command,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"main.py terminato con codice "
            f"{result.returncode}"
        )


def find_camera17_videos(
    dataset_root,
    exercise=None
):
    if exercise is not None:
        folders = [
            dataset_root
            / f"Ex{exercise}"
        ]
    else:
        folders = sorted(
            dataset_root.glob(
                "Ex*"
            )
        )

    videos = []

    for folder in folders:
        if not folder.exists():
            continue

        videos.extend(
            sorted(
                folder.glob(
                    "*-Camera17-30fps.mp4"
                )
            )
        )

    return videos


def print_video_result(
    summary,
    unmatched_gt,
    unmatched_pred
):
    print(
        "\nVALIDAZIONE:"
    )

    print(
        f"GT={summary['gt_reps']} | "
        f"Pred={summary['pred_reps']} | "
        f"Match={summary['matched_reps']} | "
        f"IoU={summary['mean_iou']:.3f}"
        if not pd.isna(
            summary["mean_iou"]
        )
        else
        f"GT={summary['gt_reps']} | "
        f"Pred={summary['pred_reps']} | "
        f"Match={summary['matched_reps']} | "
        f"IoU=n/a"
    )

    if not pd.isna(
        summary[
            "mean_abs_start_error"
        ]
    ):
        print(
            "Errore medio start="
            f"{summary['mean_abs_start_error']:.1f} frame | "
            "end="
            f"{summary['mean_abs_end_error']:.1f} frame"
        )

    print(
        f"GT non trovate: {len(unmatched_gt)} | "
        f"Pred senza match: {len(unmatched_pred)}"
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Validazione batch del segmentatore "
            "REHAB24-6 con matching Hungarian."
        )
    )

    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DEFAULT_DATASET_ROOT
    )

    parser.add_argument(
        "--annotations",
        type=Path,
        default=DEFAULT_ANNOTATIONS
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT
    )

    parser.add_argument(
        "--exercise",
        type=int,
        default=None,
        help=(
            "Valida solo ExN, ad esempio --exercise 3"
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Numero massimo di video da validare."
        )
    )

    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help=(
            "Non riesegue main.py se segments_all.csv "
            "esiste già."
        )
    )

    parser.add_argument(
        "--clips",
        action="store_true",
        help=(
            "Esporta anche i clip durante la validazione. "
            "Di default non lo fa per risparmiare tempo/spazio."
        )
    )

    parser.add_argument(
        "--exercise-config",
        type=Path,
        default=None,
        help=(
            "JSON con guide_angle e direction da riutilizzare "
            "per tutti i video dell'esercizio."
        )
    )

    args = parser.parse_args()

    if not args.annotations.exists():
        raise FileNotFoundError(
            f"Annotazioni non trovate: "
            f"{args.annotations}"
        )

    if not args.dataset_root.exists():
        raise FileNotFoundError(
            f"Dataset non trovato: "
            f"{args.dataset_root}"
        )

    if (
        args.exercise_config is not None
        and not args.exercise_config.exists()
    ):
        raise FileNotFoundError(
            f"Configurazione esercizio non trovata: "
            f"{args.exercise_config}"
        )

    annotations = load_annotations(
        args.annotations
    )

    videos = find_camera17_videos(
        args.dataset_root,
        exercise=args.exercise
    )

    if args.limit is not None:
        videos = videos[
            :args.limit
        ]

    if not videos:
        raise RuntimeError(
            "Nessun video Camera17 trovato."
        )

    args.output_root.mkdir(
        parents=True,
        exist_ok=True
    )

    print(
        f"Video da validare: {len(videos)}"
    )

    summaries = []
    failed = []

    for position, video_path in enumerate(
        videos,
        start=1
    ):
        try:
            video_id, exercise_id = (
                parse_video_info(
                    video_path
                )
            )

            print(
                "\n"
                + "#" * 80
            )

            print(
                f"[{position}/{len(videos)}] "
                f"{video_id} - Ex{exercise_id}"
            )

            output_dir = (
                args.output_root
                / f"Ex{exercise_id}"
                / video_id
            )

            predictions_path = (
                output_dir
                / "segments_all.csv"
            )

            if not (
                args.skip_existing
                and predictions_path.exists()
            ):
                output_dir.mkdir(
                    parents=True,
                    exist_ok=True
                )

                run_segmentation(
                    video_path,
                    output_dir,
                    clips=args.clips,
                    exercise_config=args.exercise_config
                )

            gt = ground_truth_for_video(
                annotations,
                video_id,
                exercise_id
            )

            if len(gt) == 0:
                print(
                    "ATTENZIONE: nessuna annotazione GT trovata. "
                    "Video saltato."
                )
                failed.append({
                    "video_id": video_id,
                    "exercise_id": exercise_id,
                    "reason": "ground_truth_missing",
                })
                continue

            pred = load_predictions(
                predictions_path
            )

            (
                matches,
                unmatched_gt,
                unmatched_pred
            ) = hungarian_match(
                gt,
                pred
            )

            summary = summarize_video(
                video_id,
                exercise_id,
                gt,
                pred,
                matches
            )

            summaries.append(
                summary
            )

            match_path = (
                output_dir
                / "validation_matches.csv"
            )

            pd.DataFrame(
                matches
            ).to_csv(
                match_path,
                index=False
            )

            unmatched_gt_rows = []

            for idx in unmatched_gt:
                row = gt.loc[idx]

                unmatched_gt_rows.append({
                    "gt_rep": (
                        int(
                            row["repetition_number"]
                        )
                        if pd.notna(
                            row["repetition_number"]
                        )
                        else idx + 1
                    ),
                    "correctness": str(
                        row["correctness"]
                    ),
                    "first_frame": int(
                        row["first_frame"]
                    ),
                    "last_frame": int(
                        row["last_frame"]
                    ),
                })

            pd.DataFrame(
                unmatched_gt_rows
            ).to_csv(
                output_dir
                / "validation_unmatched_gt.csv",
                index=False
            )

            unmatched_pred_rows = []

            for idx in unmatched_pred:
                row = pred.loc[idx]

                unmatched_pred_rows.append({
                    "pred_index": idx + 1,
                    "start_frame": int(
                        row["start_frame"]
                    ),
                    "end_frame": int(
                        row["end_frame"]
                    ),
                })

            pd.DataFrame(
                unmatched_pred_rows
            ).to_csv(
                output_dir
                / "validation_unmatched_pred.csv",
                index=False
            )

            print_video_result(
                summary,
                unmatched_gt,
                unmatched_pred
            )

        except Exception as exc:
            print(
                f"ERRORE: {exc}"
            )

            failed.append({
                "video": str(
                    video_path
                ),
                "reason": str(
                    exc
                ),
            })

    if not summaries:
        raise RuntimeError(
            "Nessun video validato con successo."
        )

    summary_df = pd.DataFrame(
        summaries
    )

    summary_path = (
        args.output_root
        / "validation_summary.csv"
    )

    summary_df.to_csv(
        summary_path,
        index=False
    )

    # Riepilogo per esercizio.
    exercise_summary = (
        summary_df
        .groupby(
            "exercise_id",
            as_index=False
        )
        .agg(
            videos=("video_id", "count"),
            gt_reps=("gt_reps", "sum"),
            pred_reps=("pred_reps", "sum"),
            matched_reps=(
                "matched_reps",
                "sum"
            ),
            mean_iou=(
                "mean_iou",
                "mean"
            ),
            mean_abs_start_error=(
                "mean_abs_start_error",
                "mean"
            ),
            mean_abs_end_error=(
                "mean_abs_end_error",
                "mean"
            ),
            mean_abs_count_error=(
                "abs_count_error",
                "mean"
            ),
            recall_iou_50=(
                "recall_iou_50",
                "mean"
            ),
            precision_iou_50=(
                "precision_iou_50",
                "mean"
            ),
        )
    )

    exercise_summary_path = (
        args.output_root
        / "validation_by_exercise.csv"
    )

    exercise_summary.to_csv(
        exercise_summary_path,
        index=False
    )

    if failed:
        pd.DataFrame(
            failed
        ).to_csv(
            args.output_root
            / "validation_failed.csv",
            index=False
        )

    print(
        "\n"
        + "=" * 80
    )

    print(
        "RIEPILOGO COMPLESSIVO"
    )

    print(
        "=" * 80
    )

    print(
        summary_df[
            [
                "video_id",
                "exercise_id",
                "gt_reps",
                "pred_reps",
                "matched_reps",
                "mean_iou",
                "mean_abs_start_error",
                "mean_abs_end_error",
            ]
        ].to_string(
            index=False
        )
    )

    print(
        "\nMedia IoU per video: "
        f"{summary_df['mean_iou'].mean():.3f}"
    )

    print(
        "Errore medio assoluto conteggio: "
        f"{summary_df['abs_count_error'].mean():.2f} REP"
    )

    print(
        "Errore medio start: "
        f"{summary_df['mean_abs_start_error'].mean():.1f} frame"
    )

    print(
        "Errore medio end: "
        f"{summary_df['mean_abs_end_error'].mean():.1f} frame"
    )

    print(
        f"\nSalvato: {summary_path}"
    )

    print(
        f"Salvato: {exercise_summary_path}"
    )


if __name__ == "__main__":
    main()
