import random
import numpy as np

# Mappatura indice dei landmark MediaPipe Pose
LANDMARK_DICT = {
    "LEFT_SHOULDER": 11, "RIGHT_SHOULDER": 12, "LEFT_ELBOW": 13, "RIGHT_ELBOW": 14,
    "LEFT_WRIST": 15, "RIGHT_WRIST": 16, "LEFT_HIP": 23, "RIGHT_HIP": 24,
    "LEFT_KNEE": 25, "RIGHT_KNEE": 26, "LEFT_ANKLE": 27, "RIGHT_ANKLE": 28,
    "LEFT_FOOT_INDEX": 31, "RIGHT_FOOT_INDEX": 32
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
        'correction_knee_forward': 'Le ginocchia non devono superare la punta dei piedi!',
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
        'correction_arms': 'Tieni le braccia ben distese sopra la testa!',
        'good_rep': 'Flessione perfetta!'
    }
}


class ExerciseTracker:

    # Soglia massima di avanzamento del ginocchio OLTRE la punta del piede durante lo
    # squat, espressa come rapporto sulla lunghezza del piede (ankle->foot_index).
    KNEE_FORWARD_RATIO_THRESHOLD: float = 2
 
    # Frame consecutivi richiesti per confermare una transizione di stage (down<->up).
    # Evita che un singolo frame con angolo "sporco" per rumore di tracking (landmark
    # perso/instabile) faccia scattare un ciclo down->up fantasma, cioè una rep contata
    # senza che l'utente si sia effettivamente mosso.
    STAGE_CONFIRM_FRAMES: int = 2
 
    # Rapporto massimo plausibile di avanzamento ginocchio oltre la punta del piede
    # (in multipli della lunghezza del piede). Oltre questo valore la lettura è quasi
    # certamente un errore di tracking su un singolo frame, non movimento reale: viene
    # scartata invece di contribuire al picco della ripetizione.
    KNEE_FORWARD_PLAUSIBILITY_CAP: float = 3.0

    # Angolo minimo spalla-gomito-polso (in gradi) sotto il quale il braccio è
    # considerato "piegato" invece che disteso, in overhead_ball_side_bends.
    ARM_EXTENSION_THRESHOLD: float = 125.0


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
                'phrase': FEEDBACK_MESSAGES['medicine_ball_squat']['start'],
                # Contatori di conferma per il debounce delle transizioni di stage
                'down_confirm': 0, 'up_confirm': 0,
                # Massimo avanzamento del ginocchio oltre la punta del piede (rapporto
                # sulla lunghezza del piede) osservato durante la discesa corrente
                # (reset ad ogni nuova ripetizione).
                'knee_fwd_peak_l': 0.0, 'knee_fwd_peak_r': 0.0
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
                'phrase': FEEDBACK_MESSAGES['overhead_ball_side_bends']['start'],
                'min_elbow_angle': 180.0
            }
        }
        self.feedback_timer = 0
        self.last_predicted = None
        self.last_angle = None
        self.is_correcting = False
        self.last_correction_phrase = None
        # Ultimo rapporto di avanzamento ginocchio calcolato (diagnostica/tuning squat).
        self.last_knee_forward_ratio = None
        # Ultimo angolo minimo di gomito osservato (diagnostica/tuning side bends).
        self.last_min_elbow_angle = None


    def _pt(self, lm, key):
        """Restituisce [x, y] del landmark specificato."""
        idx = LANDMARK_DICT[key]
        return [lm[idx].x, lm[idx].y]

    def _z(self, lm, key):
        """Restituisce la coordinata z (profondità rispetto alla camera) del landmark.

        Convenzione MediaPipe: valori più piccoli = landmark più vicino alla camera,
        con origine approssimativa nel punto medio dei fianchi.
        """
        return lm[LANDMARK_DICT[key]].z

    def _vis(self, lm, *keys, threshold=0.45):
        """True se tutti i landmark indicati hanno visibility >= threshold."""
        return all(lm[LANDMARK_DICT[k]].visibility >= threshold for k in keys)

    def _knee_forward_excess(self, lm, ankle_key, knee_key, toe_key):
        """Calcola di quanto il ginocchio ha superato la punta del piede.
 
        La direzione "in avanti" è definita dal vettore caviglia->punta del piede
        (nel piano x, z) invece che da un asse fisso della camera: usare la
        geometria del piede stesso come riferimento rende il check valido anche
        con inquadrature non perfettamente frontali, perché indica dove sta
        "avanti" per quella gamba indipendentemente dall'angolazione della ripresa.
 
        Args:
        - lm: lista dei landmark MediaPipe del frame corrente
        - ankle_key, knee_key, toe_key: chiavi LANDMARK_DICT per caviglia, ginocchio,
          punta del piede (stesso lato)
 
        Returns:
        - (eccesso, lunghezza_piede): eccesso è un rapporto >= 0 sulla lunghezza del
          piede (0 se il ginocchio è dietro o allineato con la punta, crescente se
          la supera); lunghezza_piede è il fattore di normalizzazione usato.
        """
        ankle = np.array([lm[LANDMARK_DICT[ankle_key]].x, self._z(lm, ankle_key)])
        toe   = np.array([lm[LANDMARK_DICT[toe_key]].x,   self._z(lm, toe_key)])
        knee  = np.array([lm[LANDMARK_DICT[knee_key]].x,  self._z(lm, knee_key)])
 
        forward_vec = toe - ankle
        foot_len = float(np.linalg.norm(forward_vec))
        if foot_len < 1e-6:
            return 0.0, foot_len
 
        forward_dir = forward_vec / foot_len
        excess = float(np.dot(knee - toe, forward_dir))  # proiezione lungo "avanti"
        return max(0.0, excess) / foot_len, foot_len

    
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
                    # Debounce: richiede STAGE_CONFIRM_FRAMES consecutivi sotto soglia
                    # prima di considerare iniziata la discesa. Un singolo frame con
                    # angolo basso per rumore di tracking (landmark perso/instabile)
                    # non deve bastare a far scattare un ciclo down->up fantasma
                    if angle < 100:
                        state['down_confirm'] += 1
                    else:
                        state['down_confirm'] = 0

                    if state['down_confirm'] >= self.STAGE_CONFIRM_FRAMES:
                        state['stage'] = 'down'
                        state['down_confirm'] = 0
                        state['knee_fwd_peak_l'] = 0.0
                        state['knee_fwd_peak_r'] = 0.0
                        print(f"[SQUAT] ↓ Inizio discesa (angle={angle:.1f}°)")
                    elif angle < 140 and self.feedback_timer % 15 == 0:
                        self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_depth'])

                elif state['stage'] == 'down':
                    # --- Avanzamento ginocchio oltre la punta del piede ---
                    # Riferimento: FOOT_INDEX (punta del piede), confrontato
                    # direttamente frame per frame — non più una baseline "in piedi"
                    # calibrata a inizio rep.
                    knee_feet_ok = self._vis(landmarks, "LEFT_KNEE", "LEFT_ANKLE", "LEFT_FOOT_INDEX",
                                                        "RIGHT_KNEE", "RIGHT_ANKLE", "RIGHT_FOOT_INDEX")
                    if knee_feet_ok:
                        excess_l, _ = self._knee_forward_excess(landmarks, "LEFT_ANKLE", "LEFT_KNEE", "LEFT_FOOT_INDEX")
                        excess_r, _ = self._knee_forward_excess(landmarks, "RIGHT_ANKLE", "RIGHT_KNEE", "RIGHT_FOOT_INDEX")

                        scartato_l = excess_l > self.KNEE_FORWARD_PLAUSIBILITY_CAP
                        scartato_r = excess_r > self.KNEE_FORWARD_PLAUSIBILITY_CAP

                        # Scarta letture chiaramente implausibili (quasi certamente un
                        # errore di tracking su un singolo frame) invece di lasciarle
                        # inquinare il picco della ripetizione con un valore assurdo.
                        if not scartato_l:
                            state['knee_fwd_peak_l'] = max(state['knee_fwd_peak_l'], excess_l)
                        if not scartato_r:
                            state['knee_fwd_peak_r'] = max(state['knee_fwd_peak_r'], excess_r)

                        self.last_knee_forward_ratio = max(state['knee_fwd_peak_l'], state['knee_fwd_peak_r'])

                        print(
                            f"[SQUAT][DOWN] angle={angle:.1f}° | "
                            f"excess_l={excess_l:.3f}{'(SCARTATO)' if scartato_l else ''} "
                            f"excess_r={excess_r:.3f}{'(SCARTATO)' if scartato_r else ''} | "
                            f"peak_l={state['knee_fwd_peak_l']:.3f} peak_r={state['knee_fwd_peak_r']:.3f} | "
                            f"soglia={self.KNEE_FORWARD_RATIO_THRESHOLD}"
                        )
                    else:
                        print(f"[SQUAT][DOWN] angle={angle:.1f}° | visibility FOOT_INDEX insufficiente → check ginocchio saltato")

                    # Debounce anche per la risalita, stessa motivazione della discesa.
                    if angle > 160:
                        state['up_confirm'] += 1
                    else:
                        state['up_confirm'] = 0

                    if state['up_confirm'] >= self.STAGE_CONFIRM_FRAMES:
                        state['stage'] = 'up'
                        state['up_confirm'] = 0

                        # Check secondario 1: tronco non troppo inclinato in avanti
                        trunk_ok = True
                        trunk_l = trunk_r = None
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

                        # Check secondario 3: il ginocchio non deve superare la punta del
                        # piede. Se il picco è rimasto a 0.0 (mai stato possibile calcolarlo
                        # per bassa visibilità di ginocchio/caviglia/punta) il check passa
                        # di default (fail-open, coerente con trunk_ok/sym_ok).
                        knee_ok = (state['knee_fwd_peak_l'] < self.KNEE_FORWARD_RATIO_THRESHOLD and
                                   state['knee_fwd_peak_r'] < self.KNEE_FORWARD_RATIO_THRESHOLD)

                        print(
                            f"[SQUAT][DECISION] angle={angle:.1f}° (sx={angle_sx:.1f}° dx={angle_dx:.1f}°) | "
                            f"trunk_ok={trunk_ok} (l={trunk_l:.1f}° r={trunk_r:.1f}°) | " if trunk_l is not None else
                            f"[SQUAT][DECISION] angle={angle:.1f}° (sx={angle_sx:.1f}° dx={angle_dx:.1f}°) | "
                            f"trunk_ok={trunk_ok} (landmark non visibili) | "
                        )
                        print(
                            f"           sym_ok={sym_ok} (diff={abs(angle_sx-angle_dx):.1f}°) | "
                            f"knee_ok={knee_ok} (peak_l={state['knee_fwd_peak_l']:.3f} peak_r={state['knee_fwd_peak_r']:.3f} soglia={self.KNEE_FORWARD_RATIO_THRESHOLD})"
                        )

                        if trunk_ok and sym_ok and knee_ok:
                            state['reps'] += 1
                            print(f"[SQUAT] ✅ REP CONTATA → totale={state['reps']}")
                            state['phrase'] = f"{FEEDBACK_MESSAGES[exercise_name]['good_rep']} ({state['reps']})"
                        elif not trunk_ok:
                            print(f"[SQUAT] ❌ REP RIFIUTATA → tronco inclinato")
                            self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_trunk'])
                        elif not knee_ok:
                            print(f"[SQUAT] ❌ REP RIFIUTATA → ginocchio avanzato (peak_l={state['knee_fwd_peak_l']:.3f} peak_r={state['knee_fwd_peak_r']:.3f})")
                            self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_knee_forward'])
                        else:
                            print(f"[SQUAT] ❌ REP RIFIUTATA → asimmetria (sx={angle_sx:.1f}° dx={angle_dx:.1f}°)")
                            self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_sym'])

                        # Reset dei picchi per la prossima ripetizione
                        state['knee_fwd_peak_l'] = 0.0
                        state['knee_fwd_peak_r'] = 0.0

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
                        print(f"[SIDE_BEND] ↓ Inizio flessione (angle={angle:.1f}° L={angle_left:.1f}° R={angle_right:.1f}°)")
                    elif angle >= 155 and angle < 168 and self.feedback_timer % 15 == 0:
                        self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_short'])

                elif state['stage'] == 'bend':
                    # Traccia il gomito più piegato osservato finora in questa
                    # ripetizione (stesso pattern del picco usato per lo squat):
                    # un cedimento momentaneo del gomito che si corregge prima del
                    # frame di decisione non deve sfuggire al check.
                    elbow_vis = self._vis(landmarks, "LEFT_SHOULDER", "LEFT_ELBOW", "LEFT_WRIST",
                                                     "RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_WRIST")
                    if elbow_vis:
                        elbow_l = self._calculate_angle(
                            self._pt(landmarks, "LEFT_SHOULDER"),
                            self._pt(landmarks, "LEFT_ELBOW"),
                            self._pt(landmarks, "LEFT_WRIST")
                        )
                        elbow_r = self._calculate_angle(
                            self._pt(landmarks, "RIGHT_SHOULDER"),
                            self._pt(landmarks, "RIGHT_ELBOW"),
                            self._pt(landmarks, "RIGHT_WRIST")
                        )
                        state['min_elbow_angle'] = min(state['min_elbow_angle'], elbow_l, elbow_r)
                        print(
                            f"[SIDE_BEND][BEND] angle={angle:.1f}° | "
                            f"elbow_l={elbow_l:.1f}° elbow_r={elbow_r:.1f}° | "
                            f"min_elbow={state['min_elbow_angle']:.1f}° soglia={self.ARM_EXTENSION_THRESHOLD}"
                        )
                    else:
                        print(f"[SIDE_BEND][BEND] angle={angle:.1f}° | visibility gomiti insufficiente → check braccia saltato")

                    if angle > 173:
                        state['stage'] = 'center'

                        # Check secondario 1: gambe dritte durante la flessione laterale
                        knees_ok = True
                        knee_l = knee_r = None
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

                        # Check secondario 2: braccia rimaste distese sopra la testa
                        # per tutta la flessione (se la visibilità non è mai stata
                        # sufficiente, min_elbow_angle resta a 180.0 e il check passa
                        # di default — fail-open, coerente con knees_ok).
                        arms_ok = state['min_elbow_angle'] > self.ARM_EXTENSION_THRESHOLD

                        print(
                            f"[SIDE_BEND][DECISION] angle={angle:.1f}° (L={angle_left:.1f}° R={angle_right:.1f}°) | "
                            f"knees_ok={knees_ok} (l={knee_l:.1f}° r={knee_r:.1f}° soglia>155)" if knee_l is not None else
                            f"[SIDE_BEND][DECISION] angle={angle:.1f}° | knees_ok={knees_ok} (landmark non visibili)"
                        )
                        print(
                            f"           arms_ok={arms_ok} "
                            f"(min_elbow={state['min_elbow_angle']:.1f}° soglia>{self.ARM_EXTENSION_THRESHOLD}) | "
                            f"elbow_vis_mai_ok={'no' if state['min_elbow_angle'] == 180.0 else 'sì'}"
                        )

                        if knees_ok and arms_ok:
                            state['reps'] += 1
                            print(f"[SIDE_BEND] ✅ REP CONTATA → totale={state['reps']}")
                            state['phrase'] = f"{FEEDBACK_MESSAGES[exercise_name]['good_rep']} ({state['reps']})"
                        elif not knees_ok:
                            print(f"[SIDE_BEND] ❌ REP RIFIUTATA → gambe piegate (l={knee_l:.1f}° r={knee_r:.1f}°)")
                            self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_knees'])
                        else:
                            print(f"[SIDE_BEND] ❌ REP RIFIUTATA → braccia piegate (min_elbow={state['min_elbow_angle']:.1f}°)")
                            self._set_correction(state, FEEDBACK_MESSAGES[exercise_name]['correction_arms'])

                        # Reset per la prossima ripetizione
                        state['min_elbow_angle'] = 180.0
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

        except Exception as e:
            print(f"[TRACKER] Eccezione in update({exercise_name}): {e}")

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

    def get_last_knee_forward_ratio(self):
        """Diagnostica: ultimo rapporto di avanzamento ginocchio/stinco calcolato.

        Utile per loggare/plottare i valori durante test reali e tarare
        KNEE_FORWARD_RATIO_THRESHOLD su dati veri invece che a occhio.
        """
        return self.last_knee_forward_ratio

    def get_last_min_elbow_angle(self):
        """Diagnostica: ultimo angolo minimo di gomito osservato (side bends).
 
        Utile per loggare i valori durante test reali e tarare
        ARM_EXTENSION_THRESHOLD, oltre che per graduare la gravità del
        feedback del coach AI in base a quanto il gomito è piegato.
        """
        return self.last_min_elbow_angle