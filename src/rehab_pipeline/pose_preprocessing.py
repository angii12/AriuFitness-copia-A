import numpy as np
import pandas as pd

from config import (
    ANGLE_COLUMNS,
    KEYPOINT_INTERPOLATION_VISIBILITY,
    LSTM_WINDOW_SIZE,
    POSE_KEYPOINT_INDICES,
    TEMPORAL_SHIFT_FRAMES,
)


def interpolate_landmarks(landmarks, visibility_threshold=KEYPOINT_INTERPOLATION_VISIBILITY):
    """
    Interpola nel tempo x/y/z dei landmark poco affidabili o mancanti.

    L'array in ingresso ha forma (frames, 33, 4): x, y, z, visibility.
    Manteniamo la visibility originale solo come informazione diagnostica; il modello
    usera' esclusivamente le coordinate processate.
    """
    data = np.asarray(landmarks, dtype=np.float32).copy()
    if data.ndim != 3 or data.shape[1:] != (33, 4):
        raise ValueError(f"Landmark attesi con shape (N, 33, 4), ricevuto {data.shape}")

    n_frames = data.shape[0]
    frame_idx = np.arange(n_frames)

    for kp in POSE_KEYPOINT_INDICES:
        visibility = data[:, kp, 3]
        reliable = np.isfinite(visibility) & (visibility >= visibility_threshold)

        for coord in range(3):
            values = data[:, kp, coord]
            valid = reliable & np.isfinite(values)
            if not np.any(valid):
                data[:, kp, coord] = 0.0
                continue
            if np.sum(valid) == 1:
                data[:, kp, coord] = float(values[valid][0])
                continue
            data[:, kp, coord] = np.interp(frame_idx, frame_idx[valid], values[valid])

    return data


def process_keypoints(landmarks):
    """
    Preprocessing compatibile con l'approccio finale di Cirullo:
    - 13 landmark corporei utili;
    - coordinate relative al naso;
    - rimozione del naso e della visibility;
    - output 12 * 3 = 36 feature per frame.

    Non viene usata la normalizzazione per distanza tra i fianchi, scartata anche
    nel lavoro finale di Cirullo per la sensibilita' alla rotazione del soggetto.
    """
    data = interpolate_landmarks(landmarks)
    selected = data[:, POSE_KEYPOINT_INDICES, :3].copy()

    origin = selected[:, 0:1, :]
    selected = selected - origin
    selected = selected[:, 1:, :]  # elimina il naso, che e' sempre (0,0,0)
    return selected.reshape(selected.shape[0], -1).astype(np.float32)


def process_angles(angles_df):
    """Restituisce le 8 feature angolari senza NaN, mantenendo la timeline."""
    missing = [c for c in ANGLE_COLUMNS if c not in angles_df.columns]
    if missing:
        raise ValueError(f"Colonne angolari mancanti: {missing}")

    processed = (
        angles_df[ANGLE_COLUMNS]
        .apply(pd.to_numeric, errors="coerce")
        .interpolate(method="linear", limit_direction="both")
    )
    if processed.isna().any().any():
        processed = processed.fillna(processed.median()).fillna(0.0)
    return processed.to_numpy(dtype=np.float32)


def uniform_frame_indices(start_frame, end_frame, window_size=LSTM_WINDOW_SIZE):
    """Seleziona window_size frame uniformemente lungo l'intera REP."""
    start_frame = int(start_frame)
    end_frame = int(end_frame)
    if end_frame < start_frame:
        raise ValueError("end_frame deve essere >= start_frame")

    indices = np.rint(np.linspace(start_frame, end_frame, window_size)).astype(int)
    return np.clip(indices, start_frame, end_frame)


def shifted_rep_windows(segment, total_frames, max_shift=TEMPORAL_SHIFT_FRAMES):
    """
    Genera la finestra centrale e le versioni spostate fino a +/- max_shift frame.
    Lo shift muove entrambi i confini e conserva quindi la durata osservata della REP.
    Le finestre che uscirebbero dal video vengono escluse, non deformate.
    """
    start = int(segment["start_frame"])
    end = int(segment["end_frame"])
    windows = []

    for shift in range(-int(max_shift), int(max_shift) + 1):
        shifted_start = start + shift
        shifted_end = end + shift
        if shifted_start < 0 or shifted_end >= int(total_frames):
            continue
        indices = uniform_frame_indices(shifted_start, shifted_end)
        windows.append({
            "shift": shift,
            "start_frame": shifted_start,
            "end_frame": shifted_end,
            "frame_indices": indices,
        })

    return windows
