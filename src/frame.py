import os
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# --- CONFIGURAZIONE PERCORSO FILE .TASK ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TASK_FILE_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "pose_landmarker_lite.task"))

# --- INIZIALIZZAZIONE MEDIAPIPE TASKS ---
base_options = python.BaseOptions(model_asset_path=TASK_FILE_PATH)
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.IMAGE,
    num_poses=1,
    min_pose_detection_confidence=0.5,
    min_pose_presence_confidence=0.5,
    min_tracking_confidence=0.5,
    output_segmentation_masks=False
)
pose_landmarker = vision.PoseLandmarker.create_from_options(options)
mp_vision = vision

# Indici MediaPipe Pose standard
LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12
LEFT_ELBOW, RIGHT_ELBOW = 13, 14
LEFT_WRIST, RIGHT_WRIST = 15, 16
LEFT_HIP, RIGHT_HIP = 23, 24
LEFT_KNEE, RIGHT_KNEE = 25, 26
LEFT_ANKLE, RIGHT_ANKLE = 27, 28

POSE_KEYPOINT_INDICES = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]

ANGLE_KEYS = [
    "left_elbow",
    "right_elbow",
    "left_shoulder",
    "right_shoulder",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
]

def calculate_angle_3d(a, b, c, min_visibility=0.30):
    """
    Calcola l'angolo ABC nello spazio 3D (in gradi). b è il vertice dell'articolazione.
    Supporta dizionari {'x':..., 'y':..., 'z':..., 'visibility':...} o array/liste [x, y, z, v].
    """
    if isinstance(a, dict):
        va, vb, vc = a.get('visibility', 1.0), b.get('visibility', 1.0), c.get('visibility', 1.0)
        p_a = np.array([a['x'], a['y'], a['z']], dtype=float)
        p_b = np.array([b['x'], b['y'], b['z']], dtype=float)
        p_c = np.array([c['x'], c['y'], c['z']], dtype=float)
    else:
        va, vb, vc = a[3], b[3], c[3]
        p_a = np.asarray(a[:3], dtype=float)
        p_b = np.asarray(b[:3], dtype=float)
        p_c = np.asarray(c[:3], dtype=float)

    if va < min_visibility or vb < min_visibility or vc < min_visibility:
        return 0.0

    ba = p_a - p_b
    bc = p_c - p_b
    denom = np.linalg.norm(ba) * np.linalg.norm(bc)
    if denom <= 1e-12:
        return 0.0

    cosine = np.clip(np.dot(ba, bc) / denom, -1.0, 1.0)
    return float(np.degrees(np.arccos(cosine)))


class Frame:
    """
    Rappresenta e processa un singolo frame video garantendo che
    l'estrazione dei keypoint e degli angoli 3D sia identica al training di PhysioVision.
    """
    num_keypoints_data = 36
    num_angles_data = 8
    num_mediapipe_keypoints = 33

    def __init__(self, frame):
        self.frame = frame
        self.keypoints = None
        self.angles = None
        self.mediapipe_landmarks = []
        self.extract_keypoints()

    def extract_keypoints(self):
        """Estrae tutti i 33 landmark con MediaPipe PoseLandmarker."""
        global pose_landmarker
        if self.frame is None:
            self.keypoints = np.array([])
            return

        rgb_frame = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        detection_result = pose_landmarker.detect(image)

        if detection_result.pose_landmarks and len(detection_result.pose_landmarks) > 0:
            self.mediapipe_landmarks = detection_result.pose_landmarks[0]
            points = []
            for lm in self.mediapipe_landmarks:
                points.append({
                    "x": float(lm.x),
                    "y": float(lm.y),
                    "z": float(lm.z),
                    "visibility": float(getattr(lm, "visibility", 1.0))
                })
            self.keypoints = np.array(points)
        else:
            self.keypoints = np.array([])
            self.mediapipe_landmarks = []

    def extract_angles(self):
        """Calcola gli 8 angoli anatomici 3D conformemente al training."""
        if self.keypoints is None or len(self.keypoints) < 29:
            self.angles = [0.0] * 8
            return self.angles

        kp = self.keypoints
        angles = [
            calculate_angle_3d(kp[LEFT_SHOULDER], kp[LEFT_ELBOW], kp[LEFT_WRIST]),
            calculate_angle_3d(kp[RIGHT_SHOULDER], kp[RIGHT_ELBOW], kp[RIGHT_WRIST]),
            calculate_angle_3d(kp[LEFT_ELBOW], kp[LEFT_SHOULDER], kp[LEFT_HIP]),
            calculate_angle_3d(kp[RIGHT_ELBOW], kp[RIGHT_SHOULDER], kp[RIGHT_HIP]),
            calculate_angle_3d(kp[LEFT_SHOULDER], kp[LEFT_HIP], kp[LEFT_KNEE]),
            calculate_angle_3d(kp[RIGHT_SHOULDER], kp[RIGHT_HIP], kp[RIGHT_KNEE]),
            calculate_angle_3d(kp[LEFT_HIP], kp[LEFT_KNEE], kp[LEFT_ANKLE]),
            calculate_angle_3d(kp[RIGHT_HIP], kp[RIGHT_KNEE], kp[RIGHT_ANKLE]),
        ]
        self.angles = angles
        return angles

    def interpolate_keypoints(self, prev_frame, next_frame, treshold=0.3):
        """Mantiene retrocompatibilità con l'interfaccia esistente."""
        pass

    def process_keypoints(self):
        """
        Estrae i 12 keypoint corporei centrati sul naso (36 feature/frame).
        """
        if self.keypoints is None or len(self.keypoints) < 29:
            return np.zeros(self.num_keypoints_data, dtype=np.float32)

        # Seleziona i 13 punti [0, 11..16, 23..28]
        selected = []
        for idx in POSE_KEYPOINT_INDICES:
            if idx < len(self.keypoints):
                p = self.keypoints[idx]
                selected.append([p["x"], p["y"], p["z"]])
            else:
                selected.append([0.0, 0.0, 0.0])

        selected = np.array(selected, dtype=np.float32) # (13, 3)
        origin = selected[0:1, :].copy() # Naso
        centered = selected - origin
        # Rimuove il naso che è sempre (0,0,0) -> restano 12 punti
        without_nose = centered[1:, :] # (12, 3)
        return without_nose.flatten().astype(np.float32) # (36,)

    def process_angles(self):
        """Restituisce il vettore degli 8 angoli 3D processati."""
        if self.angles is None:
            self.extract_angles()
        return np.array(self.angles, dtype=np.float32)

    def process_only_ball(self):
        """Mantiene retrocompatibilità restituisce [0.0, 0.0]."""
        return np.zeros(2, dtype=np.float32)

    def get_keypoints(self):
        return self.keypoints

    def get_keypoint(self, num):
        if self.keypoints is not None and 0 <= num < len(self.keypoints):
            return self.keypoints[num]
        return None

    def get_angles(self):
        return self.angles

    def get_frame(self):
        return self.frame

    def get_landmarks(self):
        return self.mediapipe_landmarks