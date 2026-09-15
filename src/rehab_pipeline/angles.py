import numpy as np

from config import MIN_VISIBILITY

LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12
LEFT_ELBOW, RIGHT_ELBOW = 13, 14
LEFT_WRIST, RIGHT_WRIST = 15, 16
LEFT_HIP, RIGHT_HIP = 23, 24
LEFT_KNEE, RIGHT_KNEE = 25, 26
LEFT_ANKLE, RIGHT_ANKLE = 27, 28


def calculate_angle(a, b, c, min_visibility=MIN_VISIBILITY):
    """Angolo ABC nello spazio 3D (x, y, z) in gradi. b è il vertice."""
    points = (a, b, c)
    if any(float(p[3]) < min_visibility for p in points):
        return np.nan

    a3 = np.asarray(a[:3], dtype=float)
    b3 = np.asarray(b[:3], dtype=float)
    c3 = np.asarray(c[:3], dtype=float)
    ba, bc = a3 - b3, c3 - b3
    denom = np.linalg.norm(ba) * np.linalg.norm(bc)
    if denom <= 1e-12:
        return np.nan

    cosine = np.clip(np.dot(ba, bc) / denom, -1.0, 1.0)
    return float(np.degrees(np.arccos(cosine)))


def extract_angles(landmarks):
    if landmarks is None:
        return None

    return {
        "left_elbow": calculate_angle(landmarks[LEFT_SHOULDER], landmarks[LEFT_ELBOW], landmarks[LEFT_WRIST]),
        "right_elbow": calculate_angle(landmarks[RIGHT_SHOULDER], landmarks[RIGHT_ELBOW], landmarks[RIGHT_WRIST]),
        "left_shoulder": calculate_angle(landmarks[LEFT_ELBOW], landmarks[LEFT_SHOULDER], landmarks[LEFT_HIP]),
        "right_shoulder": calculate_angle(landmarks[RIGHT_ELBOW], landmarks[RIGHT_SHOULDER], landmarks[RIGHT_HIP]),
        "left_hip": calculate_angle(landmarks[LEFT_SHOULDER], landmarks[LEFT_HIP], landmarks[LEFT_KNEE]),
        "right_hip": calculate_angle(landmarks[RIGHT_SHOULDER], landmarks[RIGHT_HIP], landmarks[RIGHT_KNEE]),
        "left_knee": calculate_angle(landmarks[LEFT_HIP], landmarks[LEFT_KNEE], landmarks[LEFT_ANKLE]),
        "right_knee": calculate_angle(landmarks[RIGHT_HIP], landmarks[RIGHT_KNEE], landmarks[RIGHT_ANKLE]),
    }
