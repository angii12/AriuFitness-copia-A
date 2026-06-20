import os
import json
import base64
import collections
import cv2
import numpy as np
import torch
import torch.nn.functional as F
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# --- IMPORTA LA TUA LOGICA ORIGINALE ---
from logic import util
from models_pytorch import MultiInputLSTM, device 
# IMPORTANTE: Cambia questa riga inserendo il percorso esatto in cui si trova la tua classe Frame
from frame import Frame 

app = FastAPI(title="Ariufitness AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CARICAMENTO MODELLO A 3 RAMI ---
MODELS_PATH = util.getModelsPath()
PARAMS_PATH = os.path.join(MODELS_PATH, 'best_params_3rami.npy')

print("Caricamento parametri ottimali del modello a 3 rami...")
best_param = np.load(PARAMS_PATH, allow_pickle=True).item()

model = MultiInputLSTM(
    input_size_1=best_param['X1_size'],
    input_size_2=best_param['X2_size'],
    input_size_3=best_param['X3_size'],
    hidden_size_1=best_param['hidden_size_1'],
    hidden_size_2=best_param['hidden_size_2'],
    hidden_size_3=best_param['hidden_size_3'],
    num_classes=best_param['num_classes'],
    dropout_rate=best_param['dropout_rate']
).to(device)

MODEL_WEIGHTS = os.path.join(MODELS_PATH, 'LSTM_Combo3_Ottimizzato.pth')
model.load_state_dict(torch.load(MODEL_WEIGHTS, map_location=device))
model.eval()
print("✅ Modello a 3 rami pronto per l'inferenza in tempo reale.")

DATASET_PATH = util.getDatasetPath()
categories = np.load(os.path.join(DATASET_PATH, "categories.npy"), allow_pickle=True).tolist()


# --- GESTIONE DEL FLUSSO WEBSOCKET CON BUFFER MEMORIA DI LUNGHEZZA 8 ---
@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🔌 Client React connesso al canale WebSocket!")
    
    # Creiamo una coda FIFO di lunghezza massima = 8 (il nostro window_size)
    # Quando la coda è piena (ha 8 elementi) e inseriamo il 9°, il 1° esce automaticamente.
    window_buffer = collections.deque(maxlen=8)
    
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
                
                # 4. Salviamo questa terna nel nostro buffer temporaneo
                window_buffer.append((kp_data, an_data, ball_data))
                
                # 5. Se non abbiamo ancora accumulato almeno 8 frame, diciamo a React di continuare a inviare
                if len(window_buffer) < 8:
                    response = {
                        "status": "buffering",
                        "frames_stacked": len(window_buffer),
                        "exercise": "In attesa di dati...",
                        "confidence": 0.0
                    }
                    await websocket.send_text(json.dumps(response))
                    continue

                # 6. Recuperiamo i dati dei keypoints per controllare il movimento effettivo
                kp_window = [f[0] for f in window_buffer]  # Lista di 8 array di keypoints

                # Convertiamo in un array NumPy (Shape: 8, num_keypoints) per fare i calcoli
                kp_window_np = np.array(kp_window)

                # Calcoliamo la deviazione standard temporale per ogni coordinata
                # Questo ci dice quanto variano i punti nel tempo (negli ultimi 8 frame)
                movimento_rilevato = np.std(kp_window_np, axis=0).mean()

                # SOGLIA DI MOVIMENTO: Regola questo valore empiricamente!
                # Se il valore è inferiore alla soglia, l'utente è fermo o si muove pochissimo.
                SOGLIA_STASI = 0.005 

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

                # --- SE SUPERA LA SOGLIA, PROCEDE CON IL MODELLO A 3 RAMI (Codice attuale) ---
                x1_np = np.expand_dims(kp_window_np, axis=0)
                x2_np = np.expand_dims(np.array([f[1] for f in window_buffer]), axis=0)
                x3_np = np.expand_dims(np.array([f[2] for f in window_buffer]), axis=0)
                
                # 6. Se il buffer è pieno (ha esattamente 8 frame), costruiamo il minibatch per la LSTM
                # Estraiamo separatamente le liste per i 3 rami dalla coda
                kp_window = [f[0] for f in window_buffer]
                an_window = [f[1] for f in window_buffer]
                ball_window = [f[2] for f in window_buffer]
                
                # Convertiamo in array NumPy aggiungendo la dimensione del Batch (= 1)
                # Shape finale desiderata dalla LSTM: (1, 8, numero_features)
                x1_np = np.expand_dims(np.array(kp_window), axis=0)
                x2_np = np.expand_dims(np.array(an_window), axis=0)
                x3_np = np.expand_dims(np.array(ball_window), axis=0)
                
                # Trasformiamo in Tensor PyTorch e spostiamo sulla GPU/CPU corretta
                x1_tensor = torch.tensor(x1_np, dtype=torch.float32).to(device)
                x2_tensor = torch.tensor(x2_np, dtype=torch.float32).to(device)
                x3_tensor = torch.tensor(x3_np, dtype=torch.float32).to(device)
                
                # 7. Eseguiamo il Forward pass del modello (Predizione al volo)
                with torch.no_grad():
                    logits = model(x1_tensor, x2_tensor, x3_tensor)
                    # Convertiamo i logits grezzi in probabilità (0.0 - 1.0) usando la Softmax
                    probabilities = F.softmax(logits, dim=1)
                    
                    # Troviamo l'indice della classe con probabilità maggiore
                    pred_idx = torch.argmax(probabilities, dim=1).item()
                    confidence = probabilities[0][pred_idx].item()
                
                # Mappiamo l'indice nel nome testuale dell'esercizio
                predicted_exercise = categories[pred_idx]
                
                # 8. Inviamo il responso finale in tempo reale a React
                response = {
                    "status": "predicted",
                    "frames_stacked": 8,
                    "exercise": predicted_exercise,
                    "confidence": round(confidence * 100, 2) # Percentuale pulita (es. 95.45)
                }
                await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        print("Client React disconnesso.")
    except Exception as e:
        print(f"Errore imprevisto nel loop WebSocket: {e}")