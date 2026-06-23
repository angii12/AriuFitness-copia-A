import os
import json
import base64
import collections
import cv2
import numpy as np
import torch
import torch.nn as float
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# --- IMPORTA LA TUA LOGICA ORIGINALE ---
from logic import util, reps_tracker
from models_pytorch import MultiInputLSTM, device 
from frame import Frame 

SKIP_INTERVAL = 6      # Campiona un frame ogni 6 (pari a circa ~0.2 secondi di salto)

tracker = reps_tracker.ExerciseTracker()

app = FastAPI(title="Ariufitness AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURAZIONE E CARICAMENTO ENSEMBLE DI 6 MODELLI BINARI ---
MODELS_PATH = util.getModelsPath()
PARAMS_PATH = os.path.join(MODELS_PATH, 'best_params_3rami.npy')

print("Caricamento parametri ottimali del modello a 3 rami...")
best_param = np.load(PARAMS_PATH, allow_pickle=True).item()

# Lista degli esercizi esatti (corrispondenti ai nomi dei file .pth salvati)
esercizi = [
    "sollevamento_gambe_stringendo_la_fitball",
    "braccia_con_miniball",
    "roll_out_sulla_fitball",
    "medicine_ball_squat",
    "fitball_back_extensions",
    "overhead_ball_side_bends"
]

# Dizionario che conterrà le istanze dei 6 modelli pronti a lavorare
modelli_ensemble = {}

print("Caricamento in memoria dei 6 modelli binari indipendenti...")
for esercizio in esercizi:
    # 1. Inizializziamo l'architettura forzando num_classes=1 (Classificazione Binaria)
    model_binario = MultiInputLSTM(
        input_size_1=best_param['X1_size'],
        input_size_2=best_param['X2_size'],
        input_size_3=best_param['X3_size'],
        hidden_size_1=best_param['hidden_size_1'],
        hidden_size_2=best_param['hidden_size_2'],
        hidden_size_3=best_param['hidden_size_3'],
        num_classes=1, # <--- 1 solo output per modello binario
        dropout_rate=best_param['dropout_rate']
    ).to(device)

    # 2. Carichiamo i pesi specifici salvati durante la Fase 3
    weights_path = os.path.join(MODELS_PATH, f'LSTM_Binario_{esercizio}.pth')
    model_binario.load_state_dict(torch.load(weights_path, map_location=device))
    model_binario.eval() # Modalità inferenza
    
    # 3. Salviamo il modello nel nostro dizionario
    modelli_ensemble[esercizio] = model_binario

print("Tutti e 6 i modelli binari sono stati caricati e sono pronti!")

# --- GESTIONE DEL FLUSSO WEBSOCKET CON BUFFER MEMORIA ---
@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client React connesso al canale WebSocket!")

    # Reset dei contatori all'apertura di una nuova sessione
    global tracker
    tracker = reps_tracker.ExerciseTracker()
    
    #MODIFICA: Usiamo una lista normale come "storico grezzo" invece del deque rigido da 8
    raw_history_buffer = []
    max_history_length = 50 # Contiene abbastanza frame storici per coprire il salto temporale    

    # STATO INIZIALE: Il sistema attende che l'utente sia visibile per la prima volta
    is_fully_visible_at_start = False

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            image_base64 = message.get("image")
            
            if image_base64:
                if "," in image_base64:
                    image_base64 = image_base64.split(",")[1]
                
                image_bytes = base64.b64decode(image_base64)
                np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
                
                # Decodifichiamo l'immagine in formato BGR (OpenCV standard)
                frame_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                
                if frame_bgr is None:
                    continue
                
                # 1. Istanziamo la tua classe originale passandogli l'immagine
                frame_obj = Frame(frame_bgr)
                
                # 2. Riproduciamo i passaggi del tuo script Dataset: interpolazione e calcoli
                # (Dato che lavoriamo frame per frame in diretta, passiamo None per i fotogrammi adiacenti)
                frame_obj.interpolate_keypoints(None, None)
                frame_obj.extract_angles()
                
                # 3. Estraiamo i tre vettori di feature
                kp_data = frame_obj.process_keypoints()   # Ramo 1
                an_data = frame_obj.process_angles()      # Ramo 2
                ball_data = frame_obj.process_only_ball() # Ramo 3

                # --- NUOVO CONTROLLO MIRATO SUGLI EXERCISE KEYPOINTS ---
                landmarks_mediapipe = frame_obj.get_landmarks()
                
                # Indici MediaPipe per: spalle, gomiti, polsi, anche, ginocchia, caviglie/piedi
                indici_richiesti = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
                                
# Se non siamo ancora partiti ufficialmente, facciamo il controllo severo
                if not is_fully_visible_at_start:
                    corpo_visibile = True
                    if not landmarks_mediapipe:
                        corpo_visibile = False
                    else:
                        for idx in indici_richiesti:
                            if idx >= len(landmarks_mediapipe) or landmarks_mediapipe[idx].visibility < 0.5:
                                corpo_visibile = False
                                break
                    
                    if not corpo_visibile:
                        response = {
                            "status": "buffering",
                            "frames_stacked": len(raw_history_buffer),
                            "exercise": "Allontanati e inquadra il corpo 🧍‍♂️",
                            "confidence": 0.0,
                            "reps": tracker.get_reps(),
                            "phrase": "Posizionati nella tua postazione in modo da mostrare tutte le articolazioni."
                        }
                        await websocket.send_text(json.dumps(response))
                        continue # Salta il frame e non riempie il buffer iniziale
                    else:
                        # SBLOCCO: L'utente si è posizionato correttamente per la prima volta!
                        is_fully_visible_at_start = True
                        print("🚀 Utente posizionato correttamente. Sistema di riconoscimento sbloccato!")
                
                # Se MediaPipe si perde completamente un frame a causa di un'occlusione estrema durante il movimento, 
                # facciamo solo un check di sopravvivenza per non far crashare i calcoli successivi
                if not landmarks_mediapipe:
                    continue
                # -------------------------------------------------------------------------------------                
                # 4. Salviamo questa terna nel nostro buffer temporaneo
                raw_history_buffer.append((kp_data, an_data, ball_data))

                # Se lo storico cresce troppo, eliminiamo il frame più vecchio
                if len(raw_history_buffer) > max_history_length:
                    raw_history_buffer.pop(0)

                # Calcoliamo la lunghezza minima della cronologia necessaria per estrarre 8 frame a salti
                # Es: Con 8 frame richiesti e SKIP_INTERVAL=6, servono almeno (7 * 6) + 1 = 43 frame accumulati
                min_frames_required = (8 - 1) * SKIP_INTERVAL + 1
                
                # 5. MODIFICA: Se non abbiamo abbastanza cronologia di frame, chiediamo a React di fare buffering
                if len(raw_history_buffer) < min_frames_required:
                    response = {
                        "status": "buffering",
                        "frames_stacked": len(raw_history_buffer),
                        "exercise": "In attesa di dati...",
                        "confidence": 0.0,
                        "reps": 0,
                        "phrase": f"Inizializzazione della telecamera... ({len(raw_history_buffer)}/{min_frames_required})"
                    }
                    await websocket.send_text(json.dumps(response))
                    continue

                # 6.MODIFICA: Campionamento a salti equidistanti (Stesso comportamento del Dataset!)
                # Partiamo dall'ultimo frame inserito (-1) e andiamo a ritroso estraendo un frame ogni SKIP_INTERVAL
                sampled_window = raw_history_buffer[-1 : -min_frames_required - 1 : -SKIP_INTERVAL]
                
                # Ripristiniamo l'ordine cronologico corretto (da più vecchio a più recente)
                sampled_window.reverse()

                # 7. Recuperiamo i dati dei keypoints per controllare il movimento effettivo sulla finestra campionata
                kp_window_np = np.array([f[0] for f in sampled_window])

                # Calcoliamo la deviazione standard temporale per ogni coordinata
                # Questo ci dice quanto variano i punti nel tempo (negli ultimi 8 frame)
                movimento_rilevato = np.std(kp_window_np, axis=0).mean()

                # SOGLIA DI MOVIMENTO: Regola questo valore empiricamente!
                # Se il valore è inferiore alla soglia, l'utente è fermo o si muove pochissimo.
                SOGLIA_STASI = 0.0001 

                if movimento_rilevato < SOGLIA_STASI:
                    # Se la persona è ferma, forziamo il risultato a "In attesa di movimento"
                    response = {
                        "status": "predicted",
                        "frames_stacked": 8,
                        "exercise": "In attesa di movimento... 🛑",
                        "confidence": 0.0
                    }
                    await websocket.send_text(json.dumps(response))
                    continue
                
                # 6. Se il buffer è pieno (ha esattamente 8 frame), costruiamo il minibatch per la LSTM
                # Estraiamo separatamente le liste per i 3 rami dalla coda
                kp_window = [f[0] for f in sampled_window]
                an_window = [f[1] for f in sampled_window]
                ball_window = [f[2] for f in sampled_window]

                # Convertiamo in array NumPy aggiungendo la dimensione del Batch (= 1)
                # Shape finale desiderata dalla LSTM: (1, 8, numero_features)
                x1_np = np.expand_dims(np.array(kp_window), axis=0)
                x2_np = np.expand_dims(np.array(an_window), axis=0)
                x3_np = np.expand_dims(np.array(ball_window), axis=0)
                
                # Trasformiamo in Tensor PyTorch e spostiamo sulla GPU/CPU corretta
                x1_tensor = torch.tensor(x1_np, dtype=torch.float32).to(device)
                x2_tensor = torch.tensor(x2_np, dtype=torch.float32).to(device)
                x3_tensor = torch.tensor(x3_np, dtype=torch.float32).to(device)
                
                # --- NUOVA LOGICA DI INFERENZA MULTI-MODELLO (ENSEMBLE) ---
                best_exercise = "Esercizio Sconosciuto"
                highest_confidence = 0.0
                
                with torch.no_grad():
                    # Interroghiamo tutti e 6 i modelli sullo stesso identico input temporale
                    for nome_esercizio, modello in modelli_ensemble.items():
                        logit = modello(x1_tensor, x2_tensor, x3_tensor)
                        # Schiacciamo il logit tra 0.0 e 1.0 usando la Sigmoide (visto che l'output è pari a 1)
                        probabilita_binaria = torch.sigmoid(logit).item()
                        
                        # Il modello con il punteggio più alto si aggiudica la predizione corrente
                        if probabilita_binaria > highest_confidence:
                            highest_confidence = probabilita_binaria
                            best_exercise = nome_esercizio

                confidence_percentage = round(highest_confidence * 100, 2)

                
                # --- AGGIORNAMENTO DEL TRACKER CON LE CORREZIONI (Fase 4) ---
                # Aggiorna il contatore solo se l'IA è sufficientemente stabile
                if confidence_percentage > 70.0:
                    # Otteniamo la lista di landmark tramite la funzione get_landmarks() del tuo Frame
                    landmarks_mediapipe = frame_obj.get_landmarks()
                    
                    if landmarks_mediapipe:
                        # Comunichiamo al tracker i punti e l'esercizio predetto
                        tracker.update(best_exercise, landmarks_mediapipe)

                # 8. Inviamo il responso finale in tempo reale a React recuperando 
                # i contatori aggiornati dal tracker
                response = {
                    "status": "predicted",
                    "frames_stacked": 8,
                    "exercise": best_exercise,
                    "confidence": confidence_percentage, 
                    "reps": tracker.get_reps(),
                    "phrase": tracker.get_phrase()
                }
                await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        print("Client React disconnesso.")
    except Exception as e:
        print(f"Errore imprevisto nel loop WebSocket: {e}")