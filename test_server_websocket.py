import sys
import json
import base64
import numpy as np
import cv2
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastapi.testclient import TestClient
from webapp.server import app

def test_server_and_websocket():
    print("=== TEST SERVER FASTAPI & WEBSOCKET LIVE STREAM ===")
    
    # 1. Verifica Endpoints REST FastAPI
    client = TestClient(app)
    
    # Test GET /api/exercises
    res_ex = client.get("/api/exercises")
    assert res_ex.status_code == 200, f"Errore GET /api/exercises: {res_ex.status_code}"
    exercises_data = res_ex.json()["exercises"]
    model_ids = [m["exercise_id"] for m in exercises_data]
    print(f"[OK] GET /api/exercises ha restituito {len(model_ids)} modelli attivi: {model_ids}")
    assert set(model_ids) == {"ex1", "ex6"}, f"Inatteso elenco modelli: {model_ids}"
    
    # 2. Verifica Connessione e Protocollo WebSocket /ws/stream
    print("\nConnessione al WebSocket /ws/stream...")
    with client.websocket_connect("/ws/stream") as websocket:
        print("[OK] WebSocket connessione stabilita.")
        
        # Selezione esercizio reale "ex1" -> Caricamento modello ex1 ed elaborazione frame
        websocket.send_json({"selected_exercise": "ex1", "llm_enabled": False})
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        _, buffer = cv2.imencode('.jpg', dummy_frame)
        base64_frame = base64.b64encode(buffer).decode('utf-8')
        
        websocket.send_json({"image": base64_frame})
        resp_ex1 = json.loads(websocket.receive_text())
        print(f"[OK] Risposta WebSocket (ex1 stream) ricevuta:\n     {json.dumps(resp_ex1, indent=2)}")
        assert "status" in resp_ex1

    print("\n==================================================")
    print("[SUCCESS] VERIFICA SERVER & WEBSOCKET COMPLETATA CON SUCCESSO!")
    print("==================================================")

if __name__ == "__main__":
    test_server_and_websocket()
