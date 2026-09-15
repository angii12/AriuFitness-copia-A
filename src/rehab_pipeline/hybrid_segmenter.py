import numpy as np
import pandas as pd
from scipy.signal import find_peaks, savgol_filter

from config import (
    ANGLE_COLUMNS,
    MAX_REP_SECONDS,
    MAX_REPS_FOR_TRAINING,
    MIN_REP_SECONDS,
    MIN_REPS_ACCEPTED,
)

REST_LEVEL = 0.22
PEAK_LEVEL = 0.50

# Una REP valida deve essere un ciclo completo: riposo -> estremo -> riposo.
# Queste soglie sono espresse sul segnale normalizzato e valgono per tutti
# gli esercizi/profili, non per un esercizio specifico.
FULL_CYCLE_REST_CEILING = 0.38
MIN_PHASE_SECONDS = 0.25
REST_HOLD_SECONDS = 0.15

# Gestione segmenti anormalmente lunghi. Se un tratto contiene piu cicli
# completi ma il ritorno al riposo globale non e abbastanza netto, proviamo
# a separarlo usando picchi prominenti e minimi locali.
OVERSIZED_FACTOR = 2.20
INTERNAL_PEAK_MIN_HEIGHT = 0.42
INTERNAL_PEAK_MIN_PROMINENCE = 0.16
LOCAL_RETURN_FRACTION = 0.55


def _smooth(signal, fps):
    x = np.array(signal, dtype=float, copy=True)
    x[~np.isfinite(x)] = np.nan
    series = pd.Series(x).interpolate(method="linear", limit_direction="both")
    if series.isna().any():
        valid = series.dropna()
        if len(valid) == 0:
            return np.zeros(len(series), dtype=float)
        series = series.fillna(float(valid.median()))

    x = series.to_numpy(dtype=float, copy=True)
    x[~np.isfinite(x)] = 0.0
    if len(x) < 7:
        return x

    window = max(7, int(round(0.25 * fps)))
    if window % 2 == 0:
        window += 1
    max_window = len(x) if len(x) % 2 == 1 else len(x) - 1
    window = min(window, max_window)
    if window < 5:
        return x

    try:
        return savgol_filter(x, window_length=window, polyorder=min(3, window - 1))
    except ValueError:
        return x


def _directional_signal(smoothed, direction):
    q10, q90 = np.percentile(smoothed, [10, 90])
    amplitude = float(q90 - q10)
    if amplitude < 1e-6:
        return None, amplitude

    if direction == "decrease":
        normalized = (q90 - smoothed) / amplitude
    else:
        normalized = (smoothed - q10) / amplitude

    return np.clip(normalized, 0.0, 1.5), amplitude


def _extract_rest_to_rest_cycles(normalized, fps):
    """
    Estrae cicli usando estremi locali + minimi locali, invece di richiedere
    che ogni REP attraversi sempre le stesse soglie globali.

    Questo evita due errori tipici:
    - false negative quando una REP ha ROM ridotto e non torna esattamente a REST_LEVEL;
    - false positive dovuti a piccole oscillazioni, filtrate tramite prominence,
      escursione locale e durata minima.
    """
    x = np.asarray(normalized, dtype=float)
    n = len(x)
    if n < 5:
        return []

    min_len = max(2, int(round(MIN_REP_SECONDS * fps)))
    max_len = max(min_len + 1, int(round(MAX_REP_SECONDS * fps)))

    # La distanza tra estremi è volutamente meno rigida della durata minima
    # rest-to-rest: serve solo a non contare due volte lo stesso gesto.
    min_peak_distance = max(2, int(round(0.55 * MIN_REP_SECONDS * fps)))

    # Soglie relativamente permissive: la decisione finale usa anche
    # l'escursione rispetto ai minimi locali e il supporto multi-angolo.
    peaks, properties = find_peaks(
        x,
        height=0.30,
        prominence=0.12,
        distance=min_peak_distance,
    )

    if len(peaks) == 0:
        return []

    # Elimina picchi molto deboli rispetto al comportamento del video senza
    # imporre una ROM assoluta uguale per tutte le persone.
    peak_values = x[peaks]
    # Non alziamo la soglia in base alle REP più ampie: una singola REP con ROM
    # ridotto è comunque una REP e deve poter essere segmentata. Il rumore viene
    # già filtrato da prominence + escursione locale + durata.
    adaptive_peak_floor = 0.30
    peaks = peaks[peak_values >= adaptive_peak_floor]
    if len(peaks) == 0:
        return []

    # Confini: minimo locale tra due picchi consecutivi. Per i bordi del video
    # cerchiamo il minimo in una finestra ampia ma fisicamente plausibile.
    boundaries = []
    for i in range(len(peaks) - 1):
        left = int(peaks[i])
        right = int(peaks[i + 1])
        valley = left + int(np.argmin(x[left:right + 1]))
        boundaries.append(valley)

    cycles = []
    for i, peak in enumerate(peaks):
        peak = int(peak)

        if i == 0:
            left_limit = max(0, peak - max_len)
            start = left_limit + int(np.argmin(x[left_limit:peak + 1]))
        else:
            start = int(boundaries[i - 1])

        if i == len(peaks) - 1:
            right_limit = min(n - 1, peak + max_len)
            end = peak + int(np.argmin(x[peak:right_limit + 1]))
        else:
            end = int(boundaries[i])

        duration = end - start
        if not (min_len <= duration <= max_len):
            continue

        left_valley = float(x[start])
        right_valley = float(x[end])
        peak_value = float(x[peak])
        local_base = max(left_valley, right_valley)
        local_excursion = peak_value - local_base

        # Una REP deve emergere chiaramente dal proprio riposo locale.
        if local_excursion < 0.18:
            continue

        # CICLO COMPLETO GENERALE. Non basta trovare un picco: prima del picco
        # dobbiamo avere osservato il riposo e, dopo il picco, dobbiamo tornarci.
        # Questo elimina le pseudo-REP quando il video inizia gia' nel punto
        # estremo e mostra soltanto la fase di ritorno.
        if left_valley > FULL_CYCLE_REST_CEILING or right_valley > FULL_CYCLE_REST_CEILING:
            continue

        min_phase = max(2, int(round(MIN_PHASE_SECONDS * fps)))
        if (peak - start) < min_phase or (end - peak) < min_phase:
            continue

        # Il riposo deve essere realmente osservato per piu' di un singolo frame
        # rumoroso. Verifichiamo una piccola finestra intorno ai due confini.
        hold = max(2, int(round(REST_HOLD_SECONDS * fps)))
        pre_lo = max(0, start - hold)
        pre_hi = min(n, start + hold + 1)
        post_lo = max(0, end - hold)
        post_hi = min(n, end + hold + 1)
        pre_rest_fraction = float(np.mean(x[pre_lo:pre_hi] <= FULL_CYCLE_REST_CEILING))
        post_rest_fraction = float(np.mean(x[post_lo:post_hi] <= FULL_CYCLE_REST_CEILING))
        if pre_rest_fraction < 0.60 or post_rest_fraction < 0.60:
            continue

        cycles.append({
            "start_idx": int(start),
            "peak_idx": int(peak),
            "end_idx": int(end),
            "peak_value": peak_value,
            "duration_idx": int(duration),
            "local_excursion": float(local_excursion),
        })

    return cycles



def _split_oversized_cycles(cycles, normalized, fps):
    """
    Divide un ciclo anormalmente lungo quando contiene piu movimenti completi
    plausibili. Le piccole aperture/finte partenze vengono ignorate richiedendo
    picchi abbastanza alti e prominenti e un ritorno locale marcato tra due picchi.

    La regola e generale: usa solo forma, durata e ampiezza del segnale normalizzato,
    non conosce il nome dell'esercizio.
    """
    if not cycles:
        return []

    x = np.asarray(normalized, dtype=float)
    min_len = max(2, int(round(MIN_REP_SECONDS * fps)))
    max_len = max(min_len + 1, int(round(MAX_REP_SECONDS * fps)))

    durations = np.asarray([c["duration_idx"] for c in cycles], dtype=float)
    # Stima robusta della durata normale. Se c'e un outlier enorme, non deve
    # trascinare verso l'alto la soglia che serve proprio a riconoscerlo.
    if len(durations) >= 3:
        q75 = float(np.percentile(durations, 75))
        normal = durations[durations <= q75]
        typical = float(np.median(normal)) if len(normal) else float(np.median(durations))
    else:
        typical = float(np.median(durations))
    typical = max(typical, float(min_len))

    result = []
    for cycle in cycles:
        start = int(cycle["start_idx"])
        end = int(cycle["end_idx"])
        duration = end - start

        if duration <= min(max_len, int(round(OVERSIZED_FACTOR * typical))):
            result.append(cycle)
            continue

        piece = x[start:end + 1]
        if len(piece) < 2 * min_len:
            result.append(cycle)
            continue

        min_peak_distance = max(2, int(round(0.55 * min_len)))
        internal_peaks, props = find_peaks(
            piece,
            height=INTERNAL_PEAK_MIN_HEIGHT,
            prominence=INTERNAL_PEAK_MIN_PROMINENCE,
            distance=min_peak_distance,
        )
        internal_peaks = internal_peaks + start

        # Per evitare che piccole aperture vengano promosse a REP, rendiamo la
        # soglia relativa ai picchi gia considerati validi nel video.
        reference_peaks = np.asarray([c["peak_value"] for c in cycles], dtype=float)
        reference_floor = (
            0.65 * float(np.median(reference_peaks))
            if len(reference_peaks)
            else INTERNAL_PEAK_MIN_HEIGHT
        )
        strong_peaks = [
            int(p) for p in internal_peaks
            if float(x[int(p)]) >= max(INTERNAL_PEAK_MIN_HEIGHT, reference_floor)
        ]

        if len(strong_peaks) < 2:
            # Nessuna prova sufficiente che il tratto contenga piu REP.
            result.append(cycle)
            continue

        # Confini locali nei minimi tra picchi forti consecutivi.
        valleys = []
        for left_peak, right_peak in zip(strong_peaks[:-1], strong_peaks[1:]):
            valley = left_peak + int(np.argmin(x[left_peak:right_peak + 1]))
            # Il ritorno non deve per forza raggiungere il riposo globale, ma
            # deve scendere di una frazione sostanziale rispetto ai due estremi.
            valley_value = float(x[valley])
            lower_peak = min(float(x[left_peak]), float(x[right_peak]))
            local_drop = lower_peak - valley_value
            required_drop = LOCAL_RETURN_FRACTION * max(lower_peak - FULL_CYCLE_REST_CEILING, 0.18)
            if local_drop >= required_drop:
                valleys.append(int(valley))
            else:
                valleys.append(None)

        split_cycles = []
        for i, peak in enumerate(strong_peaks):
            sub_start = start if i == 0 else valleys[i - 1]
            sub_end = end if i == len(strong_peaks) - 1 else valleys[i]
            if sub_start is None or sub_end is None:
                continue

            sub_start = int(sub_start)
            sub_end = int(sub_end)
            sub_duration = sub_end - sub_start
            if not (min_len <= sub_duration <= max_len):
                continue

            peak_value = float(x[peak])
            local_base = max(float(x[sub_start]), float(x[sub_end]))
            excursion = peak_value - local_base
            if excursion < 0.18:
                continue

            min_phase = max(2, int(round(MIN_PHASE_SECONDS * fps)))
            if (peak - sub_start) < min_phase or (sub_end - peak) < min_phase:
                continue

            split_cycles.append({
                "start_idx": sub_start,
                "peak_idx": int(peak),
                "end_idx": sub_end,
                "peak_value": peak_value,
                "duration_idx": int(sub_duration),
                "local_excursion": float(excursion),
                "recovered_from_oversized": True,
            })

        # Sostituiamo il tratto lungo solo se abbiamo recuperato almeno due REP
        # plausibili; altrimenti e piu sicuro lasciarlo segnalato come anomalo.
        if len(split_cycles) >= 2:
            result.extend(split_cycles)
        else:
            result.append(cycle)

    result.sort(key=lambda c: c["start_idx"])
    return result

def _candidate_quality(cycles, normalized, amplitude):
    if not cycles:
        return 0.0

    durations = np.asarray([c["duration_idx"] for c in cycles], dtype=float)
    peaks = np.asarray([c["peak_value"] for c in cycles], dtype=float)
    rests = np.asarray([
        0.5 * (normalized[c["start_idx"]] + normalized[c["end_idx"]])
        for c in cycles
    ], dtype=float)

    duration_cv = float(np.std(durations) / max(np.mean(durations), 1.0))
    duration_stability = 1.0 / (1.0 + 2.0 * duration_cv)
    peak_strength = float(np.clip((np.median(peaks) - PEAK_LEVEL) / 0.70, 0.0, 1.0))
    rest_return = float(np.clip(1.0 - np.median(rests) / max(REST_LEVEL + 0.12, 1e-6), 0.0, 1.0))
    count_support = min(len(cycles) / max(MIN_REPS_ACCEPTED + 3, 1), 1.0)
    amplitude_support = float(np.clip(amplitude / 30.0, 0.0, 1.0))

    return float(
        0.30 * count_support
        + 0.25 * duration_stability
        + 0.20 * peak_strength
        + 0.15 * rest_return
        + 0.10 * amplitude_support
    )


def _evaluate_angle(df, fps, angle, preferred_direction=None, adaptive_direction=True):
    if angle not in df.columns:
        return None

    smoothed = _smooth(df[angle].to_numpy(), fps)
    directions = []

    if preferred_direction in ("increase", "decrease"):
        directions.append(preferred_direction)
        if adaptive_direction:
            directions.append("decrease" if preferred_direction == "increase" else "increase")
    else:
        directions = ["increase", "decrease"]

    evaluated = []
    for direction in directions:
        normalized, amplitude = _directional_signal(smoothed, direction)
        if normalized is None or amplitude < 5.0:
            continue

        cycles = _extract_rest_to_rest_cycles(normalized, fps)
        cycles = _split_oversized_cycles(cycles, normalized, fps)
        score = _candidate_quality(cycles, normalized, amplitude)
        evaluated.append({
            "angle": angle,
            "direction": direction,
            "score": score,
            "peaks": np.asarray([c["peak_idx"] for c in cycles], dtype=int),
            "cycles": cycles,
            "normalized": normalized,
            "amplitude": float(amplitude),
            "period": float(np.median(np.diff([c["peak_idx"] for c in cycles])))
                if len(cycles) >= 2 else 0.0,
            "closure_score": None,
            "rep_count": len(cycles),
        })

    if not evaluated:
        return None

    # Se esiste una direzione salvata nel profilo, deve avere una preferenza reale.
    # Prima il codice provava entrambe le direzioni e sceglieva semplicemente lo
    # score massimo: piccole differenze potevano quindi invertire il gesto e
    # contare i ritorni al riposo al posto degli estremi del movimento.
    if preferred_direction in ("increase", "decrease"):
        preferred_item = next(
            (item for item in evaluated if item["direction"] == preferred_direction),
            None,
        )
        # Per uno stesso esercizio il verso biomeccanico dell'angolo non dovrebbe
        # cambiare da una REP all'altra. L'adattamento alla direzione opposta è
        # quindi un fallback, non una competizione 50/50.
        if (
            preferred_item is not None
            and preferred_item.get("rep_count", 0) >= MIN_REPS_ACCEPTED
            and preferred_item.get("score", 0.0) >= 0.45
        ):
            preferred_item["direction_selection_score"] = float(preferred_item["score"] + 0.05)
            return preferred_item

        for item in evaluated:
            item["direction_selection_score"] = float(
                item["score"] + (0.05 if item["direction"] == preferred_direction else 0.0)
            )
        return max(evaluated, key=lambda c: c["direction_selection_score"])

    return max(evaluated, key=lambda c: c["score"])


def rank_rest_signals(df, fps, signals=None):
    """Ritorna i candidati rest-to-rest ordinati per qualità."""
    candidates = []

    if signals is None:
        signals = [
            {
                "angle": angle,
                "preferred_direction": None,
                "adaptive_direction": True,
                "weight": 1.0,
            }
            for angle in ANGLE_COLUMNS
        ]

    for signal in signals:
        angle = signal.get("angle") or signal.get("guide_angle")
        if not angle:
            continue
        preferred = signal.get("preferred_direction", signal.get("direction"))
        adaptive = bool(signal.get("adaptive_direction", True))
        candidate = _evaluate_angle(
            df,
            fps,
            angle,
            preferred_direction=preferred,
            adaptive_direction=adaptive,
        )
        if candidate is None:
            continue
        candidate["profile_weight"] = float(signal.get("weight", 1.0))
        # Il peso del profilo conta, ma non deve sovrastare la qualità nel video corrente.
        candidate["selection_score"] = (
            0.80 * candidate["score"]
            + 0.20 * min(max(candidate["profile_weight"], 0.0), 1.0)
        )
        candidates.append(candidate)

    return sorted(candidates, key=lambda c: c["selection_score"], reverse=True)


def _support_for_cycle(cycle, secondary_candidates):
    """Conta quanti altri angoli mostrano un estremo dentro la stessa REP."""
    support = 0
    start = cycle["start_idx"]
    end = cycle["end_idx"]
    margin = max(2, int(round(0.15 * max(end - start, 1))))

    for candidate in secondary_candidates:
        peaks = candidate.get("peaks", [])
        if any((start - margin) <= int(p) <= (end + margin) for p in peaks):
            support += 1
    return support


def _valley_boundaries(normalized, peaks):
    """Confini di riposo locali tra estremi consecutivi."""
    peaks = np.asarray(peaks, dtype=int)
    if len(peaks) == 0:
        return []

    if len(peaks) >= 2:
        typical = float(np.median(np.diff(peaks)))
    else:
        typical = 90.0

    result = []
    for i, peak in enumerate(peaks):
        if i == 0:
            left = max(0, int(round(peak - 1.2 * typical)))
        else:
            left = int(peaks[i - 1])
        start = left + int(np.argmin(normalized[left:peak + 1]))

        if i == len(peaks) - 1:
            right = min(len(normalized) - 1, int(round(peak + 1.2 * typical)))
        else:
            right = int(peaks[i + 1])
        end = peak + int(np.argmin(normalized[peak:right + 1]))
        result.append((int(start), int(end)))

    return result


def _segments_from_candidate(candidate, secondary_candidates, frame_numbers):
    segments = []
    cycles = candidate["cycles"]
    normalized = candidate["normalized"]
    peaks = [cycle["peak_idx"] for cycle in cycles]
    valley_limits = _valley_boundaries(normalized, peaks)

    # I crossing rest-to-rest sono robusti per il conteggio; i minimi locali
    # sono migliori per i confini. Li combiniamo senza imporre un periodo fisso.
    boundary_blend = 0.70

    for cycle, valley in zip(cycles, valley_limits):
        raw_start = cycle["start_idx"]
        raw_end = cycle["end_idx"]
        valley_start, valley_end = valley

        start_idx = int(round((1.0 - boundary_blend) * raw_start + boundary_blend * valley_start))
        end_idx = int(round((1.0 - boundary_blend) * raw_end + boundary_blend * valley_end))
        peak_idx = cycle["peak_idx"]

        start_idx = max(0, min(start_idx, peak_idx))
        end_idx = min(len(frame_numbers) - 1, max(end_idx, peak_idx))
        if end_idx <= start_idx:
            continue

        support = _support_for_cycle(cycle, secondary_candidates)

        # Non eliminiamo una REP solo perché un secondo angolo non la conferma:
        # esecuzioni errate o ROM ridotto possono muovere meno alcune articolazioni.
        excursion = float(cycle.get("local_excursion", cycle["peak_value"]))
        multi_support = min(support / max(len(secondary_candidates), 1), 1.0)
        confidence = float(
            min(
                1.0,
                0.45 * min(max(excursion / 0.45, 0.0), 1.0)
                + 0.30 * min(cycle["peak_value"] / 1.0, 1.0)
                + 0.25 * multi_support
            )
        )

        segments.append({
            "rep": len(segments) + 1,
            "start_frame": int(frame_numbers[start_idx]),
            "peak_frame": int(frame_numbers[peak_idx]),
            "end_frame": int(frame_numbers[end_idx]),
            "duration_frames": int(frame_numbers[end_idx] - frame_numbers[start_idx] + 1),
            "supporting_angles": int(support),
            "confidence": confidence,
            # Usati SOLO per scegliere un insieme di REP vario per il training.
            # Non cambiano i confini della segmentazione.
            "motion_amplitude": float(excursion),
            "guide_peak_value": float(cycle["peak_value"]),
        })

    return segments



def _recover_oversized_output_segments(segments, candidate, frame_numbers, fps):
    """
    Secondo livello di recupero: se l'output contiene ancora un segmento molto
    piu lungo della durata tipica, cerchiamo picchi forti del segnale guida e
    ricostruiamo cicli completi usando minimi locali attorno a ciascun picco.
    Questo evita che pause + piu REP vengano mantenute come una singola clip.
    """
    if not segments or len(segments) < 3:
        return segments

    x = np.asarray(candidate.get("normalized", []), dtype=float)
    if len(x) == 0:
        return segments

    durations = np.asarray([s["duration_frames"] for s in segments], dtype=float)
    q75 = float(np.percentile(durations, 75))
    normal = durations[durations <= q75]
    typical = float(np.median(normal)) if len(normal) else float(np.median(durations))
    typical = max(typical, MIN_REP_SECONDS * fps)

    frame_numbers = np.asarray(frame_numbers, dtype=int)
    frame_to_idx = {int(f): i for i, f in enumerate(frame_numbers)}
    min_len = max(2, int(round(MIN_REP_SECONDS * fps)))
    max_len = max(min_len + 1, int(round(MAX_REP_SECONDS * fps)))

    recovered = []
    for seg in segments:
        if seg["duration_frames"] <= OVERSIZED_FACTOR * typical:
            recovered.append(seg)
            continue

        start_idx = frame_to_idx.get(int(seg["start_frame"]))
        end_idx = frame_to_idx.get(int(seg["end_frame"]))
        if start_idx is None or end_idx is None or end_idx <= start_idx:
            recovered.append(seg)
            continue

        piece = x[start_idx:end_idx + 1]
        peaks, props = find_peaks(
            piece,
            height=INTERNAL_PEAK_MIN_HEIGHT,
            prominence=INTERNAL_PEAK_MIN_PROMINENCE,
            distance=max(2, int(round(0.55 * MIN_REP_SECONDS * fps))),
        )
        peaks = [int(p + start_idx) for p in peaks]

        if len(peaks) < 2:
            recovered.append(seg)
            continue

        local_radius = max(min_len, int(round(1.15 * typical)))
        pieces = []
        for peak in peaks:
            left_lo = max(start_idx, peak - local_radius)
            right_hi = min(end_idx, peak + local_radius)
            sub_start = left_lo + int(np.argmin(x[left_lo:peak + 1]))
            sub_end = peak + int(np.argmin(x[peak:right_hi + 1]))
            duration = sub_end - sub_start
            if not (min_len <= duration <= max_len):
                continue
            if (peak - sub_start) < max(2, int(round(MIN_PHASE_SECONDS * fps))):
                continue
            if (sub_end - peak) < max(2, int(round(MIN_PHASE_SECONDS * fps))):
                continue
            left_rest = float(x[sub_start])
            right_rest = float(x[sub_end])
            peak_value = float(x[peak])
            if left_rest > FULL_CYCLE_REST_CEILING or right_rest > FULL_CYCLE_REST_CEILING:
                continue
            excursion = peak_value - max(left_rest, right_rest)
            if excursion < 0.18:
                continue

            pieces.append({
                "rep": 0,
                "start_frame": int(frame_numbers[sub_start]),
                "peak_frame": int(frame_numbers[peak]),
                "end_frame": int(frame_numbers[sub_end]),
                "duration_frames": int(frame_numbers[sub_end] - frame_numbers[sub_start] + 1),
                "supporting_angles": int(seg.get("supporting_angles", 0)),
                "confidence": max(float(seg.get("confidence", 0.5)), 0.80),
                "recovered_from_oversized": True,
            })

        # deduplica cicli quasi identici/fortemente sovrapposti
        pieces.sort(key=lambda z: z["start_frame"])
        deduped = []
        for piece_seg in pieces:
            if deduped and piece_seg["start_frame"] < deduped[-1]["end_frame"]:
                # conserva quello con picco piu separato temporalmente; in pratica
                # preferiamo il segmento piu corto e locale.
                if piece_seg["duration_frames"] < deduped[-1]["duration_frames"]:
                    deduped[-1] = piece_seg
                continue
            deduped.append(piece_seg)

        if len(deduped) >= 2:
            recovered.extend(deduped)
        else:
            recovered.append(seg)

    recovered.sort(key=lambda z: z["start_frame"])
    for i, seg in enumerate(recovered, start=1):
        seg["rep"] = i
    return recovered


def _align_first_boundary_to_canonical_rest(segments, df, candidate, fps):
    """
    Riallinea il confine iniziale della prima REP all'ULTIMO TRATTO STABILE
    di riposo canonico prima dell'inizio del movimento.

    Non sceglie piu' l'ultimo singolo frame simile al riposo (che puo' cadere
    quando la discesa/salita e' gia' iniziata). Cerca invece una finestra
    continua in cui:
      1) la postura multi-angolo assomiglia al riposo delle REP successive;
      2) il segnale guida e' ancora nella zona di riposo;
      3) il segnale e' stabile, cioe' con variazione locale piccola.

    La regola e' generale e non dipende dal nome dell'esercizio.
    """
    if len(segments) < 3 or "frame" not in df.columns:
        return segments

    frames = df["frame"].to_numpy(dtype=int)
    frame_to_idx = {int(f): i for i, f in enumerate(frames)}
    first = segments[0]
    first_start = frame_to_idx.get(int(first["start_frame"]))
    first_peak = frame_to_idx.get(int(first["peak_frame"]))
    if first_start is None or first_peak is None or first_peak <= first_start:
        return segments

    angle_cols = []
    for c in df.columns:
        if c == "frame":
            continue
        try:
            arr = np.asarray(df[c], dtype=float)
        except Exception:
            continue
        finite = arr[np.isfinite(arr)]
        if len(finite) >= max(10, int(0.5 * len(arr))) and float(np.nanstd(finite)) > 1e-3:
            angle_cols.append(c)
    if not angle_cols:
        return segments

    X = df[angle_cols].to_numpy(dtype=float)
    q25 = np.nanpercentile(X, 25, axis=0)
    q75 = np.nanpercentile(X, 75, axis=0)
    scale = q75 - q25
    std = np.nanstd(X, axis=0)
    scale = np.where(scale > 1e-3, scale, np.where(std > 1e-3, std, 1.0))

    ref_rows = []
    for seg in segments[1:]:
        for key in ("start_frame", "end_frame"):
            idx = frame_to_idx.get(int(seg[key]))
            if idx is not None:
                row = X[idx]
                if np.all(np.isfinite(row)):
                    ref_rows.append(row)
    if len(ref_rows) < 4:
        return segments

    refs = np.vstack(ref_rows)
    ref = np.nanmedian(refs, axis=0)
    ref_d = np.sqrt(np.nanmean(((refs - ref) / scale) ** 2, axis=1))
    typical_d = float(np.nanmedian(ref_d))
    accept_d = max(0.20, typical_d * 2.5 + 0.05)

    normalized = np.asarray(candidate.get("normalized", []), dtype=float)
    if len(normalized) != len(df):
        return segments

    min_phase = max(2, int(round(MIN_PHASE_SECONDS * fps)))
    hold = max(3, int(round(REST_HOLD_SECONDS * fps)))
    search_end = max(first_start, first_peak - min_phase)
    if search_end <= first_start:
        return segments

    # Derivata smussata del segnale guida: il riposo deve essere una postura
    # realmente stabile, non un frame attraversato mentre il gesto e' gia' iniziato.
    grad = np.abs(np.gradient(normalized))
    local_grad = pd.Series(grad).rolling(window=max(3, hold), center=True, min_periods=1).median().to_numpy()
    # soglia adattiva ma prudente; mai troppo permissiva
    grad_ref = float(np.nanpercentile(local_grad[first_start:search_end + 1], 40)) if search_end > first_start else 0.0
    stable_grad_limit = max(0.006, min(0.025, grad_ref * 2.0 + 0.003))

    valid = np.zeros(len(df), dtype=bool)
    distances = np.full(len(df), np.inf, dtype=float)
    for idx in range(first_start, search_end + 1):
        row = X[idx]
        if not np.all(np.isfinite(row)):
            continue
        if normalized[idx] > FULL_CYCLE_REST_CEILING:
            continue
        d = float(np.sqrt(np.nanmean(((row - ref) / scale) ** 2)))
        distances[idx] = d
        if d <= accept_d and local_grad[idx] <= stable_grad_limit:
            valid[idx] = True

    # Trova run contigui di riposo canonico stabile.
    runs = []
    i = first_start
    while i <= search_end:
        if not valid[i]:
            i += 1
            continue
        j = i
        while j + 1 <= search_end and valid[j + 1]:
            j += 1
        if (j - i + 1) >= hold:
            runs.append((i, j))
        i = j + 1

    if not runs:
        return segments

    # Usa l'ultimo plateau stabile prima del movimento, ma parte DALL'INIZIO
    # del plateau (non dal suo ultimo frame), cosi' la clip mostra chiaramente
    # la posizione iniziale completa prima della fase dinamica.
    run_start, run_end = runs[-1]
    new_start = int(run_start)

    if new_start <= first_start + 2 or (first_peak - new_start) < min_phase:
        return segments

    old_start_frame = int(first["start_frame"])
    first["start_frame"] = int(frames[new_start])
    first["duration_frames"] = int(first["end_frame"] - first["start_frame"] + 1)
    first["start_boundary_aligned"] = True
    first["original_start_frame"] = old_start_frame
    first["canonical_rest_distance"] = float(np.nanmedian(distances[run_start:run_end + 1]))
    first["canonical_rest_run_frames"] = int(run_end - run_start + 1)
    first["canonical_rest_stable"] = True
    return segments

def _select_best_segments(segments, max_segments):
    """
    Se ci sono piu REP del massimo ammesso, non prende soltanto quelle piu
    "medie". Mantiene prima la qualita minima e poi sceglie un insieme
    diversificato per durata (velocita di esecuzione) e ampiezza del movimento.

    La segmentazione NON viene modificata: questa funzione decide soltanto quali
    cicli gia validi proporre al medico per il dataset di training.
    """
    copied = [dict(s) for s in segments]
    if len(copied) <= max_segments:
        for s in copied:
            s["training_selection_score"] = float(s.get("confidence", 0.5))
            s["selection_reason"] = "all_valid_reps_kept"
        return copied

    durations = np.asarray([float(s.get("duration_frames", 0.0)) for s in copied], dtype=float)
    amplitudes = np.asarray([float(s.get("motion_amplitude", s.get("confidence", 0.5))) for s in copied], dtype=float)
    confidences = np.asarray([float(s.get("confidence", 0.5)) for s in copied], dtype=float)

    def robust01(values):
        values = np.asarray(values, dtype=float)
        lo, hi = np.percentile(values, [10, 90])
        if hi - lo < 1e-9:
            return np.full(len(values), 0.5, dtype=float)
        return np.clip((values - lo) / (hi - lo), 0.0, 1.0)

    d_norm = robust01(durations)
    a_norm = robust01(amplitudes)
    q_norm = np.clip(confidences, 0.0, 1.0)

    # Evita di usare REP chiaramente peggiori quando esistono abbastanza
    # alternative, ma non pretende che siano tutte quasi identiche/perfette.
    quality_floor = max(0.35, float(np.percentile(q_norm, 20)))
    eligible = [i for i, q in enumerate(q_norm) if q >= quality_floor]
    if len(eligible) < max_segments:
        eligible = list(range(len(copied)))

    # Prima REP: la piu affidabile. Poi scelta greedy che premia la distanza
    # dalle REP gia selezionate nello spazio durata/ampiezza, mantenendo un
    # contributo della confidence. Risultato: lente/veloci e ROM diverse.
    first = max(eligible, key=lambda i: q_norm[i])
    chosen = [first]
    remaining = set(eligible) - {first}

    while remaining and len(chosen) < max_segments:
        best_idx = None
        best_score = -1.0
        for i in remaining:
            min_dist = min(
                float(np.hypot(d_norm[i] - d_norm[j], a_norm[i] - a_norm[j]))
                for j in chosen
            )
            # Diversita conta leggermente piu della qualita, ma una REP molto
            # rumorosa non viene scelta solo perche e diversa.
            score = 0.60 * min_dist + 0.40 * q_norm[i]
            if score > best_score:
                best_score = score
                best_idx = i

        if best_idx is None:
            break
        chosen.append(best_idx)
        remaining.remove(best_idx)

    # Se il filtro di qualita ha lasciato meno di max_segments candidati,
    # completa con le migliori confidence rimaste.
    if len(chosen) < max_segments:
        leftovers = [i for i in range(len(copied)) if i not in chosen]
        leftovers.sort(key=lambda i: q_norm[i], reverse=True)
        chosen.extend(leftovers[: max_segments - len(chosen)])

    selected = []
    for i in chosen[:max_segments]:
        s = dict(copied[i])
        s["training_selection_score"] = float(q_norm[i])
        s["selection_reason"] = "quality_plus_duration_amplitude_diversity"
        selected.append(s)

    selected.sort(key=lambda s: s["start_frame"])
    for rep_id, s in enumerate(selected, start=1):
        s["rep"] = rep_id
    return selected


def choose_guide_signal(df, fps, guide_angle=None, direction=None):
    """Compatibilità con il codice precedente e con exercise_profile."""
    if guide_angle is not None:
        signals = [{
            "angle": guide_angle,
            "preferred_direction": direction,
            "adaptive_direction": True,
            "weight": 1.0,
        }]
    else:
        signals = None

    candidates = rank_rest_signals(df, fps, signals=signals)
    if not candidates:
        raise RuntimeError("Nessun segnale articolare utilizzabile trovato.")
    return candidates[0], candidates


def segment_repetitions(
    df,
    fps,
    guide_angle=None,
    direction=None,
    guide_signals=None,
    expected_reps=None,
):
    """
    Segmentazione finale rest-to-rest.

    - nessun periodo fisso imposto;
    - ogni REP può avere una durata diversa;
    - più angoli salvati possono competere/supportarsi;
    - il periodo riportato nei metadata è solo descrittivo.
    """
    if guide_signals:
        candidates = rank_rest_signals(df, fps, signals=guide_signals)
        selection_mode = "saved_multi_angle_profile"
    elif guide_angle is not None:
        candidates = rank_rest_signals(df, fps, signals=[{
            "angle": guide_angle,
            "preferred_direction": direction,
            "adaptive_direction": True,
            "weight": 1.0,
        }])
        selection_mode = "saved_configuration"
    else:
        candidates = rank_rest_signals(df, fps, signals=None)
        selection_mode = "automatic_proposal"

    if not candidates:
        raise RuntimeError("Nessun segnale articolare utilizzabile trovato.")

    # Se il protocollo clinico/UI conosce già il numero prescritto di REP,
    # lo usiamo solo come prior debole per scegliere tra segnali quasi equivalenti.
    # Non creiamo né cancelliamo segmenti per raggiungere artificialmente il numero.
    if expected_reps is not None:
        expected_reps = int(expected_reps)
        if expected_reps <= 0:
            raise ValueError("expected_reps deve essere > 0")
        for candidate in candidates:
            count_error = abs(int(candidate.get("rep_count", 0)) - expected_reps) / max(expected_reps, 1)
            candidate["expected_count_error"] = float(count_error)
            candidate["final_selection_score"] = float(
                candidate.get("selection_score", candidate.get("score", 0.0))
                - 0.12 * min(count_error, 1.5)
            )
        candidates = sorted(candidates, key=lambda c: c["final_selection_score"], reverse=True)

    best = candidates[0]
    secondary = candidates[1:]
    frames = df["frame"].to_numpy()
    all_segments = _segments_from_candidate(best, secondary, frames)
    all_segments = _recover_oversized_output_segments(all_segments, best, frames, fps)
    all_segments = _align_first_boundary_to_canonical_rest(all_segments, df, best, fps)
    detected_count = len(all_segments)
    used_segments = _select_best_segments(all_segments, MAX_REPS_FOR_TRAINING)

    if detected_count < MIN_REPS_ACCEPTED:
        status = "too_few_repetitions"
    elif detected_count > MAX_REPS_FOR_TRAINING:
        status = "capped_for_training"
    else:
        status = "ok"

    period_frames = float(best.get("period", 0.0))
    metadata = {
        "guide_angle": best["angle"],
        "direction": best["direction"],
        "selection_mode": selection_mode,
        "configuration_to_save": guide_signals is None and guide_angle is None,
        "score": float(best["score"]),
        "closure_score": None,
        "period_frames": period_frames,
        "period_seconds": period_frames / fps if fps else 0.0,
        "period_role": "diagnostic_only",
        "segmentation_mode": "strict_full_cycle_v5_stable_canonical_rest",
        "candidate_angles": [c["angle"] for c in candidates],
        "detected_reps": detected_count,
        "used_reps": len(used_segments),
        "training_rep_selection": "quality_plus_duration_amplitude_diversity_v1",
        "max_training_reps": int(MAX_REPS_FOR_TRAINING),
        "status": status,
        "expected_reps": expected_reps,
        "expected_reps_role": "soft_signal_selection_prior" if expected_reps is not None else None,
    }

    return all_segments, used_segments, metadata, candidates