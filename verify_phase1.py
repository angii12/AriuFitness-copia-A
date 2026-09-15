import sys
from pathlib import Path
import torch
import numpy as np

# Aggiunge src al PYTHONPATH
SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from services.model_registry import model_registry


def test_phase1():
    print("==================================================")
    print("VERIFICA FASE 1: REGISTRO MODELLI E SCHEMATIZZAZIONE")
    print("==================================================")

    # 1. Elenco dei modelli registrati nel sistema
    models = model_registry.get_registered_models()
    print(f"\n1. Modelli trovati nel registro locale ({len(models)}):")
    for m in models:
        print(f"   - Exercise ID: '{m['exercise_id']}'")
        print(f"     Path Modello: {m['model_uri']}")
        print(f"     Path Statistiche: {m['normalization_stats_uri']}")
        print(f"     Metriche F1: {m['metrics'].get('f1', 'N/A')}, Accuracy: {m['metrics'].get('accuracy', 'N/A')}")

    assert len(models) >= 2, "ERRORE: Modelli Ex1 ed Ex6 non trovati nel registro!"

    # 2. Caricamento ed esecuzione test inferenza per Ex1
    print("\n2. Test caricamento ed inferenza per 'ex1':")
    entry_ex1 = model_registry.load_model("ex1")
    assert entry_ex1 is not None, "ERRORE: Caricamento modello ex1 fallito!"

    # Dummy data: 8 frame, 36 keypoints, 8 angoli
    dummy_kp = np.random.randn(1, 8, 36).astype(np.float32)
    dummy_ang = np.random.randn(1, 8, 8).astype(np.float32)

    norm_kp, norm_ang = entry_ex1.normalize(dummy_kp, dummy_ang)
    assert norm_kp.shape == (1, 8, 36), "Shape keypoints normalizzata errata!"
    assert norm_ang.shape == (1, 8, 8), "Shape angoli normalizzata errata!"

    t_kp = torch.tensor(norm_kp, dtype=torch.float32)
    t_ang = torch.tensor(norm_ang, dtype=torch.float32)

    conf_ex1 = entry_ex1.predict_confidence(t_kp, t_ang)
    print(f"   [OK] Ex1 caricato con successo. Confidenza su dummy input: {conf_ex1}%")
    
    # 3. Caricamento ed esecuzione test inferenza per Ex6
    print("\n3. Test caricamento ed inferenza per 'ex6':")
    entry_ex6 = model_registry.load_model("ex6")
    assert entry_ex6 is not None, "ERRORE: Caricamento modello ex6 fallito!"

    norm_kp6, norm_ang6 = entry_ex6.normalize(dummy_kp, dummy_ang)
    t_kp6 = torch.tensor(norm_kp6, dtype=torch.float32)
    t_ang6 = torch.tensor(norm_ang6, dtype=torch.float32)

    conf_ex6 = entry_ex6.predict_confidence(t_kp6, t_ang6)
    print(f"   [OK] Ex6 caricato con successo. Confidenza su dummy input: {conf_ex6}%")

    # 4. Verifica dello schema Supabase SQL
    schema_file = Path(__file__).resolve().parent / "supabase_schema.sql"
    assert schema_file.exists(), "ERRORE: supabase_schema.sql non trovato!"
    sql_text = schema_file.read_text(encoding="utf-8")
    
    required_entities = [
        "profili",
        "esercizi",
        "exercise_models",
        "exercise_profiles",
        "doctor_patients",
        "assigned_exercises"
    ]
    print("\n4. Verifica entità nello schema Supabase SQL:")
    for entity in required_entities:
        assert f"public.{entity}" in sql_text or f"TABLE IF NOT EXISTS {entity}" in sql_text or f"TABLE IF NOT EXISTS public.{entity}" in sql_text or entity in sql_text, f"Entità {entity} mancante nello schema SQL!"
        print(f"   [OK] Tabella '{entity}' presente nello schema SQL.")

    print("\n==================================================")
    print("[SUCCESS] RISULTATO: VERIFICA FASE 1 COMPLETATA CON SUCCESSO!")
    print("==================================================")


if __name__ == "__main__":
    test_phase1()
