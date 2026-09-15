import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from exercise_profile import build_profile
from validation import (
    find_camera17_videos,
    ground_truth_for_video,
    hungarian_match,
    load_annotations,
    load_predictions,
    parse_video_info,
    summarize_video,
)


DEFAULT_DATASET_ROOT = Path(r"C:\Users\Utente\Desktop\videos")
DEFAULT_ANNOTATIONS = Path("data/annotations/Segmentation.csv")
DEFAULT_OUTPUT_ROOT = Path("output/final_experiments")
DEFAULT_CONFIG_ROOT = Path("configs")
MAIN_SCRIPT = Path("src/main.py")


def run_main(video_path, output_dir, exercise_config=None):
    output_dir.mkdir(parents=True, exist_ok=True)

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

    result = subprocess.run(
        command,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"main.py fallito per {video_path.name} "
            f"(codice {result.returncode})"
        )


def choose_profile_and_test_videos(videos, profile_count=None):
    """
    Split deterministico e riproducibile.

    Di default usa circa il 30% dei video per costruire il profilo,
    con almeno 3 video quando disponibili, e il resto per il test.

    Il ground truth NON viene usato per creare il profilo.
    """
    videos = sorted(videos)

    n = len(videos)

    if n < 2:
        return videos, []

    if profile_count is None:
        profile_count = max(
            3,
            int(math.ceil(0.30 * n))
        )

    profile_count = min(
        max(1, profile_count),
        n - 1
    )

    # Distribuiamo i video profilo lungo l'elenco, invece di prendere
    # semplicemente i primi N. Lo split resta deterministico.
    if profile_count == 1:
        profile_indices = {0}
    else:
        profile_indices = {
            int(round(x))
            for x in np.linspace(
                0,
                n - 1,
                profile_count
            )
        }

    # In casi di arrotondamento, completiamo fino al numero richiesto.
    if len(profile_indices) < profile_count:
        for idx in range(n):
            profile_indices.add(idx)
            if len(profile_indices) >= profile_count:
                break

    profile_videos = [
        video
        for idx, video in enumerate(videos)
        if idx in profile_indices
    ]

    test_videos = [
        video
        for idx, video in enumerate(videos)
        if idx not in profile_indices
    ]

    return profile_videos, test_videos


def build_exercise_config(
    exercise_id,
    profile_videos,
    output_root,
    config_root,
    fps,
    top_n,
):
    profile_root = (
        output_root
        / f"Ex{exercise_id}"
        / "profile_videos"
    )

    angle_files = []

    print(
        "\n"
        + "=" * 80
    )
    print(
        f"EX{exercise_id} - CREAZIONE PROFILO"
    )
    print(
        "=" * 80
    )

    for position, video_path in enumerate(
        profile_videos,
        start=1
    ):
        video_id, _ = parse_video_info(
            video_path
        )

        output_dir = (
            profile_root
            / video_id
        )

        angles_path = (
            output_dir
            / "angles.csv"
        )

        print(
            f"[profilo {position}/{len(profile_videos)}] "
            f"{video_path.name}"
        )

        if not angles_path.exists():
            run_main(
                video_path,
                output_dir,
                exercise_config=None,
            )

        if not angles_path.exists():
            raise FileNotFoundError(
                f"angles.csv non creato per {video_path.name}"
            )

        angle_files.append(
            angles_path
        )

    profile = build_profile(
        angle_files,
        fps=fps,
        top_n=top_n,
    )

    # Metadati utili per rendere l'esperimento riproducibile.
    profile["exercise_id"] = exercise_id
    profile["profile_video_ids"] = [
        parse_video_info(video)[0]
        for video in profile_videos
    ]
    profile["profile_video_count"] = len(
        profile_videos
    )
    profile["evaluation_note"] = (
        "Profilo costruito senza usare first_frame, last_frame o correctness."
    )

    config_root.mkdir(
        parents=True,
        exist_ok=True
    )

    config_path = (
        config_root
        / f"ex{exercise_id}.json"
    )

    config_path.write_text(
        json.dumps(
            profile,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        "\nProfilo salvato:",
        config_path
    )

    for signal in profile[
        "guide_signals"
    ]:
        print(
            f"- {signal['angle']} | "
            f"preferenza={signal['preferred_direction']} | "
            f"peso={signal['weight']:.3f}"
        )

    return config_path


def validate_test_videos(
    exercise_id,
    test_videos,
    config_path,
    annotations,
    output_root,
):
    validation_root = (
        output_root
        / f"Ex{exercise_id}"
        / "test_videos"
    )

    summaries = []
    failures = []

    print(
        "\n"
        + "=" * 80
    )
    print(
        f"EX{exercise_id} - VALIDAZIONE SU VIDEO NON USATI NEL PROFILO"
    )
    print(
        "=" * 80
    )

    for position, video_path in enumerate(
        test_videos,
        start=1
    ):
        video_id, parsed_exercise_id = (
            parse_video_info(
                video_path
            )
        )

        output_dir = (
            validation_root
            / video_id
        )

        print(
            "\n"
            + "-" * 80
        )
        print(
            f"[test {position}/{len(test_videos)}] "
            f"{video_id}"
        )

        try:
            run_main(
                video_path,
                output_dir,
                exercise_config=config_path,
            )

            gt = ground_truth_for_video(
                annotations,
                video_id,
                parsed_exercise_id,
            )

            if len(gt) == 0:
                raise RuntimeError(
                    "Ground truth non trovato."
                )

            pred = load_predictions(
                output_dir
                / "segments_all.csv"
            )

            (
                matches,
                unmatched_gt,
                unmatched_pred
            ) = hungarian_match(
                gt,
                pred,
            )

            summary = summarize_video(
                video_id,
                parsed_exercise_id,
                gt,
                pred,
                matches,
            )

            summaries.append(
                summary
            )

            pd.DataFrame(
                matches
            ).to_csv(
                output_dir
                / "validation_matches.csv",
                index=False,
            )

            print(
                f"GT={summary['gt_reps']} | "
                f"Pred={summary['pred_reps']} | "
                f"Match={summary['matched_reps']} | "
                f"IoU={summary['mean_iou']:.3f} | "
                f"|count error|={summary['abs_count_error']}"
            )

        except Exception as exc:
            print(
                f"ERRORE: {exc}"
            )

            failures.append({
                "exercise_id": exercise_id,
                "video_id": video_id,
                "reason": str(exc),
            })

    return summaries, failures


def aggregate_results(summary_df):
    if summary_df.empty:
        return pd.DataFrame()

    grouped = (
        summary_df
        .groupby(
            "exercise_id",
            as_index=False
        )
        .agg(
            test_videos=(
                "video_id",
                "count"
            ),
            gt_reps=(
                "gt_reps",
                "sum"
            ),
            pred_reps=(
                "pred_reps",
                "sum"
            ),
            matched_reps=(
                "matched_reps",
                "sum"
            ),
            mean_iou=(
                "mean_iou",
                "mean"
            ),
            mean_abs_count_error=(
                "abs_count_error",
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

    return grouped


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Costruisce un profilo multi-angolo per ogni esercizio "
            "e lo valida su video separati."
        )
    )

    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
    )

    parser.add_argument(
        "--annotations",
        type=Path,
        default=DEFAULT_ANNOTATIONS,
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
    )

    parser.add_argument(
        "--config-root",
        type=Path,
        default=DEFAULT_CONFIG_ROOT,
    )

    parser.add_argument(
        "--exercises",
        nargs="+",
        type=int,
        default=[1, 2, 3, 4, 5, 6],
    )

    parser.add_argument(
        "--profile-count",
        type=int,
        default=None,
        help=(
            "Numero di video usati per creare il profilo di ogni esercizio. "
            "Default: circa 30%, minimo 3 quando possibile."
        ),
    )

    parser.add_argument(
        "--top-n",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--fps",
        type=float,
        default=30.0,
    )

    args = parser.parse_args()

    if not args.dataset_root.exists():
        raise FileNotFoundError(
            f"Dataset non trovato: {args.dataset_root}"
        )

    if not args.annotations.exists():
        raise FileNotFoundError(
            f"Annotazioni non trovate: {args.annotations}"
        )

    annotations = load_annotations(
        args.annotations
    )

    args.output_root.mkdir(
        parents=True,
        exist_ok=True
    )

    all_summaries = []
    all_failures = []
    split_rows = []

    for exercise_id in args.exercises:
        videos = find_camera17_videos(
            args.dataset_root,
            exercise=exercise_id,
        )

        if not videos:
            print(
                f"\nEx{exercise_id}: nessun video trovato, salto."
            )
            continue

        (
            profile_videos,
            test_videos
        ) = choose_profile_and_test_videos(
            videos,
            profile_count=args.profile_count,
        )

        print(
            "\n"
            + "#" * 80
        )
        print(
            f"EX{exercise_id}: "
            f"{len(videos)} video totali | "
            f"{len(profile_videos)} profilo | "
            f"{len(test_videos)} test"
        )
        print(
            "#" * 80
        )

        for video in profile_videos:
            split_rows.append({
                "exercise_id": exercise_id,
                "video_id": parse_video_info(video)[0],
                "split": "profile",
            })

        for video in test_videos:
            split_rows.append({
                "exercise_id": exercise_id,
                "video_id": parse_video_info(video)[0],
                "split": "test",
            })

        try:
            config_path = (
                build_exercise_config(
                    exercise_id=exercise_id,
                    profile_videos=profile_videos,
                    output_root=args.output_root,
                    config_root=args.config_root,
                    fps=args.fps,
                    top_n=args.top_n,
                )
            )

            summaries, failures = (
                validate_test_videos(
                    exercise_id=exercise_id,
                    test_videos=test_videos,
                    config_path=config_path,
                    annotations=annotations,
                    output_root=args.output_root,
                )
            )

            all_summaries.extend(
                summaries
            )

            all_failures.extend(
                failures
            )

        except Exception as exc:
            print(
                f"ERRORE GENERALE Ex{exercise_id}: {exc}"
            )

            all_failures.append({
                "exercise_id": exercise_id,
                "video_id": "",
                "reason": str(exc),
            })

    pd.DataFrame(
        split_rows
    ).to_csv(
        args.output_root
        / "profile_test_split.csv",
        index=False,
    )

    summary_df = pd.DataFrame(
        all_summaries
    )

    if summary_df.empty:
        if all_failures:
            pd.DataFrame(
                all_failures
            ).to_csv(
                args.output_root
                / "validation_failed.csv",
                index=False,
            )

        raise RuntimeError(
            "Nessun video di test validato con successo."
        )

    summary_df.to_csv(
        args.output_root
        / "validation_summary.csv",
        index=False,
    )

    exercise_df = aggregate_results(
        summary_df
    )

    exercise_df.to_csv(
        args.output_root
        / "validation_by_exercise.csv",
        index=False,
    )

    if all_failures:
        pd.DataFrame(
            all_failures
        ).to_csv(
            args.output_root
            / "validation_failed.csv",
            index=False,
        )

    print(
        "\n"
        + "=" * 100
    )
    print(
        "RISULTATO FINALE PER ESERCIZIO"
    )
    print(
        "=" * 100
    )

    print(
        exercise_df.to_string(
            index=False
        )
    )

    print(
        "\n"
        + "=" * 100
    )
    print(
        "RISULTATO COMPLESSIVO"
    )
    print(
        "=" * 100
    )

    print(
        f"Video di test: {len(summary_df)}"
    )

    print(
        "IoU medio: "
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
        "Recall IoU>=0.50 medio: "
        f"{summary_df['recall_iou_50'].mean():.3f}"
    )

    print(
        "Precision IoU>=0.50 media: "
        f"{summary_df['precision_iou_50'].mean():.3f}"
    )

    print(
        f"\nRisultati salvati in: {args.output_root}"
    )


if __name__ == "__main__":
    main()
