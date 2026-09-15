from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from angles import extract_angles
from config import ANGLE_COLUMNS
from pose_extractor import PoseExtractor


def extract_pose_data_from_video(video_path, model_path):
    """
    Estrae una riga per ogni frame senza comprimere la timeline.

    Restituisce anche tutti i 33 landmark MediaPipe, necessari in seguito per
    costruire il ramo keypoint dell'LSTM senza dover analizzare di nuovo il video.
    Shape pose_landmarks: (N_frames, 33, 4) = x,y,z,visibility.
    """
    video_path = Path(video_path)
    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        raise RuntimeError(f"Impossibile aprire il video: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0:
        cap.release()
        raise RuntimeError(f"FPS non validi per il video: {video_path}")

    extractor = PoseExtractor(model_path)
    rows = []
    pose_rows = []
    frame_number = 0
    detected_frames = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            timestamp_ms = int(frame_number / fps * 1000)
            landmarks = extractor.extract_from_frame(frame, timestamp_ms)

            row = {"frame": frame_number, "time_seconds": frame_number / fps}
            if landmarks is not None:
                detected_frames += 1
                row.update(extract_angles(landmarks))
                pose_rows.append(landmarks.astype(np.float32, copy=False))
            else:
                for angle_name in ANGLE_COLUMNS:
                    row[angle_name] = np.nan
                pose_rows.append(np.full((33, 4), np.nan, dtype=np.float32))

            rows.append(row)
            frame_number += 1
    finally:
        cap.release()
        extractor.close()

    df = pd.DataFrame(rows)
    landmarks_array = (
        np.stack(pose_rows).astype(np.float32)
        if pose_rows
        else np.empty((0, 33, 4), dtype=np.float32)
    )

    real_total = frame_number if frame_number > 0 else total_frames
    detection_rate = 100.0 * detected_frames / real_total if real_total else 0.0
    return df, landmarks_array, fps, real_total, detection_rate


def extract_angles_from_video(video_path, model_path):
    """Wrapper retrocompatibile: la validazione esistente continua a funzionare."""
    df, _, fps, total_frames, detection_rate = extract_pose_data_from_video(
        video_path, model_path
    )
    return df, fps, total_frames, detection_rate
