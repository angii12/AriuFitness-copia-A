import os
import json
import asyncio
import time
import base64
import cv2
import numpy as np
import torch
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from groq import AsyncGroq

from logic import util, reps_tracker
from models_pytorch import MultiInputLSTM, device
from frame import Frame

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

SKIP_INTERVAL = 6

# --- CLIENT GROQ ---
_groq_api_key = os.getenv("GROQ_API_KEY")
groq_client = AsyncGroq(api_key=_groq_api_key) if _groq_api_key else None
if not groq_client:
    print("⚠️  GROQ_API_KEY non trovata: il feedback vocale LLM è disabilitato.")

CORRECTION_COOLDOWN = 5    # secondi minimi tra feedback correttivi
LLM_INTERVAL = 15          # secondi tra feedback motivazionali
DEFAULT_TARGET_REPS = 5

# Frase esatta della correzione "ginocchia oltre la punta dei piedi" (medicine_ball_squat).
# Usata come chiave di confronto per riconoscere quando applicare la gradazione di gravità.
_KNEE_FORWARD_CORRECTION = reps_tracker.FEEDBACK_MESSAGES['medicine_ball_squat']['correction_knee_forward']

# Rapporto (ratio / soglia) oltre il quale l'errore ginocchia-in-avanti è considerato "marcato"
# invece che "lieve". Valore di partenza, da tarare insieme a KNEE_FORWARD_RATIO_THRESHOLD
# in reps_tracker.py con dati reali di webcam.
_KNEE_FORWARD_SEVERE_RATIO = 1.6

# Frase esatta della correzione "braccia piegate" (overhead_ball_side_bends).
_ARMS_BENT_CORRECTION = reps_tracker.FEEDBACK_MESSAGES['overhead_ball_side_bends']['correction_arms']
 
# Gradi sotto ARM_EXTENSION_THRESHOLD oltre i quali l'errore braccia-piegate è considerato
# "marcato" invece che "lieve" (es. soglia 125° e gomito misurato a 100° → 25° di scarto).
_ARMS_BENT_SEVERE_DEFICIT_DEG = 20.0


_SYSTEM_PROMPT_CORREZIONE = (
    "Sei un trainer fitness. Riformula il messaggio di correzione che ti viene dato in modo "
    "naturale, diretto e incoraggiante in italiano. Massimo 10 parole, 1 frase. "
    "Mantieni il significato preciso della correzione — non inventare correzioni diverse. "
    "Conserva SEMPRE il riferimento alla parte del corpo o al gesto indicato (es. ginocchia, busto, gambe) - non genericizzare"
    "in un richiamo vago tipo 'attenzione alla postura'."
    "Se viene indicata una gravità 'marcata', usa un tono più deciso e urgente; se 'lieve', un tono più leggero, quasi un promemoria"
    "Varia leggermente il fraseggio rispetto alla versione originale. "
    "Rispondi SOLO con la frase riformulata, senza saluti, emoji o prefissi."
)

_SYSTEM_PROMPT_MOTIVAZIONE = (
    "Sei un trainer fitness. Dai un breve incoraggiamento in italiano (massimo 10 parole, 1 frase). "
    "Incita l'utente o ricordagli le ripetizioni mancanti. "
    "Rispondi SOLO con la frase, senza saluti, emoji o prefissi."
)

def _knee_forward_severity(tracker: reps_tracker.ExerciseTracker) -> str | None:
    """
    Determina la gravità dell'errore "ginocchia oltre la punta dei piedi" nello squat.
 
    Ritorna 'lieve' o 'marcata' solo se la correzione attiva in questo frame è
    esattamente quella ginocchia-in-avanti; altrimenti None (nessun'altra correzione
    dello squat, o altro esercizio, viene "graduata" da questa funzione).
 
    Args:
    - tracker: l'istanza di ExerciseTracker della sessione corrente
 
    Returns:
    - str | None: 'lieve', 'marcata', oppure None se non applicabile
    """
    if tracker.get_last_correction_phrase() != _KNEE_FORWARD_CORRECTION:
        return None
 
    ratio = tracker.get_last_knee_forward_ratio()
    if ratio is None:
        return None
 
    rel = ratio / reps_tracker.ExerciseTracker.KNEE_FORWARD_RATIO_THRESHOLD
    return "marcata" if rel >= _KNEE_FORWARD_SEVERE_RATIO else "lieve"

def _arms_bent_severity(tracker: reps_tracker.ExerciseTracker) -> str | None:
    """
    Determina la gravità dell'errore "braccia piegate" in overhead_ball_side_bends,
    con la stessa logica di _knee_forward_severity: None se la correzione attiva in
    questo frame non è esattamente quella, altrimenti 'lieve' o 'marcata' in base a
    quanti gradi sotto soglia è sceso il gomito peggiore della ripetizione.
 
    Args:
    - tracker: l'istanza di ExerciseTracker della sessione corrente
 
    Returns:
    - str | None: 'lieve', 'marcata', oppure None se non applicabile
    """
    if tracker.get_last_correction_phrase() != _ARMS_BENT_CORRECTION:
        return None
 
    min_elbow = tracker.get_last_min_elbow_angle()
    if min_elbow is None:
        return None
 
    deficit_deg = reps_tracker.ExerciseTracker.ARM_EXTENSION_THRESHOLD - min_elbow
    return "marcata" if deficit_deg >= _ARMS_BENT_SEVERE_DEFICIT_DEG else "lieve"
 
 
def _correction_severity(tracker: reps_tracker.ExerciseTracker) -> str | None:
    """
    Calcola una gravità testuale ('lieve'/'marcata') per le correzioni che la
    supportano. Ritorna None per le correzioni senza gradazione (es. tronco,
    simmetria, profondità...) o per il feedback puramente motivazionale.
 
    Per aggiungere una nuova correzione graduata in futuro: scrivere una funzione
    _xxx_severity() sullo stesso modello di _knee_forward_severity /
    _arms_bent_severity e aggiungerla qui nell'OR — sono mutuamente esclusive
    perché ogni frame ha al più una correzione attiva.
    """
    return (
        _knee_forward_severity(tracker)
        or _arms_bent_severity(tracker)
    )


async def genera_feedback_llm(
    esercizio: str,
    angolo: float,
    reps: int,
    is_correcting: bool,
    correction_phrase: str | None,
    gravita: str | None = None,
) -> str | None:
    if groq_client is None:
        return None
    try:
        rimanenti = max(DEFAULT_TARGET_REPS - reps, 0)
        if is_correcting and correction_phrase:
            system_prompt = _SYSTEM_PROMPT_CORREZIONE
            user_msg = (
                f"Esercizio: {esercizio.replace('_', ' ')}\n"
                f"Correzione da comunicare: \"{correction_phrase}\"\n"
                f"Gravità: {gravita}\n"
                f"Riformula questa correzione specifica in modo naturale e diretto."
            )
        else:
            system_prompt = _SYSTEM_PROMPT_MOTIVAZIONE
            user_msg = (
                f"Esercizio: {esercizio.replace('_', ' ')}\n"
                f"Ripetizioni completate: {reps} su {DEFAULT_TARGET_REPS} (mancano {rimanenti})\n"
                f"Angolo rilevato: {angolo:.1f}°"
            )
        resp = await groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=30,
            temperature=0.8,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️  Groq errore: {e}")
        return None

app = FastAPI(title="Ariufitness AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- PARAMETRI ARCHITETTURA (caricati una volta sola all'avvio) ---
MODELS_PATH = util.getModelsPath()
PARAMS_PATH = os.path.join(MODELS_PATH, 'best_params_3rami.npy')

print("Caricamento parametri ottimali del modello a 3 rami...")
best_param = np.load(PARAMS_PATH, allow_pickle=True).item()

# Insieme degli esercizi che dispongono di un modello addestrato
ESERCIZI_CON_MODELLO = {
    "sollevamento_gambe_stringendo_la_fitball",
    "braccia_con_miniball",
    "roll_out_sulla_fitball",
    "medicine_ball_squat",
    "fitball_back_extensions",
    "overhead_ball_side_bends",
}

# Cache dei modelli già caricati: evita di rileggere il disco ad ogni cambio esercizio
_cache_modelli: dict = {}


def carica_modello(nome_esercizio: str):
    """
    Carica il modello binario per l'esercizio richiesto.
    Usa la cache in-memory per evitare ricaricamenti da disco.
    Restituisce il modello PyTorch pronto all'inferenza, oppure None
    se il file .pth non esiste.
    """
    if nome_esercizio in _cache_modelli:
        return _cache_modelli[nome_esercizio]

    weights_path = os.path.join(MODELS_PATH, f"LSTM_Binario_{nome_esercizio}.pth")
    if not os.path.exists(weights_path):
        return None

    print(f"  → Caricamento modello per '{nome_esercizio}' da disco...")
    modello = MultiInputLSTM(
        input_size_1=best_param["X1_size"],
        input_size_2=best_param["X2_size"],
        input_size_3=best_param["X3_size"],
        hidden_size_1=best_param["hidden_size_1"],
        hidden_size_2=best_param["hidden_size_2"],
        hidden_size_3=best_param["hidden_size_3"],
        num_classes=1,
        dropout_rate=best_param["dropout_rate"],
    ).to(device)

    modello.load_state_dict(torch.load(weights_path, map_location=device))
    modello.eval()

    _cache_modelli[nome_esercizio] = modello
    print(f"  ✓ Modello '{nome_esercizio}' pronto (memorizzato in cache).")
    return modello


# --- WEBSOCKET ---
@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connesso al canale WebSocket.")

    tracker = reps_tracker.ExerciseTracker()
    raw_history_buffer: list = []
    max_history_length = 50
    is_fully_visible_at_start = False

    selected_exercise: str | None = None
    modello_attivo = None           # Unico modello attivo per la sessione corrente

    # Stato feedback LLM (per-connessione)
    llm_task = None
    pending_llm_feedback: tuple | None = None
    llm_feedback_id: int = 0
    last_feedback_time: float = time.time()
    llm_enabled: bool = True

    # Indici MediaPipe per le principali articolazioni del corpo
    INDICI_CORPO = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
    MIN_FRAMES = (8 - 1) * SKIP_INTERVAL + 1   # 43 frame necessari per la finestra da 8
    SOGLIA_STASI = 0.0001

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # ── Messaggio di selezione esercizio ──────────────────────────────
            if "selected_exercise" in message:
                nuovo = message["selected_exercise"]

                if nuovo == selected_exercise:
                    continue    # Stesso esercizio: niente da fare

                selected_exercise = nuovo
                llm_enabled = bool(message.get("llm_enabled", True))
                print(f"\nEsercizio selezionato: '{selected_exercise}' (LLM {'ON' if llm_enabled else 'OFF'})")

                # Carica il modello corrispondente (o segnala l'assenza)
                modello_attivo = carica_modello(selected_exercise)
                if modello_attivo is None:
                    print(f"⚠️  AVVISO: nessun modello addestrato per '{selected_exercise}'.")

                # Resetta il contesto per il nuovo esercizio
                tracker = reps_tracker.ExerciseTracker()
                raw_history_buffer = []
                is_fully_visible_at_start = False

                # Resetta stato feedback LLM
                if llm_task is not None:
                    llm_task.cancel()
                    llm_task = None
                pending_llm_feedback = None
                last_feedback_time = time.time()
                continue

            # ── Frame video ───────────────────────────────────────────────────
            image_base64 = message.get("image")
            if not image_base64:
                continue

            # Risposta immediata se non c'è nessun modello per l'esercizio scelto
            if modello_attivo is None:
                nome_leggibile = (selected_exercise or "").replace("_", " ").title()
                response = {
                    "status": "no_model",
                    "frames_stacked": 0,
                    "exercise": "Modello non disponibile",
                    "confidence": 0.0,
                    "reps": 0,
                    "phrase": (
                        f"L'esercizio '{nome_leggibile}' non ha un modello di riconoscimento."
                        if selected_exercise
                        else "Seleziona un esercizio."
                    ),
                }
                await websocket.send_text(json.dumps(response))
                continue

            # Decodifica frame
            if "," in image_base64:
                image_base64 = image_base64.split(",")[1]
            frame_bgr = cv2.imdecode(
                np.frombuffer(base64.b64decode(image_base64), dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
            if frame_bgr is None:
                continue

            # Estrazione feature
            frame_obj = Frame(frame_bgr)
            frame_obj.interpolate_keypoints(None, None)
            frame_obj.extract_angles()

            kp_data   = frame_obj.process_keypoints()
            an_data   = frame_obj.process_angles()
            ball_data = frame_obj.process_only_ball()

            landmarks = frame_obj.get_landmarks()

            # ── Controllo visibilità iniziale ─────────────────────────────────
            if not is_fully_visible_at_start:
                corpo_ok = bool(landmarks) and all(
                    i < len(landmarks) and landmarks[i].visibility >= 0.5
                    for i in INDICI_CORPO
                )
                if not corpo_ok:
                    await websocket.send_text(json.dumps({
                        "status": "buffering",
                        "frames_stacked": 0,
                        "max_frames": MIN_FRAMES,
                        "exercise": "Allontanati e inquadra il corpo",
                        "confidence": 0.0,
                        "reps": tracker.get_reps(),
                        "phrase": "Posizionati in modo da mostrare tutte le articolazioni.",
                    }))
                    continue

                is_fully_visible_at_start = True
                print("Utente posizionato correttamente. Riconoscimento sbloccato!")

            if not landmarks:
                continue

            # ── Buffer cronologico ────────────────────────────────────────────
            raw_history_buffer.append((kp_data, an_data, ball_data))
            if len(raw_history_buffer) > max_history_length:
                raw_history_buffer.pop(0)

            if len(raw_history_buffer) < MIN_FRAMES:
                await websocket.send_text(json.dumps({
                    "status": "buffering",
                    "frames_stacked": len(raw_history_buffer),
                    "max_frames": MIN_FRAMES,
                    "exercise": "In attesa di dati...",
                    "confidence": 0.0,
                    "reps": 0,
                    "phrase": f"Inizializzazione... ({len(raw_history_buffer)}/{MIN_FRAMES})",
                }))
                continue

            # ── Campionamento a salti equidistanti ────────────────────────────
            sampled = raw_history_buffer[-1 : -MIN_FRAMES - 1 : -SKIP_INTERVAL]
            sampled.reverse()

            # Controllo stasi
            movimento = np.std(np.array([f[0] for f in sampled]), axis=0).mean()
            if movimento < SOGLIA_STASI:
                await websocket.send_text(json.dumps({
                    "status": "predicted",
                    "frames_stacked": 8,
                    "exercise": "In attesa di movimento... 🛑",
                    "confidence": 0.0,
                }))
                continue

            # ── Inferenza (solo il modello dell'esercizio scelto) ─────────────
            x1 = torch.tensor(np.expand_dims(np.array([f[0] for f in sampled]), 0), dtype=torch.float32).to(device)
            x2 = torch.tensor(np.expand_dims(np.array([f[1] for f in sampled]), 0), dtype=torch.float32).to(device)
            x3 = torch.tensor(np.expand_dims(np.array([f[2] for f in sampled]), 0), dtype=torch.float32).to(device)

            with torch.no_grad():
                logit = modello_attivo(x1, x2, x3)
                confidence_percentage = round(torch.sigmoid(logit).item() * 100, 2)

            # ── Aggiornamento tracker ─────────────────────────────────────────
            if confidence_percentage > 70.0:
                tracker.update(selected_exercise, landmarks)

            # ── Feedback LLM (non bloccante) ──────────────────────────────────
            current_time = time.time()

            # Raccoglie il risultato se il task precedente è completato
            if llm_task is not None and llm_task.done():
                try:
                    result = llm_task.result()
                    if result:
                        llm_feedback_id += 1
                        pending_llm_feedback = (result, llm_feedback_id)
                except Exception:
                    pass
                llm_task = None

            # Determina se avviare un nuovo task
            if (
                groq_client is not None
                and llm_enabled
                and confidence_percentage > 70.0
                and llm_task is None
                and tracker.get_last_angle() is not None
                and (
                    (tracker.get_is_correcting() and current_time - last_feedback_time >= CORRECTION_COOLDOWN)
                    or (current_time - last_feedback_time >= LLM_INTERVAL)
                )
            ):
                gravita = _correction_severity(tracker) if tracker.get_is_correcting() else None

                last_feedback_time = current_time
                llm_task = asyncio.create_task(
                    genera_feedback_llm(
                        selected_exercise,
                        tracker.get_last_angle(),
                        tracker.get_reps(),
                        tracker.get_is_correcting(),
                        tracker.get_last_correction_phrase(),
                        gravita,
                    )
                )

            # Prepara i campi LLM per la risposta
            if pending_llm_feedback is not None:
                llm_text, llm_id = pending_llm_feedback
                pending_llm_feedback = None
            else:
                llm_text = None
                llm_id = llm_feedback_id

            await websocket.send_text(json.dumps({
                "status": "predicted",
                "frames_stacked": 8,
                "exercise": selected_exercise,
                "confidence": confidence_percentage,
                "reps": tracker.get_reps(),
                "phrase": tracker.get_phrase(),
                "llm_feedback": llm_text,
                "llm_feedback_id": llm_id,
            }))

    except WebSocketDisconnect:
        print("Client disconnesso.")
    except Exception as e:
        print(f"Errore nel loop WebSocket: {e}")
