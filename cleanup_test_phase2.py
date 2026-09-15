import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from services.db_service import db_service
from services.model_registry import model_registry

def clean_test_artifacts():
    print("=== PULIZIA ARTEFATTI DI TEST: test_ex_phase2 ===")
    test_id = "test_ex_phase2"

    # 1. Pulizia Supabase Database
    if db_service.client:
        try:
            res = db_service.client.table("esercizi").delete().eq("exercise_id", test_id).execute()
            print(f"[OK] Record DB eliminati da Supabase per {test_id}: {res.data}")
        except Exception as e:
            print(f"[WARNING] Errore durante l'eliminazione da Supabase: {e}")
    else:
        print("[INFO] Client Supabase non connesso. Pulizia cache locale DB.")
        db_service._local_esercizi.pop(test_id, None)
        db_service._local_profiles.pop(test_id, None)
        db_service._local_reps.pop(test_id, None)
        db_service._local_models.pop(test_id, None)

    # 2. Rimozione cartella modello di produzione
    prod_model_dir = PROJECT_ROOT / "models" / "production_models" / test_id
    if prod_model_dir.exists():
        shutil.rmtree(prod_model_dir, ignore_errors=True)
        print(f"[OK] Cartella modello rimossa: {prod_model_dir}")

    # 3. Rimozione cartelle temporanee di run e video
    run_dir = PROJECT_ROOT / "uploads" / "runs" / test_id
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)
        print(f"[OK] Cartella run rimossa: {run_dir}")

    video_dir = PROJECT_ROOT / "uploads" / "videos" / test_id
    if video_dir.exists():
        shutil.rmtree(video_dir, ignore_errors=True)
        print(f"[OK] Cartella video rimossa: {video_dir}")

    # 4. Ricarica Registro Modelli
    active_models = model_registry.get_registered_models()
    model_ids = [m["exercise_id"] for m in active_models]
    print(f"\n[VERIFICA] Modelli reali attualmente attivi nel registro ({len(model_ids)}): {model_ids}")

    if set(model_ids) == {"ex1", "ex6"}:
        print("[SUCCESS] Pulizia completata con successo! Soltanto Ex1 ed Ex6 rimangono attivi.")
    else:
        print(f"[WARNING] Attenzione: elenco modelli attivi inatteso: {model_ids}")

if __name__ == "__main__":
    clean_test_artifacts()
