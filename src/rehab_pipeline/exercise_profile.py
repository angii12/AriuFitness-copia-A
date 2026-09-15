import argparse
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from hybrid_segmenter import rank_rest_signals
from joint_selection import AVAILABLE_JOINTS, build_allowed_signals, normalize_selected_joints


def build_profile(angle_files, fps=30.0, top_n=3, selection_mode="auto", selected_joints=None):
    """
    Impara quali articolazioni descrivono meglio l'esercizio su più video.
    Non salva un periodo fisso. La direzione preferita viene salvata come
    riferimento, ma può adattarsi nel singolo video.
    """
    selection_mode = str(selection_mode).strip().lower()
    if selection_mode not in {"auto", "doctor_guided"}:
        raise ValueError("selection_mode deve essere 'auto' oppure 'doctor_guided'.")

    selected_joints = normalize_selected_joints(selected_joints)
    if selection_mode == "doctor_guided" and not selected_joints:
        raise ValueError(
            "In modalita' doctor_guided devi selezionare almeno un'articolazione."
        )

    allowed_signals = (
        build_allowed_signals(selected_joints)
        if selection_mode == "doctor_guided"
        else None
    )

    aggregate = defaultdict(lambda: {
        "videos_seen": 0,
        "quality_sum": 0.0,
        "top_votes": 0,
        "increase_votes": 0,
        "decrease_votes": 0,
    })

    processed = 0
    for angle_file in angle_files:
        df = pd.read_csv(angle_file)
        if df.empty:
            continue

        candidates = rank_rest_signals(df, fps, signals=allowed_signals)
        if not candidates:
            continue

        processed += 1
        for rank, candidate in enumerate(candidates, start=1):
            angle = candidate["angle"]
            stats = aggregate[angle]
            stats["videos_seen"] += 1
            stats["quality_sum"] += float(candidate["score"])
            if rank == 1:
                stats["top_votes"] += 1
            if candidate["direction"] == "increase":
                stats["increase_votes"] += 1
            else:
                stats["decrease_votes"] += 1

    if processed == 0:
        raise RuntimeError("Nessun file angles.csv valido trovato.")

    ranking = []
    for angle, stats in aggregate.items():
        coverage = stats["videos_seen"] / processed
        mean_quality = stats["quality_sum"] / max(stats["videos_seen"], 1)
        top_fraction = stats["top_votes"] / processed
        total_dir_votes = stats["increase_votes"] + stats["decrease_votes"]
        preferred_direction = (
            "increase"
            if stats["increase_votes"] > stats["decrease_votes"]
            else "decrease"
        )
        direction_agreement = (
            max(stats["increase_votes"], stats["decrease_votes"]) / max(total_dir_votes, 1)
        )
        aggregate_score = 0.50 * coverage + 0.30 * mean_quality + 0.20 * top_fraction
        ranking.append({
            "angle": angle,
            "preferred_direction": preferred_direction,
            "direction_agreement": direction_agreement,
            "videos_seen": stats["videos_seen"],
            "coverage": coverage,
            "mean_quality": mean_quality,
            "top_votes": stats["top_votes"],
            "aggregate_score": aggregate_score,
        })

    ranking.sort(key=lambda item: item["aggregate_score"], reverse=True)
    selected = ranking[:max(1, top_n)]
    max_score = max(selected[0]["aggregate_score"], 1e-9)

    guide_signals = []
    for item in selected:
        guide_signals.append({
            "angle": item["angle"],
            "preferred_direction": item["preferred_direction"],
            "adaptive_direction": True,
            "weight": float(item["aggregate_score"] / max_score),
        })

    return {
        "segmentation_mode": "adaptive_rest_to_rest_multi_angle",
        "period_mode": "diagnostic_only",
        "source_videos": processed,
        "selection_method": "multi_video_rest_to_rest_consensus",
        "signal_selection_mode": selection_mode,
        "doctor_selected_joints": selected_joints if selection_mode == "doctor_guided" else [],
        "allowed_angles": [s["angle"] for s in allowed_signals] if allowed_signals else None,
        "guide_signals": guide_signals,
        "ranking": ranking,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Crea il profilo multi-angolo di un esercizio dai file angles.csv."
    )
    parser.add_argument("angles_root", type=Path)
    parser.add_argument("--output", type=Path, default=Path("output/exercise_config.json"))
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument(
        "--selection-mode",
        choices=["auto", "doctor_guided"],
        default="auto",
        help="AUTO usa tutti gli 8 angoli; DOCTOR_GUIDED limita il ranking alle articolazioni scelte.",
    )
    parser.add_argument(
        "--selected-joints",
        nargs="+",
        choices=AVAILABLE_JOINTS,
        default=None,
        help="Articolazioni selezionate dal medico (richieste in doctor_guided).",
    )
    args = parser.parse_args()

    files = sorted(args.angles_root.rglob("angles.csv"))
    if not files:
        files = sorted(args.angles_root.rglob("*_angles.csv"))
    if not files:
        raise FileNotFoundError(f"Nessun angles.csv trovato in {args.angles_root}")

    profile = build_profile(
        files,
        fps=args.fps,
        top_n=args.top_n,
        selection_mode=args.selection_mode,
        selected_joints=args.selected_joints,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    print("Profilo esercizio creato.")
    print(f"Selezione segnali: {profile['signal_selection_mode'].upper()}")
    if profile["doctor_selected_joints"]:
        print("Articolazioni medico: " + ", ".join(profile["doctor_selected_joints"]))
    for signal in profile["guide_signals"]:
        print(
            f"- {signal['angle']} | preferenza={signal['preferred_direction']} | "
            f"peso={signal['weight']:.3f} | direzione adattiva"
        )
    print("Periodo: non usato per delimitare le REP.")
    print(f"Salvato: {args.output}")


if __name__ == "__main__":
    main()
