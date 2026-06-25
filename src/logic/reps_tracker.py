import random
import numpy as np

# Mappatura indice dei landmark MediaPipe Pose
LANDMARK_DICT = {
    "LEFT_SHOULDER": 11, "RIGHT_SHOULDER": 12, "LEFT_ELBOW": 13, "RIGHT_ELBOW": 14,
    "LEFT_WRIST": 15, "RIGHT_WRIST": 16, "LEFT_HIP": 23, "RIGHT_HIP": 24,
    "LEFT_KNEE": 25, "RIGHT_KNEE": 26, "LEFT_ANKLE": 27, "RIGHT_ANKLE": 28
}

FEEDBACK_MESSAGES = {
    'sollevamento_gambe_stringendo_la_fitball': {
        'start': 'Sdraiati e posiziona i piedi sulla Fitball.',
        'motivational': ['Ottima spinta!', 'Contrai i glutei!', 'Bellissima esecuzione!'],
        'correction_low': 'Sali di più con il bacino!',
        'good_rep': 'Ponte perfetto!'
    },
    'braccia_con_miniball': {
        'start': 'Mettiti a pancia in giù stringendo la Miniball.',
        'motivational': ['Spingi forte!', 'Ottima estensione!', 'Guarda il tappetino!'],
        'correction_low': 'Prova a sollevare di più il torace!',
        'good_rep': 'Ottimo sollevamento!'
    },
    'medicine_ball_squat': {
        'start': 'In piedi, stringi la palla al petto ed esegui uno squat.',
        'motivational': ['Mantieni il busto dritto!', 'Spingi sui talloni!'],
        'correction_depth': 'Scendi di più con il bacino!',
        'good_rep': 'Squat perfetto!'
    },
    'roll_out_sulla_fitball': {
        'start': 'In ginocchio, appoggia gli avambracci sulla Fitball.',
        'motivational': ['Mantieni l\'addome attivo!', 'Ottimo controllo!'],
        'correction_back': 'Attenzione, non inarcare la schiena!',
        'good_rep': 'Ritorno controllato, ottimo!'
    },
    'fitball_back_extensions': {
        'start': 'Pancia sulla Fitball, mani dietro la testa.',
        'motivational': ['Estendi bene i lombari!', 'Sali in modo controllato!'],
        'correction_flex': 'Fletti di più il busto verso il basso prima di salire!',
        'good_rep': 'Estensione completata!'
    },
    'overhead_ball_side_bends': {
        'start': 'Porta la Fitball sopra la testa a braccia tese.',
        'motivational': ['Resta sul piano frontale!', 'Ottimo allungamento!'],
        'correction_short': 'Inclinati un po\' di più lateralmente!',
        'good_rep': 'Flessione perfetta!'
    }
}

class ExerciseTracker:
    def __init__(self):
        self.exercise_states = {
            'sollevamento_gambe_stringendo_la_fitball': {'reps': 0, 'stage': 'down', 'phrase': FEEDBACK_MESSAGES['sollevamento_gambe_stringendo_la_fitball']['start']},
            'braccia_con_miniball': {'reps': 0, 'stage': 'down', 'phrase': FEEDBACK_MESSAGES['braccia_con_miniball']['start']},
            'medicine_ball_squat': {'reps': 0, 'stage': 'up', 'phrase': FEEDBACK_MESSAGES['medicine_ball_squat']['start']},
            'roll_out_sulla_fitball': {'reps': 0, 'stage': 'start', 'phrase': FEEDBACK_MESSAGES['roll_out_sulla_fitball']['start']},
            'fitball_back_extensions': {'reps': 0, 'stage': 'down', 'phrase': FEEDBACK_MESSAGES['fitball_back_extensions']['start']},
            'overhead_ball_side_bends': {'reps': 0, 'stage': 'center', 'phrase': FEEDBACK_MESSAGES['overhead_ball_side_bends']['start']}
        }
        self.feedback_timer = 0
        self.last_predicted = None

    def _calculate_angle(self, a, b, c):
        """Calcola l'angolo tra tre punti in 2D"""
        a = np.array(a)
        b = np.array(b)
        c = np.array(c)
        radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
        angle = np.abs(radians*180.0/np.pi)
        if angle > 180.0:
            angle = 360-angle
        return angle

    def update(self, exercise_name, landmarks):
        if exercise_name not in self.exercise_states or not landmarks:
            return

        state = self.exercise_states[exercise_name]
        self.feedback_timer += 1
        self.last_predicted = exercise_name

        try:
            # --- 1. MEDICINE BALL SQUAT ---
            if exercise_name == 'medicine_ball_squat':
            # Punti lato SINISTRO (Bacino, Ginocchio, Caviglia)
                p_bacino_sx = [landmarks[LANDMARK_DICT["LEFT_HIP"]].x, landmarks[LANDMARK_DICT["LEFT_HIP"]].y]
                p_ginocchio_sx = [landmarks[LANDMARK_DICT["LEFT_KNEE"]].x, landmarks[LANDMARK_DICT["LEFT_KNEE"]].y]
                p_caviglia_sx = [landmarks[LANDMARK_DICT["LEFT_ANKLE"]].x, landmarks[LANDMARK_DICT["LEFT_ANKLE"]].y]
                
                # Punti lato DESTRO (Bacino, Ginocchio, Caviglia)
                p_bacino_dx = [landmarks[LANDMARK_DICT["RIGHT_HIP"]].x, landmarks[LANDMARK_DICT["RIGHT_HIP"]].y]
                p_ginocchio_dx = [landmarks[LANDMARK_DICT["RIGHT_KNEE"]].x, landmarks[LANDMARK_DICT["RIGHT_KNEE"]].y]
                p_caviglia_dx = [landmarks[LANDMARK_DICT["RIGHT_ANKLE"]].x, landmarks[LANDMARK_DICT["RIGHT_ANKLE"]].y]
                
                # Calcolo dell'angolo del ginocchio per entrambi i lati
                angle_sx = self._calculate_angle(p_bacino_sx, p_ginocchio_sx, p_caviglia_sx)
                angle_dx = self._calculate_angle(p_bacino_dx, p_ginocchio_dx, p_caviglia_dx)
                
                # Selezioniamo l'angolo minore per gestire le occlusioni di profilo o le asimmetrie frontali
                angle = min(angle_sx, angle_dx)

                # --- Logica di soglia per l'angolo del ginocchio ---
                # Nota: In posizione eretta il ginocchio è a ~180°. In uno squat profondo scende sotto i 90-100°.
                if state['stage'] == 'up':
                    if angle < 100:  # Soglia di discesa (puoi regolarla tra 90 e 110 in base alla profondità voluta)
                        state['stage'] = 'down'
                    elif angle < 140 and self.feedback_timer % 15 == 0:
                        state['phrase'] = FEEDBACK_MESSAGES[exercise_name]['correction_depth']
                        
                elif state['stage'] == 'down':
                    if angle > 160:  # Soglia di risalita (quasi gambe tese)
                        state['stage'] = 'up'
                        state['reps'] += 1
                        state['phrase'] = f"{FEEDBACK_MESSAGES[exercise_name]['good_rep']} ({state['reps']})"

            # --- 2. SOLLEVAMENTO GAMBE STRINGENDO LA FITBALL ---
            elif exercise_name == 'sollevamento_gambe_stringendo_la_fitball':
                p_spalla = [landmarks[LANDMARK_DICT["LEFT_SHOULDER"]].x, landmarks[LANDMARK_DICT["LEFT_SHOULDER"]].y]
                p_bacino = [landmarks[LANDMARK_DICT["LEFT_HIP"]].x, landmarks[LANDMARK_DICT["LEFT_HIP"]].y]
                p_ginocchio = [landmarks[LANDMARK_DICT["LEFT_KNEE"]].x, landmarks[LANDMARK_DICT["LEFT_KNEE"]].y]
                angle = self._calculate_angle(p_spalla, p_bacino, p_ginocchio)

                if state['stage'] == 'down':
                    if angle > 160:
                        state['stage'] = 'up'
                    elif angle > 130 and angle <= 155 and self.feedback_timer % 15 == 0:
                        state['phrase'] = FEEDBACK_MESSAGES[exercise_name]['correction_low']
                elif state['stage'] == 'up':
                    if angle < 130:
                        state['stage'] = 'down'
                        state['reps'] += 1
                        state['phrase'] = f"{FEEDBACK_MESSAGES[exercise_name]['good_rep']} ({state['reps']})"

            # --- 3. BRACCIA CON MINIBALL ---
            elif exercise_name == 'braccia_con_miniball':
                # Punti lato SINISTRO (Spalla, Bacino, Ginocchio)
                p_spalla_sx = [landmarks[LANDMARK_DICT["LEFT_SHOULDER"]].x, landmarks[LANDMARK_DICT["LEFT_SHOULDER"]].y]
                p_bacino_sx = [landmarks[LANDMARK_DICT["LEFT_HIP"]].x, landmarks[LANDMARK_DICT["LEFT_HIP"]].y]
                p_ginocchio_sx = [landmarks[LANDMARK_DICT["LEFT_KNEE"]].x, landmarks[LANDMARK_DICT["LEFT_KNEE"]].y]
                                
                angle = self._calculate_angle(p_spalla_sx, p_bacino_sx, p_ginocchio_sx)
                
                # --- Logica di conteggio per estensione busto prono ---                
                if state['stage'] == 'down':
                    if angle < 158:  # Ti sei sollevato abbastanza (fase UP)
                        state['stage'] = 'up'
                        
                elif state['stage'] == 'up':
                    if angle > 168:  # Sei tornato completamente a terra (fase DOWN)
                        state['stage'] = 'down'
                        state['reps'] += 1
                        state['phrase'] = f"{random.choice(FEEDBACK_MESSAGES[exercise_name]['motivational'])} R: {state['reps']}"
            # --- 4. FITBALL BACK EXTENSIONS ---
            elif exercise_name == 'fitball_back_extensions':
                p_caviglia = [landmarks[LANDMARK_DICT["LEFT_ANKLE"]].x, landmarks[LANDMARK_DICT["LEFT_ANKLE"]].y]
                p_bacino = [landmarks[LANDMARK_DICT["LEFT_HIP"]].x, landmarks[LANDMARK_DICT["LEFT_HIP"]].y]
                p_spalla = [landmarks[LANDMARK_DICT["LEFT_SHOULDER"]].x, landmarks[LANDMARK_DICT["LEFT_SHOULDER"]].y]
                angle = self._calculate_angle(p_caviglia, p_bacino, p_spalla)

                if state['stage'] == 'down':
                    if angle > 165:
                        state['stage'] = 'up'
                    elif angle > 145 and angle <= 165 and self.feedback_timer % 15 == 0:
                        state['phrase'] = "Ottimo, ma sali ancora un po'!"
                elif state['stage'] == 'up':
                    if angle < 140:
                        state['stage'] = 'down'
                        state['reps'] += 1
                        state['phrase'] = f"{FEEDBACK_MESSAGES[exercise_name]['good_rep']} ({state['reps']})"

            # --- 5. OVERHEAD BALL SIDE BENDS ---
            elif exercise_name == 'overhead_ball_side_bends':
                # Calcolo angolo sinistro
                p_caviglia_l = [landmarks[LANDMARK_DICT["LEFT_ANKLE"]].x, landmarks[LANDMARK_DICT["LEFT_ANKLE"]].y]
                p_bacino_l = [landmarks[LANDMARK_DICT["LEFT_HIP"]].x, landmarks[LANDMARK_DICT["LEFT_HIP"]].y]
                p_spalla_l = [landmarks[LANDMARK_DICT["LEFT_SHOULDER"]].x, landmarks[LANDMARK_DICT["LEFT_SHOULDER"]].y]
                angle_left = self._calculate_angle(p_caviglia_l, p_bacino_l, p_spalla_l)

                # Calcolo angolo destro
                p_caviglia_r = [landmarks[LANDMARK_DICT["RIGHT_ANKLE"]].x, landmarks[LANDMARK_DICT["RIGHT_ANKLE"]].y]
                p_bacino_r = [landmarks[LANDMARK_DICT["RIGHT_HIP"]].x, landmarks[LANDMARK_DICT["RIGHT_HIP"]].y]
                p_spalla_r = [landmarks[LANDMARK_DICT["RIGHT_SHOULDER"]].x, landmarks[LANDMARK_DICT["RIGHT_SHOULDER"]].y]
                angle_right = self._calculate_angle(p_caviglia_r, p_bacino_r, p_spalla_r)

                # Scegliamo l'angolo del lato che si sta flettendo di più
                angle = min(angle_left, angle_right)

                if state['stage'] == 'center':
                    if angle < 155:
                        state['stage'] = 'bend'
                    elif angle >= 155 and angle < 168 and self.feedback_timer % 15 == 0:
                        state['phrase'] = FEEDBACK_MESSAGES[exercise_name]['correction_short']
                elif state['stage'] == 'bend':
                    if angle > 173:
                        state['stage'] = 'center'
                        state['reps'] += 1
                        state['phrase'] = f"{FEEDBACK_MESSAGES[exercise_name]['good_rep']} ({state['reps']})"

            # --- 6. SWISS BALL ROLL OUT ---
            elif exercise_name == 'roll_out_sulla_fitball':
                p_spalla = [landmarks[LANDMARK_DICT["LEFT_SHOULDER"]].x, landmarks[LANDMARK_DICT["LEFT_SHOULDER"]].y]
                p_bacino = [landmarks[LANDMARK_DICT["LEFT_HIP"]].x, landmarks[LANDMARK_DICT["LEFT_HIP"]].y]
                p_ginocchio = [landmarks[LANDMARK_DICT["LEFT_KNEE"]].x, landmarks[LANDMARK_DICT["LEFT_KNEE"]].y]
                angle = self._calculate_angle(p_spalla, p_bacino, p_ginocchio)

                if state['stage'] == 'start':
                    if angle < 155:
                        state['stage'] = 'extension'
                elif state['stage'] == 'extension':
                    if angle > 165 and angle <= 172 and self.feedback_timer % 15 == 0:
                        state['phrase'] = FEEDBACK_MESSAGES[exercise_name]['correction_back']
                    elif angle > 172:
                        state['stage'] = 'start'
                        state['reps'] += 1
                        state['phrase'] = f"{FEEDBACK_MESSAGES[exercise_name]['good_rep']} ({state['reps']})"
        except Exception:
            pass

    def get_reps(self):
        if not self.last_predicted or self.last_predicted not in self.exercise_states:
            return 0
        return self.exercise_states[self.last_predicted]['reps']

    def get_phrase(self):
        if not self.last_predicted or self.last_predicted not in self.exercise_states:
            return "In attesa dell'esercizio..."
        return self.exercise_states[self.last_predicted]['phrase']