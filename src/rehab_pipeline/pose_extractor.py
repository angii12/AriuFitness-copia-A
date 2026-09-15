from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np


class PoseExtractor:
    def __init__(self, model_path: str | Path):
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Modello MediaPipe non trovato: {self.model_path}")

        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(self.model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(options)

    def extract_from_frame(self, frame, timestamp_ms: int):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = self.landmarker.detect_for_video(mp_image, timestamp_ms)

        if not result.pose_landmarks:
            return None

        return np.asarray(
            [[p.x, p.y, p.z, p.visibility] for p in result.pose_landmarks[0]],
            dtype=np.float32,
        )

    def close(self):
        self.landmarker.close()
