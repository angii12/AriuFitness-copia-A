from pathlib import Path

MODEL_PATH = Path("models/pose_landmarker_lite.task")

# Regole del tool di creazione esercizio
MIN_REPS_ACCEPTED = 5
MAX_REPS_FOR_TRAINING = 20

# Range molto ampio per esercizi lenti/veloci.
# Serve solo a escludere oscillazioni palesemente non compatibili con una REP.
MIN_REP_SECONDS = 1.2
MAX_REP_SECONDS = 12.0

# Landmark considerato poco affidabile sotto questa soglia.
MIN_VISIBILITY = 0.50

ANGLE_COLUMNS = [
    "left_elbow",
    "right_elbow",
    "left_shoulder",
    "right_shoulder",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
]

# Preprocessing per il dataset LSTM (derivato/adattato da Cirullo)
POSE_KEYPOINT_INDICES = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
KEYPOINT_INTERPOLATION_VISIBILITY = 0.30
LSTM_WINDOW_SIZE = 8
TEMPORAL_SHIFT_FRAMES = 5
