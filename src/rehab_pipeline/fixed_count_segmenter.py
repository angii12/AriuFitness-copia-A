import numpy as np

from hybrid_segmenter import segment_repetitions


def _select_exact_n_from_valid_segments(segments, n):
    """Seleziona esattamente N cicli gia' validati dal motore automatico v5."""
    n = int(n)
    if n < 1:
        raise ValueError("expected_reps deve essere >= 1")

    if len(segments) < n:
        return None
    if len(segments) == n:
        return [dict(s) for s in segments]

    durations = np.asarray(
        [float(s.get("duration_frames", 0)) for s in segments],
        dtype=float,
    )
    median_duration = float(np.median(durations)) if len(durations) else 1.0

    scored = []
    for idx, segment in enumerate(segments):
        duration = float(segment.get("duration_frames", median_duration))
        duration_error = abs(duration - median_duration) / max(median_duration, 1.0)
        confidence = float(segment.get("confidence", 0.5))
        # Preferisce cicli ben supportati e con durata coerente, senza alterare i confini.
        score = confidence - 0.35 * duration_error
        scored.append((score, idx))

    keep = sorted(idx for _, idx in sorted(scored, reverse=True)[:n])
    return [dict(segments[i]) for i in keep]


def segment_fixed_count(
    df,
    fps,
    expected_reps,
    guide_angle=None,
    direction=None,
    guide_signals=None,
    doctor_guided=False,
):
    """
    Modalita' FIXED costruita direttamente sopra il motore automatico v5.

    1. Il motore automatico trova SOLO cicli completi validi.
    2. Il numero atteso aiuta la scelta del segnale.
    3. Solo alla fine vengono mantenute esattamente N REP valide.

    Non viene mai diviso il video in N intervalli temporali uguali e non sono
    ammessi cicli parziali per raggiungere artificialmente N.
    """
    expected_reps = int(expected_reps)
    if expected_reps < 1:
        raise ValueError("expected_reps deve essere >= 1")

    all_segments, _, base_metadata, candidates = segment_repetitions(
        df,
        fps,
        guide_angle=guide_angle,
        direction=direction,
        guide_signals=guide_signals,
        expected_reps=expected_reps,
        doctor_guided=doctor_guided,
    )

    eligible_segments = [
        s for s in all_segments
        if bool(s.get("training_eligible", True))
    ]
    selected = _select_exact_n_from_valid_segments(eligible_segments, expected_reps)
    if selected is None:
        raise RuntimeError(
            f"Sono stati trovati solo {len(eligible_segments)} cicli completi validi e utilizzabili, "
            f"ma ne sono richiesti {expected_reps}. Non vengono create REP artificiali."
        )

    for i, seg in enumerate(selected, start=1):
        seg["rep"] = i

    metadata = dict(base_metadata)
    metadata.update({
        "segmentation_mode": "hybrid_v5_fixed_exact_n",
        "rep_mode": "fixed",
        "expected_reps": expected_reps,
        "detected_valid_cycles_before_fixed_selection": len(eligible_segments),
        "detected_reps": len(selected),
        "used_reps": len(selected),
        "expected_reps_role": "exact_valid_cycle_count",
        "time_equal_splitting": False,
        "partial_cycles_allowed": False,
        "status": "ok",
    })

    return all_segments, selected, metadata, candidates
