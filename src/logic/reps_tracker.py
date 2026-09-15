import time

class UniversalRepTracker:
    """
    Tracker generico di ripetizioni basato sulla macchina a stati 0 -> 1 -> 0
    e sulla probabilità/confidenza predetta dal modello TwoBranchLSTM.
    Indipendente dal nome o tipologia specifica dell'esercizio.
    """

    STATE_REST = "REST"       # 0: Posizione neutra / riposo
    STATE_ACTIVE = "ACTIVE"   # 1: Fase attiva / picco dell'esercizio

    def __init__(
        self,
        high_threshold: float = 65.0,
        low_threshold: float = 35.0,
        min_confirm_frames: int = 2,
        min_active_frames: int = 3,
        min_rep_duration_sec: float = 0.6
    ):
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.min_confirm_frames = min_confirm_frames
        self.min_active_frames = min_active_frames
        self.min_rep_duration_sec = min_rep_duration_sec

        self.reps = 0
        self.current_state = self.STATE_REST
        self.active_confirm_count = 0
        self.rest_confirm_count = 0
        self.active_frames_count = 0
        self.rep_start_time = 0.0

        self.last_confidence = 0.0
        self.phrase = "Inquadrati per iniziare l'esercizio."
        self.last_angle = None
        self.is_correcting = False
        self.last_correction_phrase = None

    def update(self, exercise_name: str, landmarks: list, confidence: float = 0.0):
        """
        Aggiorna lo stato del movimento in base alla confidenza (0.0 - 100.0)
        restituita dal modello PhysioVision.
        """
        self.last_confidence = confidence
        now = time.time()

        if not landmarks or len(landmarks) < 13:
            self.phrase = "Inquadrati completamente per iniziare."
            return

        if self.current_state == self.STATE_REST:
            if confidence >= self.high_threshold:
                self.active_confirm_count += 1
                if self.active_confirm_count >= self.min_confirm_frames:
                    self.current_state = self.STATE_ACTIVE
                    self.active_confirm_count = 0
                    self.rest_confirm_count = 0
                    self.active_frames_count = 1
                    self.rep_start_time = now
                    self.phrase = "Continua il movimento..."
            else:
                self.active_confirm_count = 0
                if self.reps == 0:
                    self.phrase = "Inizia il movimento."
                else:
                    self.phrase = f"Pronto per la prossima ripetizione ({self.reps} completate)."

        elif self.current_state == self.STATE_ACTIVE:
            self.active_frames_count += 1
            if confidence <= self.low_threshold:
                self.rest_confirm_count += 1
                if self.rest_confirm_count >= self.min_confirm_frames:
                    duration = now - self.rep_start_time if self.rep_start_time > 0 else 1.0
                    # Valida la ripetizione se ha durata temporale o numero di frame sufficiente
                    if duration >= self.min_rep_duration_sec or self.active_frames_count >= self.min_active_frames:
                        self.reps += 1
                        self.phrase = f"Ripetizione {self.reps} completata! Ottimo!"
                    self.current_state = self.STATE_REST
                    self.rest_confirm_count = 0
                    self.active_confirm_count = 0
                    self.active_frames_count = 0
            else:
                self.rest_confirm_count = 0
                self.phrase = "Torna alla posizione iniziale..."

    def get_reps(self) -> int:
        return self.reps

    def get_phrase(self) -> str:
        return self.phrase

    def get_last_angle(self):
        return self.last_angle

    def get_is_correcting(self) -> bool:
        return self.is_correcting

    def get_last_correction_phrase(self):
        return self.last_correction_phrase

    def reset(self):
        self.reps = 0
        self.current_state = self.STATE_REST
        self.active_confirm_count = 0
        self.rest_confirm_count = 0
        self.active_frames_count = 0
        self.rep_start_time = 0.0
        self.phrase = "Inquadrati per iniziare l'esercizio."


# Alias per compatibilità con il codice esistente
ExerciseTracker = UniversalRepTracker