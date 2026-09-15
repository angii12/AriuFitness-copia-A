import sys
import os
import json
import numpy as np
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fastapi.testclient import TestClient
from webapp.server import app
from services.db_service import db_service

def setup_synthetic_video_run(exercise_id: str, video_name: str, num_frames: int = 120):
    """Crea la struttura di run per un video specifico con dati di posa ed angoli per testare la review."""
    video_stem = Path(video_name).stem
    run_dir = PROJECT_ROOT / "uploads" / "runs" / exercise_id / video_stem
    run_dir.mkdir(parents=True, exist_ok=True)

    # 1. Landmarks
    landmarks = np.zeros((num_frames, 33, 4), dtype=np.float32)
    landmarks[:, :, 3] = 0.99
    np.save(run_dir / "pose_landmarks.npy", landmarks)

    # 2. Angles
    t = np.linspace(0, 4 * np.pi, num_frames)
    angles_data = {
        "frame": np.arange(num_frames),
        "timestamp": np.arange(num_frames) / 30.0,
        "left_elbow": 160.0 + 5.0 * np.sin(t),
        "right_elbow": 160.0 + 5.0 * np.sin(t),
        "left_shoulder": 30.0 + 30.0 * np.sin(t),
        "right_shoulder": 30.0 + 30.0 * np.sin(t),
        "left_hip": 170.0 + 5.0 * np.sin(t),
        "right_hip": 170.0 + 5.0 * np.sin(t),
        "left_knee": 170.0 + 5.0 * np.sin(t),
        "right_knee": 170.0 + 5.0 * np.sin(t)
    }
    pd.DataFrame(angles_data).to_csv(run_dir / "angles.csv", index=False)

    # 3. Segments
    used_segments = [
        {"rep": 1, "start_frame": 10, "end_frame": 50, "peak_frame": 30, "confidence": 0.95, "doctor_validation": "confirmed"},
        {"rep": 2, "start_frame": 60, "end_frame": 100, "peak_frame": 80, "confidence": 0.92, "doctor_validation": "confirmed"}
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

    # 4. Salva REP anche nel DB Supabase/locale
    reps_formatted = []
    for idx, seg in enumerate(used_segments, start=1):
        reps_formatted.append({
            "video_source": video_name,
            "rep_index": idx,
            "start_frame": seg["start_frame"],
            "end_frame": seg["end_frame"],
            "peak_frame": seg["peak_frame"],
            "doctor_validation": seg["doctor_validation"]
        })

    saved = db_service.save_generated_reps(exercise_id, video_name, reps_formatted)
    return saved

def test_phase3_doctor_flow():
    print("==================================================")
    print("TEST COLLAUDO FASE 3.1: PORTALE MEDICO END-TO-END")
    print("==================================================")

    test_ex_id = "ex_test_doctor_phase3"
    video_1_name = "video_dimostrativo_spalle_1.mp4"
    video_2_name = "video_dimostrativo_spalle_2.mp4"

    with TestClient(app) as client:
        # 1. Creazione Esercizio in modalita' DOCTOR_GUIDED con 4 articolazioni selezionate
        payload_create = {
            "exercise_id": test_ex_id,
            "nome": "Test Spalle e Gomiti Clinico",
            "descrizione": "Esercizio di test clinico con doctor_selected_joints",
            "categoria": "Riabilitazione",
            "signal_selection_mode": "doctor_guided",
            "doctor_selected_joints": ["left_shoulder", "right_shoulder", "left_elbow", "right_elbow"],
            "expected_reps": None
        }

        print("\n1. Invio payload creazione esercizio al backend...")
        print(f"Payload inviato:\n{json.dumps(payload_create, indent=2)}")

        res_create = client.post("/api/doctor/exercises", json=payload_create)
        assert res_create.status_code == 200, f"Errore creazione esercizio: {res_create.text}"
        print("[OK] Esercizio e profilo salvati in DB.")

        # 2. Configurazione multi-video per 2 video distinti
        print("\n2. Simulazione upload e segmentazione per 2 video distinti...")
        reps_v1 = setup_synthetic_video_run(test_ex_id, video_1_name)
        reps_v2 = setup_synthetic_video_run(test_ex_id, video_2_name)
        print(f"[OK] Video 1 ({video_1_name}): registrate {len(reps_v1)} REP.")
        print(f"[OK] Video 2 ({video_2_name}): registrate {len(reps_v2)} REP.")

        # 3. Lettura delle REP totali generate dal DB per la review
        print("\n3. Lettura REP generate dal DB per la review medico...")
        res_reps = client.get(f"/api/doctor/exercises/{test_ex_id}/reps")
        assert res_reps.status_code == 200
        all_reps = res_reps.json()["reps"]
        print(f"[OK] Trovate in totale {len(all_reps)} REP salvate per l'esercizio '{test_ex_id}'.")

        # Verifica univocita' video_source
        video_sources = list(set(r["video_source"] for r in all_reps))
        print(f"[OK] Fonti video rilevate nelle REP: {video_sources}")
        assert set(video_sources) == {video_1_name, video_2_name}, "Manca il riferimento video_source distinto"

        # 4. Invio Review Medico (Accetta prima REP, Rifiuta seconda REP)
        print("\n4. Invio review medico su Supabase / DB...")
        reviews_payload = []
        for idx, r in enumerate(all_reps):
            # Accetta le rep del primo video, rifiuta quelle del secondo per verificare il cambio di stato
            reviews_payload.append({
                "id": r.get("id"),
                "video_source": r.get("video_source"),
                "rep_index": r["rep_index"],
                "accettata": (r.get("video_source") == video_1_name)
            })

        res_review = client.post(
            f"/api/doctor/exercises/{test_ex_id}/reps/review",
            json={"reviews": reviews_payload}
        )
        assert res_review.status_code == 200
        print(f"[OK] Review salvata su DB. Updated count: {res_review.json()['updated_count']}")

        # 5. Verifica cambio stato nel DB
        reps_after_review = db_service.get_generated_reps(test_ex_id)
        accepted_in_db = [r for r in reps_after_review if r.get("accettata_medico") is True]
        rejected_in_db = [r for r in reps_after_review if r.get("accettata_medico") is False]
        print(f"[VERIFICA DB] REP accettate nel DB: {len(accepted_in_db)}, REP rifiutate nel DB: {len(rejected_in_db)}")
        assert len(accepted_in_db) == len(reps_v1), "Il conteggio delle REP accettate nel DB non corrisponde"
        assert len(rejected_in_db) == len(reps_v2), "Il conteggio delle REP rifiutate nel DB non corrisponde"

        # 6. Pulizia finale dell'esercizio di test
        print("\n5. Pulizia record ed artefatti di test...")
        if db_service.client:
            db_service.client.table("esercizi").delete().eq("exercise_id", test_ex_id).execute()
        else:
            db_service._local_esercizi.pop(test_ex_id, None)
            db_service._local_profiles.pop(test_ex_id, None)
            db_service._local_reps.pop(test_ex_id, None)

        test_run_folder = PROJECT_ROOT / "uploads" / "runs" / test_ex_id
        if test_run_folder.exists():
            import shutil
            shutil.rmtree(test_run_folder, ignore_errors=True)

    print("\n==================================================")
    print("[SUCCESS] COLLAUDO FASE 3.1 COMPLETATO CON SUCCESSO!")
    print("==================================================")

if __name__ == "__main__":
    test_phase3_doctor_flow()
