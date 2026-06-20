import datetime
import json
import os
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from logic import util

# --- CONFIGURAZIONE PERCORSO FILE .TASK ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

TASK_FILE_PATH = os.path.join(CURRENT_DIR, "pose_landmarker_lite.task")
TASK_FILE_PATH = os.path.abspath(TASK_FILE_PATH)

# Normalizziamo il percorso per sicurezza
TASK_FILE_PATH = os.path. Carrollpath = os.path.abspath(TASK_FILE_PATH)

# --- INIZIALIZZAZIONE MEDIAPIPE ---
base_options = python.BaseOptions(model_asset_path=TASK_FILE_PATH)
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    output_segmentation_masks=True
)

# Questa è la variabile che mancava al server!
pose_landmarker = vision.PoseLandmarker.create_from_options(options)
mp_vision = vision

print(f"MediaPipe PoseLandmarker inizializzato con successo da: {TASK_FILE_PATH}")
class Frame:
    """
    Classe che rappresenta un frame di un video.
    """

    # Quantità di dati facenti parte del dataset per ogni feature
    num_keypoints_data = 36
    num_angles_data = 8
    num_mediapipe_keypoints = 33

    angles_dict = {  # angoli articolari
        'left_elbow': [5, 3, 1],
        'right_elbow': [2, 4, 6],
        'left_shoulder': [3, 1, 7],
        'right_shoulder': [8, 2, 4],
        'left_hip': [1, 7, 9],
        'right_hip': [2, 8, 10],
        'left_knee': [7, 9, 11],
        'right_knee': [8, 10, 12]
    }

    keypoints_list = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]  # keypoints utili alla predizione


    def __init__(self, frame):
        """
        Costruttore della classe che inizializza gli attributi

        Args:
        - frame (numpy.ndarray): il frame del video
        """
        self.keypoints = None  # keypoints estratti dal frame
        self.angles = None  # angoli estratti dal frame
        self.frame = frame  # frame
        self.mediapipe_landmarks = []  # landmarks estratti dal frame
        self.ball_coords = None # <-- NUOVO: Conterrà {'x': val, 'y': val, 'r': val} se trova la palla


        self.extract_keypoints()
        self.extract_ball() # <-- NUOVO: Estrae la palla ad ogni inizializzazione


    def extract_ball(self):
        """
        NUOVA FUNZIONE: Rileva una palla sferica nel frame usando la Trasformata di Hough
        """
        # 1. Prepara l'immagine (Grigio + Sfocatura)
        gray = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (9, 9), 2)

        # 2. Cerca i cerchi nell'immagine
        # Parametri da regolare in base ai video:
        # minDist: distanza minima tra due cerchi
        # param1: sensibilità del rilevatore di bordi (Canny)
        # param2: soglia di precisione (più è basso, più cerchi "falsi" trova; più è alto, più è severo)
        # minRadius/maxRadius: dimensioni in pixel della palla sullo schermo
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=50,
            param1=50,
            param2=35,
            minRadius=20,
            maxRadius=150
        )

        if circles is not None:
            circles = np.uint16(np.around(circles))
            # Prendiamo il primo cerchio trovato (il più evidente)
            scelta = circles[0, 0]

            # MediaPipe lavora con coordinate normalizzate (da 0.0 a 1.0).
            # Dobbiamo convertire i pixel del cerchio nello stesso formato di MediaPipe!
            h, w, _ = self.frame.shape
            self.ball_coords = {
                "x": float(scelta[0]) / w,
                "y": float(scelta[1]) / h,
                "r": float(scelta[2]) / max(w, h)
            }
        else:
            # Se in questo frame la palla è coperta o non si vede
            self.ball_coords = None


    def extract_keypoints(self):
        """
        Funzione che estrae i keypoints dal frame con Mediapipe e li salva tutti.
        """
        # Usiamo l'istanza globale di PoseLandmarker
        global pose_landmarker

        # Prepara l'immagine
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB))

        # Esegui il rilevamento
        detection_result = pose_landmarker.detect(image)

        # Salva TUTTI i 33 landmarks se rilevati
        if detection_result.pose_landmarks:
            # Prendiamo il primo (e probabilmente unico) set di pose landmarks
            self.mediapipe_landmarks = detection_result.pose_landmarks[0]

            # Crea una lista di dizionari con tutti i 33 punti
            points = []
            for landmark in self.mediapipe_landmarks:
                points.append({
                    "x": landmark.x,
                    "y": landmark.y,
                    "z": landmark.z,
                    "visibility": landmark.visibility # MediaPipe Tasks API returns visibility
                })

            # Salva l'array completo di 33 punti, senza filtrare nulla.
            self.keypoints = np.array(points)

        else:
            # Se non viene rilevata nessuna persona, crea un array vuoto
            self.keypoints = np.array([])


    def process_only_ball(self):
        """
        Ritorna SOLO le coordinate relative della palla (2 elementi)
        """
        if self.keypoints is not None and len(self.keypoints) > 0 and self.ball_coords is not None:
            ref_x = self.keypoints[0]["x"]
            ref_y = self.keypoints[0]["y"]
            ball_rel_x = self.ball_coords["x"] - ref_x
            ball_rel_y = self.ball_coords["y"] - ref_y
        else:
            # Fallback se la palla non c'è nel frame
            ball_rel_x = 0.0
            ball_rel_y = 0.0

        return np.array([ball_rel_x, ball_rel_y]) # Array piatto di 2 elementi


    def extract_angles(self):
        """
        Funzione che estrae gli angoli in base ai keypoints precedentemente estratti
        """
        if self.keypoints is None or len(self.keypoints) == 0:
            self.angles = []
            return

        angles = []
        for angle_name in Frame.angles_dict:
            angle_keypoint_indices = Frame.angles_dict[angle_name]

            # Ensure the indices are valid for the keypoints array
            try:
                p1 = self.keypoints[angle_keypoint_indices[0]]
                p2 = self.keypoints[angle_keypoint_indices[1]]
                p3 = self.keypoints[angle_keypoint_indices[2]]
                angle = util.calculate_angle(p1, p2, p3)
                angles.append(angle)
            except IndexError:
                print(f"Warning: Not enough keypoints to calculate angle for {angle_name}. Skipping.")
                angles.append(0.0) # Append a default value if keypoints are missing

        self.angles = angles


    def interpolate_keypoints(self, prev_frame, next_frame, treshold=0.3):
        """
        Funzione che interpola i keypoints con confidence bassa.

        Args:
        - prev_frame (numpy.ndarray): Il frame precedente
        - next_frame (numpy.ndarray): Il frame successivo
        - treshold (float): La soglia di confidence sotto la quale i keypoints vengono interpolati
        """
        if self.keypoints is None or len(self.keypoints) == 0:
            # If no keypoints are detected, interpolation is not possible or necessary
            return

        # Interpolo i keypoints con confidence al di sotto della soglia treshold
        for i in range(0, len(self.keypoints)):
            curr_kp = self.keypoints[i]
            if curr_kp["visibility"] < treshold:
                prev_kp = None
                if prev_frame is not None:
                    prev_kp = prev_frame.get_keypoint(i) # This can return None

                next_kp = None
                if next_frame is not None:
                    next_kp = next_frame.get_keypoint(i) # This can return None

                # Now evaluate the conditions safely
                prev_kp_valid = prev_kp is not None and prev_kp["visibility"] >= treshold
                next_kp_valid = next_kp is not None and next_kp["visibility"] >= treshold

                if prev_kp_valid and next_kp_valid:
                    # Both adjacent keypoints are valid, interpolate
                    self.keypoints[i]["x"] = (prev_kp["x"] + next_kp["x"]) / 2
                    self.keypoints[i]["y"] = (prev_kp["y"] + next_kp["y"]) / 2
                    self.keypoints[i]["z"] = (prev_kp["z"] + next_kp["z"]) / 2
                    self.keypoints[i]["visibility"] = (prev_kp["visibility"] + next_kp["visibility"]) / 2 # Average visibility
                elif prev_kp_valid:
                    # Only previous is valid, copy previous
                    self.keypoints[i]["x"] = prev_kp["x"]
                    self.keypoints[i]["y"] = prev_kp["y"]
                    self.keypoints[i]["z"] = prev_kp["z"]
                    self.keypoints[i]["visibility"] = prev_kp["visibility"]
                elif next_kp_valid:
                    # Only next is valid, copy next
                    self.keypoints[i]["x"] = next_kp["x"]
                    self.keypoints[i]["y"] = next_kp["y"]
                    self.keypoints[i]["z"] = next_kp["z"]
                    self.keypoints[i]["visibility"] = next_kp["visibility"]
                else:
                    # Neither adjacent keypoint is valid, set current to 0
                    self.keypoints[i]["x"] = 0.0
                    self.keypoints[i]["y"] = 0.0
                    self.keypoints[i]["z"] = 0.0
                    self.keypoints[i]["visibility"] = 0.0
            # For keypoints above threshold, set visibility to 1.0 (fully visible for processing)
            else:
                self.keypoints[i]["visibility"] = 1.0

    def process_keypoints(self):
        """
        Funzione che processa i keypoints in modo da utilizzarli per l'addestramento

        Returns:
        - processed_keypoints (numpy.ndarray): i keypoints processati
        """
        if self.keypoints is None or len(self.keypoints) == 0:
            # Return a zero-filled array of the expected size if no keypoints are detected
            return np.zeros(Frame.num_keypoints_data)

        # Filter self.keypoints to only include the desired keypoints from keypoints_list
        filtered_keypoints = []
        for idx in Frame.keypoints_list:
            if idx < len(self.keypoints):
                filtered_keypoints.append(self.keypoints[idx])
            else:
                # If a keypoint from the list is missing, append a zero-filled dictionary
                filtered_keypoints.append({'x': 0.0, 'y': 0.0, 'z': 0.0, 'visibility': 0.0})

        if not filtered_keypoints: # If, after filtering, list is empty (e.g., self.keypoints was too short)
            return np.zeros(Frame.num_keypoints_data)

        kp_copy = [None for _ in range(len(filtered_keypoints))]
        for i in range(len(filtered_keypoints)):
            kp_copy[i] = {
                "x": filtered_keypoints[i]["x"],
                "y": filtered_keypoints[i]["y"],
                "z": filtered_keypoints[i]["z"],
                "visibility": filtered_keypoints[i]["visibility"]
            }

        # Trasforma le coordinate x e y di ogni punto in coordinate rispetto al keypoint 0
        if len(kp_copy) > 0:
            ref_x = kp_copy[0]["x"]
            ref_y = kp_copy[0]["y"]
            ref_z = kp_copy[0]["z"]
            for i in range(1, len(kp_copy)):
                kp_copy[i]["x"] -= ref_x
                kp_copy[i]["y"] -= ref_y
                kp_copy[i]["z"] -= ref_z

            # --- NUOVO: Calcoliamo anche la posizione della palla RISPETTO al punto 0 umano! ---
            if self.ball_coords is not None:
                ball_rel_x = self.ball_coords["x"] - ref_x
                ball_rel_y = self.ball_coords["y"] - ref_y
            else:
                # Se non trova la palla in questo frame, mette delle coordinate di fallback (es. 0)
                ball_rel_x = 0.0
                ball_rel_y = 0.0

        # Trasformo ogni elemento da dizionario a array
        kp = []
        for item in kp_copy:
            kp.append([item["x"], item["y"], item["z"], item["visibility"]])
        kp = np.array(kp)

        # Elimino il punto 0 rendendo l'array di dimensione (12, 4) if it's there
        if len(kp) > 0:
            processed_keypoints = np.delete(kp, 0, axis=0)
        else:
            # If no keypoints or only one, result will be empty after deleting index 0.
            # Return a zero-filled array of the expected size.
            return np.zeros(Frame.num_keypoints_data)

        # Elimino da ogni punto la visibility rendendo l'array di dimensione (12, 3)
        processed_keypoints = np.delete(processed_keypoints, 3, axis=1)
        # Rendo l'array keypoints da dimensione (12, 3) a (36, 1)
        processed_keypoints = processed_keypoints.flatten()

        return processed_keypoints

    def process_angles(self):
        """
        Funzione che processa gli angoli in modo da utilizzarli per l'addestramento.

        Returns:
        - processed_angles (numpy.ndarray): gli angoli processati
        """
        if self.angles is None:
            self.extract_angles() # Ensure angles are extracted if not already
        if not self.angles: # If still empty after extraction
            return np.zeros(Frame.num_angles_data) # Ensure consistent shape, e.g., 8 zeros
        processed_angles = np.array(self.angles)
        return processed_angles


    # FUNZIONI GET E SET

    def get_keypoints(self):
        """
        Funzione che restituisce i keypoints.

        Returns:
        - array: keypoints del frame
        """

        return self.keypoints

    def get_keypoint(self, num):
        """
        Funzione che restituisce il keypoint in posizione num

        Returns:
        - keypoint (dict): keypoint in posizione num
        """
        if self.keypoints is not None and 0 <= num < len(self.keypoints):
            return self.keypoints[num]
        return None

    def get_angles(self):
        """
        Funzione che restituisce gli angoli.

        Returns:
        - array: angoli del frame
        """

        return self.angles

    def get_frame(self):
        """
        Funzione che restituisce il frame.

        Returns:
        - frame: il frame
        """

        return self.frame

    def get_landmarks(self):
        """
        Funzione che restituisce i landmarks.

        Returns:
        - landmarks: i landmarks
        """

        return self.mediapipe_landmarks