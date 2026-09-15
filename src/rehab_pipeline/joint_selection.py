"""Utility per la selezione anatomica dei segnali di segmentazione.

La GUI futura mostrera' articolazioni clinicamente leggibili. Questo modulo
traduce la selezione del medico nei nomi delle colonne angolari gia' usate dal
motore di segmentazione, mantenendo nascosti i dettagli MediaPipe.
"""

from config import ANGLE_COLUMNS


# Nella prima versione ogni articolazione cliccabile corrisponde direttamente
# a uno degli 8 angoli gia' estratti dalla pipeline.
JOINT_TO_ANGLE = {
    "left_elbow": "left_elbow",
    "right_elbow": "right_elbow",
    "left_shoulder": "left_shoulder",
    "right_shoulder": "right_shoulder",
    "left_hip": "left_hip",
    "right_hip": "right_hip",
    "left_knee": "left_knee",
    "right_knee": "right_knee",
}

AVAILABLE_JOINTS = tuple(JOINT_TO_ANGLE.keys())


def normalize_selected_joints(selected_joints):
    """Valida, normalizza e deduplica la selezione del medico."""
    if selected_joints is None:
        return []

    normalized = []
    for joint in selected_joints:
        joint = str(joint).strip().lower()
        if not joint:
            continue
        if joint not in JOINT_TO_ANGLE:
            allowed = ", ".join(AVAILABLE_JOINTS)
            raise ValueError(
                f"Articolazione non supportata: {joint!r}. Valori ammessi: {allowed}"
            )
        if joint not in normalized:
            normalized.append(joint)
    return normalized


def selected_joints_to_angles(selected_joints):
    """Converte le articolazioni selezionate nei segnali angolari ammessi."""
    joints = normalize_selected_joints(selected_joints)
    return [JOINT_TO_ANGLE[joint] for joint in joints]


def build_allowed_signals(selected_joints):
    """Crea guide_signals neutri per limitare il ranking ai soli angoli scelti."""
    angles = selected_joints_to_angles(selected_joints)
    return [
        {
            "angle": angle,
            "preferred_direction": None,
            "adaptive_direction": True,
            "weight": 1.0,
        }
        for angle in angles
        if angle in ANGLE_COLUMNS
    ]
