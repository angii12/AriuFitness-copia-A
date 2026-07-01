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
        'correction_ball': 'Tieni i piedi ben appoggiati sulla palla!',
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
        'correction_trunk': 'Tieni il busto più eretto!',
        'correction_sym': 'Distribuisci il peso su entrambe le gambe!',
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
        'correction_knees': 'Tieni le gambe più tese!',
        'good_rep': 'Estensione completata!'
    },
    'overhead_ball_side_bends': {
        'start': 'Porta la Fitball sopra la testa a braccia tese.',
        'motivational': ['Resta sul piano frontale!', 'Ottimo allungamento!'],
        'correction_short': 'Inclinati un po\' di più lateralmente!',
        'correction_knees': 'Tieni le gambe dritte!',
        'good_rep': 'Flessione perfetta!'
    }
}


class ExerciseTracker:
    def __init__(self):
        self.exercise_states = {
            'sollevamento_gambe_stringendo_la_fitball': {
                'reps': 0, 'stage': 'down',
                'phrase': FEEDBACK_MESSAGES['sollevamento_gambe_stringendo_la_fitball']['start']
            },
            'braccia_con_miniball': {
                'reps': 0, 'stage': 'down',
                'phrase': FEEDBACK_MESSAGES['braccia_con_miniball']['start'],
                'min_up_angle': 180.0   # traccia il picco di sollevamento durante la fase UP
            },
            'medicine_ball_squat': {
                'reps': 0, 'stage': 'up',
                'phrase': FEEDBACK_MESSAGES['medicine_ball_squat']['start']
            },
            'roll_out_sulla_fitball': {
                'reps': 0, 'stage': 'start',
                'phrase': FEEDBACK_MESSAGES['roll_out_sulla_fitball']['start'],
                'arch_detected': False  # True se viene rilevato inarco durante l'estensione
            },
            'fitball_back_extensions': {
                'reps': 0, 'stage': 'down',
                'phrase': FEEDBACK_MESSAGES['fitball_back_extensions']['start']
            },
            'overhead_ball_side_bends': {
                'reps': 0, 'stage': 'center',
                'phrase': FEEDBACK_MESSAGES['overhead_ball_side_bends']['start']
            }
        }
        self.feedback_timer = 0
        self.last_predicted = None
        self.last_angle = None
        self.is_correcting = False
        self.last_correction_phrase = None

    def _pt(self, lm, key):
        """Restituisce [x, y] del landmark specificato."""
        idx = LANDMARK_DICT[key]
        return [lm[idx].x, lm[idx].y]

    def _vis(self, lm, *keys, threshold=0.45):
        """True se tutti i landmark indicati hanno visibility >= threshold."""
        return all(lm[LANDMARK_DICT[k]].visibility >= threshold for k in keys)

    def _calculate_angle(self, a, b, c):
        """Calcola l'angolo in gradi nel punto b tra i vettori b→a e b→c."""
        a = np.array(a)
        b = np.array(b)
        c = np.array(c)
        radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
        angle = np.abs(radians*180.0/np.pi)
        if angle > 180.0:
            angle = 360-angle
        return angle

    def _set_correction(self, state, phrase):
        """Imposta una correzione senza incrementare le reps."""
        state['phrase'] = phrase
        self.is_correcting = True
        self.last_correction_phrase = phrase

    def update(self, exercise_name, landmarks):
        if exercise_name not in self.exercise_states or not landmarks:
            return

        state = self.exercise_states[exercise_name]
        self.feedback_timer += 1
        self.last_predicted = exercise_name
        self.is_correcting = False
        self.last_correction_phrase = None

        try:
            # --- 1. MEDICINE BALL SQUAT ---
            if exercise_name == 'medicine_ball_squat':
                p_bacino_sx   = self._pt(landmarks, "LEFT_HIP")
                p_ginocchio_sx = self._pt(landmarks, "LEFT_KNEE")
                p_caviglia_sx = self._pt(landmarks, "LEFT_ANKLE")

                p_bacino_dx   = self._pt(landmarks, "RIGHT_HIP")
                p_ginocchio_dx = self._pt(landmarks, "RIGHT_KNEE")
                p_caviglia_dx = self._pt(landmarks, "RIGHT_ANKLE")

                angle_sx = self._calculate_angle(p_bacino_sx, p_ginocchio_sx, p_caviglia_sx)
                angle_dx = self._calculate_angle(p_bacino_dx, p_ginocchio_dx, p_caviglia_dx)
                angle = min(angle_sx, angle_dx)
                self.last_angle = angle

                if state['stage'] == 'up':
                    if angle < 100:
                        state['stage'] = 'down'
                    elif angle < 140 and self.feedback_timer % 15 == 0:
                        self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_depth'])

                elif state['stage'] == 'down':
                    if angle > 160:
                        state['stage'] = 'up'  # avanza sempre per non bloccare la macchina a stati

                        # Check secondario 1: tronco non troppo inclinato in avanti
                        trunk_ok = True
                        if self._vis(landmarks, "LEFT_SHOULDER", "LEFT_HIP", "LEFT_KNEE",
                                               "RIGHT_SHOULDER", "RIGHT_HIP", "RIGHT_KNEE"):
                            trunk_l = self._calculate_angle(
                                self._pt(landmarks, "LEFT_SHOULDER"),
                                self._pt(landmarks, "LEFT_HIP"),
                                self._pt(landmarks, "LEFT_KNEE")
                            )
                            trunk_r = self._calculate_angle(
                                self._pt(landmarks, "RIGHT_SHOULDER"),
                                self._pt(landmarks, "RIGHT_HIP"),
                                self._pt(landmarks, "RIGHT_KNEE")
                            )
                            trunk_ok = min(trunk_l, trunk_r) > 60

                        # Check secondario 2: simmetria tra i due lati
                        sym_ok = abs(angle_sx - angle_dx) < 20

                        if trunk_ok and sym_ok:
                            state['reps'] += 1
                            state['phrase'] = f"{FEEDBACK_MESSAGES[exercise_name]['good_rep']} ({state['reps']})"
                        elif not trunk_ok:
                            self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_trunk'])
                        else:
                            self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_sym'])

            # --- 2. SOLLEVAMENTO GAMBE STRINGENDO LA FITBALL ---
            elif exercise_name == 'sollevamento_gambe_stringendo_la_fitball':
                p_spalla   = self._pt(landmarks, "LEFT_SHOULDER")
                p_bacino   = self._pt(landmarks, "LEFT_HIP")
                p_ginocchio = self._pt(landmarks, "LEFT_KNEE")
                angle = self._calculate_angle(p_spalla, p_bacino, p_ginocchio)
                self.last_angle = angle

                if state['stage'] == 'down':
                    if angle > 160:
                        state['stage'] = 'up'
                    elif angle > 130 and angle <= 155 and self.feedback_timer % 15 == 0:
                        self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_low'])

                elif state['stage'] == 'up':
                    if angle < 130:
                        state['stage'] = 'down'

                        # Check secondario: angolo al ginocchio < 120° → piedi correttamente sulla palla
                        ball_ok = True
                        if self._vis(landmarks, "LEFT_HIP", "LEFT_KNEE", "LEFT_ANKLE"):
                            knee_angle = self._calculate_angle(
                                self._pt(landmarks, "LEFT_HIP"),
                                self._pt(landmarks, "LEFT_KNEE"),
                                self._pt(landmarks, "LEFT_ANKLE")
                            )
                            ball_ok = knee_angle < 120

                        if ball_ok:
                            state['reps'] += 1
                            state['phrase'] = f"{FEEDBACK_MESSAGES[exercise_name]['good_rep']} ({state['reps']})"
                        else:
                            self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_ball'])

            # --- 3. BRACCIA CON MINIBALL ---
            elif exercise_name == 'braccia_con_miniball':
                p_spalla_sx = self._pt(landmarks, "LEFT_SHOULDER")
                p_bacino_sx = self._pt(landmarks, "LEFT_HIP")
                p_ginocchio_sx = self._pt(landmarks, "LEFT_KNEE")
                angle = self._calculate_angle(p_spalla_sx, p_bacino_sx, p_ginocchio_sx)
                self.last_angle = angle

                if state['stage'] == 'down':
                    if angle < 158:
                        state['stage'] = 'up'
                        state['min_up_angle'] = angle  # inizia tracciamento picco

                elif state['stage'] == 'up':
                    # Aggiorna il minimo angolo raggiunto (= massimo sollevamento)
                    state['min_up_angle'] = min(state['min_up_angle'], angle)

                    if angle > 168:
                        lifted_ok = state['min_up_angle'] < 152  # ha raggiunto un sollevamento reale
                        state['stage'] = 'down'
                        state['min_up_angle'] = 180.0  # reset per il prossimo rep

                        if lifted_ok:
                            state['reps'] += 1
                            state['phrase'] = f"{random.choice(FEEDBACK_MESSAGES[exercise_name]['motivational'])} R: {state['reps']}"
                        else:
                            self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_low'])

            # --- 4. FITBALL BACK EXTENSIONS ---
            elif exercise_name == 'fitball_back_extensions':
                p_caviglia = self._pt(landmarks, "LEFT_ANKLE")
                p_bacino   = self._pt(landmarks, "LEFT_HIP")
                p_spalla   = self._pt(landmarks, "LEFT_SHOULDER")
                angle = self._calculate_angle(p_caviglia, p_bacino, p_spalla)
                self.last_angle = angle

                if state['stage'] == 'down':
                    if angle > 165:
                        state['stage'] = 'up'
                    elif angle > 145 and angle <= 165 and self.feedback_timer % 15 == 0:
                        self._set_correction(state, "Ottimo, ma sali ancora un po'!")

                elif state['stage'] == 'up':
                    if angle < 140:
                        state['stage'] = 'down'

                        # Check secondario: ginocchia sufficientemente tese (no trucco con le gambe)
                        knees_ok = True
                        if self._vis(landmarks, "LEFT_HIP", "LEFT_KNEE", "LEFT_ANKLE"):
                            knee_angle = self._calculate_angle(
                                self._pt(landmarks, "LEFT_HIP"),
                                self._pt(landmarks, "LEFT_KNEE"),
                                self._pt(landmarks, "LEFT_ANKLE")
                            )
                            knees_ok = knee_angle > 140

                        if knees_ok:
                            state['reps'] += 1
                            state['phrase'] = f"{FEEDBACK_MESSAGES[exercise_name]['good_rep']} ({state['reps']})"
                        else:
                            self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_knees'])

            # --- 5. OVERHEAD BALL SIDE BENDS ---
            elif exercise_name == 'overhead_ball_side_bends':
                p_caviglia_l = self._pt(landmarks, "LEFT_ANKLE")
                p_bacino_l   = self._pt(landmarks, "LEFT_HIP")
                p_spalla_l   = self._pt(landmarks, "LEFT_SHOULDER")
                angle_left = self._calculate_angle(p_caviglia_l, p_bacino_l, p_spalla_l)

                p_caviglia_r = self._pt(landmarks, "RIGHT_ANKLE")
                p_bacino_r   = self._pt(landmarks, "RIGHT_HIP")
                p_spalla_r   = self._pt(landmarks, "RIGHT_SHOULDER")
                angle_right = self._calculate_angle(p_caviglia_r, p_bacino_r, p_spalla_r)

                angle = min(angle_left, angle_right)
                self.last_angle = angle

                if state['stage'] == 'center':
                    if angle < 155:
                        state['stage'] = 'bend'
                    elif angle >= 155 and angle < 168 and self.feedback_timer % 15 == 0:
                        self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_short'])

                elif state['stage'] == 'bend':
                    if angle > 173:
                        state['stage'] = 'center'

                        # Check secondario: gambe dritte durante la flessione laterale
                        knees_ok = True
                        if self._vis(landmarks, "LEFT_HIP", "LEFT_KNEE", "LEFT_ANKLE",
                                               "RIGHT_HIP", "RIGHT_KNEE", "RIGHT_ANKLE"):
                            knee_l = self._calculate_angle(
                                self._pt(landmarks, "LEFT_HIP"),
                                self._pt(landmarks, "LEFT_KNEE"),
                                self._pt(landmarks, "LEFT_ANKLE")
                            )
                            knee_r = self._calculate_angle(
                                self._pt(landmarks, "RIGHT_HIP"),
                                self._pt(landmarks, "RIGHT_KNEE"),
                                self._pt(landmarks, "RIGHT_ANKLE")
                            )
                            knees_ok = knee_l > 155 and knee_r > 155

                        if knees_ok:
                            state['reps'] += 1
                            state['phrase'] = f"{FEEDBACK_MESSAGES[exercise_name]['good_rep']} ({state['reps']})"
                        else:
                            self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_knees'])

            # --- 6. SWISS BALL ROLL OUT ---
            elif exercise_name == 'roll_out_sulla_fitball':
                p_spalla   = self._pt(landmarks, "LEFT_SHOULDER")
                p_bacino   = self._pt(landmarks, "LEFT_HIP")
                p_ginocchio = self._pt(landmarks, "LEFT_KNEE")
                angle = self._calculate_angle(p_spalla, p_bacino, p_ginocchio)
                self.last_angle = angle

                if state['stage'] == 'start':
                    if angle < 155:
                        state['stage'] = 'extension'
                        state['arch_detected'] = False  # reset ad ogni nuova estensione

                elif state['stage'] == 'extension':
                    if angle > 165 and angle <= 172 and self.feedback_timer % 15 == 0:
                        self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_back'])
                        state['arch_detected'] = True  # inarco rilevato: blocca il conteggio

                    elif angle > 172:
                        state['stage'] = 'start'

                        if not state['arch_detected']:
                            state['reps'] += 1
                            state['phrase'] = f"{FEEDBACK_MESSAGES[exercise_name]['good_rep']} ({state['reps']})"
                        else:
                            self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_back'])
                        state['arch_detected'] = False  # reset per la prossima ripetizione

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

    def get_last_angle(self):
        return self.last_angle

    def get_is_correcting(self):
        return self.is_correcting

    def get_last_correction_phrase(self):
        return self.last_correction_phrase
