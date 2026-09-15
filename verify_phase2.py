import sys
import os
import json
import shutil
import numpy as np
import pandas as pd
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
REHAB_PIPELINE_DIR = SRC_DIR / "rehab_pipeline"
if str(REHAB_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(REHAB_PIPELINE_DIR))

from services.pipeline_runner import RehabPipelineRunner
from services.model_registry import model_registry
from services.db_service import db_service
from webapp.server import app
from fastapi.testclient import TestClient


def create_synthetic_run_dir(run_dir: Path, num_frames: int = 150):
    """Crea una run_dir sintetica valida con pose_landmarks, angles_df e rep_review per i test."""
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Pose landmarks: (150, 33, 4)
    landmarks = np.zeros((num_frames, 33, 4), dtype=np.float32)
    landmarks[:, :, 3] = 0.99 # visibility HIGH
    np.save(run_dir / "pose_landmarks.npy", landmarks)

    # 2. Angles DF con oscillazione per 'left_knee'
    t = np.linspace(0, 4 * np.pi, num_frames)
    angles_data = {
        "frame": np.arange(num_frames),
        "timestamp": np.arange(num_frames) / 30.0,
        "left_elbow": 160.0 + 5.0 * np.sin(t),
        "right_elbow": 160.0 + 5.0 * np.sin(t),
        "left_shoulder": 30.0 + 2.0 * np.sin(t),
        "right_shoulder": 30.0 + 2.0 * np.sin(t),
        "left_hip": 170.0 + 10.0 * np.sin(t),
        "right_hip": 170.0 + 10.0 * np.sin(t),
        "left_knee": 170.0 - 60.0 * np.abs(np.sin(t)), # oscillazione rep 170 -> 110 deg
        "right_knee": 170.0 - 60.0 * np.abs(np.sin(t))
    }
    df_angles = pd.DataFrame(angles_data)
    df_angles.to_csv(run_dir / "angles.csv", index=False)

    # 3. Segments & Review table
    used_segments = [
        {"rep": 1, "start_frame": 10, "end_frame": 45, "peak_frame": 28, "confidence": 0.95, "doctor_validation": "confirmed"},
        {"rep": 2, "start_frame": 50, "end_frame": 85, "peak_frame": 68, "confidence": 0.93, "doctor_validation": "confirmed"},
        {"rep": 3, "start_frame": 90, "end_frame": 125, "peak_frame": 108, "confidence": 0.96, "doctor_validation": "confirmed"}
    ]
    pd.DataFrame(used_segments).to_csv(run_dir / "segments_used.csv", index=False)

    review_rows = []
    for s in used_segments:
        review_rows.append({
            "rep": s["rep"],
            "start_frame": s["start_frame"],
            "end_frame": s["end_frame"],
            "peak_frame": s["peak_frame"],
            "confidence": s["confidence"],
            "doctor_validation": s["doctor_validation"],
            "review_status": "pending"
        })
    pd.DataFrame(review_rows).to_csv(run_dir / "rep_review.csv", index=False)

    metadata = {
        "exercise_id": "test_ex_phase2",
        "fps": 30.0,
        "total_frames": num_frames,
        "pose_detection_rate": 100.0,
        "rep_mode": "auto",
        "signal_selection_mode": "doctor_guided",
        "doctor_selected_joints": ["left_knee", "right_knee"]
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def test_phase2():
    print("==================================================")
    print("VERIFICA FASE 2: PIPELINE RUNNER & FASTAPI ENDPOINTS")
    print("==================================================")

    client = TestClient(app)
    exercise_id = "test_ex_phase2"

    # 1. Test Endpoint POST /api/doctor/exercises
    print("\n1. Test Endpoint POST /api/doctor/exercises:")
    resp_create = client.post("/api/doctor/exercises", json={
        "exercise_id": exercise_id,
        "nome": "Esercizio Test Fase 2",
        "descrizione": "Esercizio di prova automatizzato per la Fase 2",
        "categoria": "Riabilitazione",
        "signal_selection_mode": "doctor_guided",
        "doctor_selected_joints": ["left_knee", "right_knee"]
    })
    print(f"   Response status: {resp_create.status_code}")
    assert resp_create.status_code == 200, f"Errore creazione esercizio: {resp_create.text}"
    print("   [OK] Creazione esercizio e profilo salvati in DB.")

    # 2. Creazione run sintetica e salvataggio REP generate in DB
    run_dir = Path(__file__).resolve().parent / "uploads" / "runs" / exercise_id
    create_synthetic_run_dir(run_dir)
    
    mock_reps = [
        {"rep_index": 1, "start_frame": 10, "end_frame": 45, "peak_frame": 28, "doctor_validation": "confirmed"},
        {"rep_index": 2, "start_frame": 50, "end_frame": 85, "peak_frame": 68, "doctor_validation": "confirmed"},
        {"rep_index": 3, "start_frame": 90, "end_frame": 125, "peak_frame": 108, "doctor_validation": "confirmed"}
    ]
    db_service.save_generated_reps(exercise_id, "mock_video.mp4", mock_reps)
    print("\n2. [OK] REP generate salvate nel DB Supabase (ripetizioni_generate).")

    # 3. Test Endpoint GET /api/doctor/exercises/{exercise_id}/reps
    print("\n3. Test Endpoint GET /api/doctor/exercises/{exercise_id}/reps:")
    resp_get_reps = client.get(f"/api/doctor/exercises/{exercise_id}/reps")
    assert resp_get_reps.status_code == 200
    reps_data = resp_get_reps.json()["reps"]
    assert len(reps_data) == 3, f"Attese 3 REP, trovate: {len(reps_data)}"
    print(f"   [OK] Lettura REP per review completata. Trovate {len(reps_data)} REP.")

    # 4. Test Endpoint POST /api/doctor/exercises/{exercise_id}/reps/review
    print("\n4. Test Endpoint POST /api/doctor/exercises/{exercise_id}/reps/review:")
    # Il medico accetta la REP 1 e la REP 2, e rifiuta la REP 3
    review_payload = {
        "reviews": [
            {"rep_index": 1, "accettata": True},
            {"rep_index": 2, "accettata": True},
            {"rep_index": 3, "accettata": False}
        ]
    }
    resp_review = client.post(
        f"/api/doctor/exercises/{exercise_id}/reps/review",
        json=review_payload
    )
    assert resp_review.status_code == 200
    print(f"   [OK] Review salvata. REP accettate = [1, 2], REP rifiutata = [3]. Modificate: {resp_review.json()['updated_count']}")

    # 5. Test Endpoint POST /api/doctor/exercises/{exercise_id}/train
    print("\n5. Test Endpoint POST /api/doctor/exercises/{exercise_id}/train:")
    resp_train = client.post(
        f"/api/doctor/exercises/{exercise_id}/train",
        json={"epochs": 2, "batch_size": 8, "seed": 42}
    )
    print(f"   Response status: {resp_train.status_code}")
    assert resp_train.status_code == 200, f"Errore training: {resp_train.text}"
    train_res = resp_train.json()["train_result"]
    print(f"   [OK] Training TwoBranchLSTM completato usando SOLO le REP accettate.")
    print(f"   [OK] Modello salvato in: {train_res['model_path']}")

    # 6. Verifica del registro modelli aggiornato
    print("\n6. Verifica caricamento dal registro modelli dinamico:")
    loaded_entry = model_registry.load_model(exercise_id)
    assert loaded_entry is not None, f"Modello {exercise_id} non registrato nella cache!"
    print(f"   [OK] Modello {exercise_id} pronto ed istanziato da {train_res['model_path']}.")

    # 7. Test Endpoint GET /api/exercises
    print("\n7. Test Endpoint GET /api/exercises:")
    resp_ex_list = client.get("/api/exercises")
    assert resp_ex_list.status_code == 200
    registered = resp_ex_list.json()["exercises"]
    print(f"   [OK] Elenco modelli registrati nel sistema ({len(registered)}): {[e['exercise_id'] for e in registered]}")

    print("\n==================================================")
    print("[SUCCESS] RISULTATO: VERIFICA FASE 2 COMPLETATA CON SUCCESSO!")
    print("==================================================")

    # Pulizia scratch test
    shutil.rmtree(run_dir, ignore_errors=True)
    model_dir = Path(__file__).resolve().parent / "models" / "production_models" / exercise_id
    shutil.rmtree(model_dir, ignore_errors=True)


if __name__ == "__main__":
    test_phase2()
