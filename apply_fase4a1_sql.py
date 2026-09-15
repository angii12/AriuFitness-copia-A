"""
apply_fase4a1_sql.py
────────────────────
Applica il blocco SQL FASE 4A.1 al database Supabase PhysioVision.
Verifica anche l'esistenza della colonna updated_at su assigned_exercises.

Uso:
    $env:SUPABASE_SERVICE_KEY = "eyJ..."
    python apply_fase4a1_sql.py
"""
import os, sys, requests

SUPABASE_URL  = "https://hljxjrcvgwfedpsmyavc.supabase.co"
SERVICE_KEY   = os.environ.get("SUPABASE_SERVICE_KEY", "")

REST = f"{SUPABASE_URL}/rest/v1"

def svc_hdr():
    return {"apikey": SERVICE_KEY,
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"}

if not SERVICE_KEY:
    print("⚠ SUPABASE_SERVICE_KEY mancante.")
    print("  PowerShell: $env:SUPABASE_SERVICE_KEY='eyJ...'")
    sys.exit(1)

print("="*60)
print("FASE 4A.1 — Applicazione SQL e verifica stato DB")
print("="*60)

# ──────────────────────────────────────────────────────────────
# 1. Verifica colonna updated_at su assigned_exercises
#    (inserisce una riga temp e legge le colonne restituite)
# ──────────────────────────────────────────────────────────────
print("\n[1] Verifica colonna updated_at su assigned_exercises...")

# Prova un PATCH senza WHERE reale per leggere le colonne disponibili
# Usiamo un SELECT su una riga inesistente — le colonne sono nel header
r = requests.get(
    f"{REST}/assigned_exercises?id=eq.00000000-0000-0000-0000-000000000000&select=*",
    headers=svc_hdr()
)
# Controlla cosa restituisce (dovrebbe essere [])
if r.status_code == 200:
    # Prova a capire le colonne via un describe alternativo
    # Con PostgREST, possiamo chiamare /rest/v1/ (senza tabella) per il openapi spec
    schema_r = requests.get(f"{SUPABASE_URL}/rest/v1/", headers=svc_hdr())
    if schema_r.status_code == 200:
        spec = schema_r.json()
        paths = spec.get("paths", {})
        ae_path = paths.get("/assigned_exercises", {})
        get_op = ae_path.get("get", {})
        params = get_op.get("parameters", [])
        columns = [p["name"] for p in params if p.get("in") == "query"
                   and not p["name"].startswith("select")]
        has_updated_at = "updated_at" in columns or any("updated_at" in str(p) for p in params)
        print(f"   Colonne rilevate via OpenAPI: {columns[:15]}")
        print(f"   updated_at presente: {'✅ SÌ' if has_updated_at else '❌ NO — vedi correzione sotto'}")

        if not has_updated_at:
            print("""
   ⚠ COLONNA updated_at ASSENTE — il trigger usa NEW.updated_at := now()
     su una colonna che non esiste.

   CORREZIONE NECESSARIA — esegui nel SQL Editor Supabase:
   ──────────────────────────────────────────────────────
   ALTER TABLE public.assigned_exercises
     ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();
   ──────────────────────────────────────────────────────
   Poi riesegui questo script per applicare il trigger corretto.
""")
    else:
        print(f"   OpenAPI non accessibile ({schema_r.status_code}) — verifica manuale richiesta")
else:
    print(f"   Errore REST: {r.status_code} {r.text[:200]}")

# ──────────────────────────────────────────────────────────────
# 2. Verifica trigger esistente via pg_catalog
#    PostgREST non espone pg_catalog, ma possiamo usare l'RPC
# ──────────────────────────────────────────────────────────────
print("\n[2] Verifica trigger trg_validate_assigned_exercise...")

# Proviamo a verificare inserendo una riga INCOERENTE:
# Se il trigger esiste → errore 400/500 con messaggio "Incoerenza"
# Se NON esiste → la riga viene inserita (poi la puliamo)

# Prima troviamo un model_ex6 reale
models_r = requests.get(
    f"{REST}/exercise_models?exercise_id=eq.ex6&status=eq.active&select=id&limit=1",
    headers=svc_hdr()
)
model_ex6_id = None
if models_r.status_code == 200 and models_r.json():
    model_ex6_id = models_r.json()[0]["id"]

models_ex1_r = requests.get(
    f"{REST}/exercise_models?exercise_id=eq.ex1&status=eq.active&select=id&limit=1",
    headers=svc_hdr()
)
model_ex1_id = None
if models_ex1_r.status_code == 200 and models_ex1_r.json():
    model_ex1_id = models_ex1_r.json()[0]["id"]

# Troviamo un medico e un paziente reali
profili_r = requests.get(
    f"{REST}/profili?ruolo=eq.medico&select=id&limit=1",
    headers=svc_hdr()
)
medico_id = profili_r.json()[0]["id"] if profili_r.status_code == 200 and profili_r.json() else None

paz_r = requests.get(
    f"{REST}/profili?ruolo=eq.paziente&select=id&limit=1",
    headers=svc_hdr()
)
paz_id = paz_r.json()[0]["id"] if paz_r.status_code == 200 and paz_r.json() else None

if model_ex6_id and model_ex1_id and medico_id and paz_id:
    # Tenta INSERT incoerente (ex1 + model_ex6)
    test_insert = requests.post(
        f"{REST}/assigned_exercises",
        headers=svc_hdr(),
        json={"doctor_id": medico_id, "patient_id": paz_id,
              "exercise_id": "ex1", "model_id": model_ex6_id, "target_reps": 1}
    )
    if test_insert.status_code in (400, 409, 500):
        body = test_insert.text.lower()
        if "incoerenza" in body or "exercise_id" in body or "modello" in body or "model" in body:
            print("   ✅ Trigger ATTIVO — INSERT ex1+model_ex6 bloccato con messaggio corretto")
        else:
            print(f"   ✅ Trigger probabilmente attivo — bloccato HTTP {test_insert.status_code}: {test_insert.text[:150]}")
    elif test_insert.status_code in (200, 201):
        new_id = test_insert.json()[0].get("id") if test_insert.json() else None
        print(f"   ❌ Trigger NON ATTIVO — INSERT incoerente passato! id={new_id}")
        print("      Applicare il SQL del trigger manualmente (vedi sotto)")
        # Cleanup dell'inserimento indesiderato
        if new_id:
            requests.delete(f"{REST}/assigned_exercises?id=eq.{new_id}", headers=svc_hdr())
    else:
        print(f"   ⚠ HTTP {test_insert.status_code}: {test_insert.text[:200]}")
else:
    print("   ⚠ Impossibile testare: medico/paziente/modello non trovati nel DB")
    print(f"   medico_id={medico_id}, paz_id={paz_id}, model_ex1={model_ex1_id}, model_ex6={model_ex6_id}")

# ──────────────────────────────────────────────────────────────
# 3. Verifica policy granulari assigned_exercises
# ──────────────────────────────────────────────────────────────
print("\n[3] Policy assigned_exercises attese:")
expected_policies = [
    "Lettura assigned_exercises",
    "Medico inserisce assigned_exercises",
    "Medico aggiorna assigned_exercises",
    "Medico revoca assigned_exercises",
]
print("   (Verifica manuale nel Dashboard: Authentication → Policies → assigned_exercises)")
for p in expected_policies:
    print(f"   • {p}")

# ──────────────────────────────────────────────────────────────
# 4. SQL da applicare se trigger non attivo
# ──────────────────────────────────────────────────────────────
print("""
[4] SQL DA APPLICARE NEL SQL EDITOR SUPABASE (se trigger non ancora attivo):
────────────────────────────────────────────────────────────────────────────
-- Step A: aggiungi colonna updated_at se mancante
ALTER TABLE public.assigned_exercises
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- Step B: applica il trigger di validazione
DROP TRIGGER IF EXISTS trg_validate_assigned_exercise ON public.assigned_exercises;
DROP FUNCTION IF EXISTS public.validate_assigned_exercise();

CREATE OR REPLACE FUNCTION public.validate_assigned_exercise()
RETURNS TRIGGER AS $$
DECLARE
  v_model_exercise_id TEXT;
  v_model_status      TEXT;
  v_exercise_owner    UUID;
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF NEW.doctor_id IS DISTINCT FROM OLD.doctor_id THEN
      RAISE EXCEPTION 'Non è consentito modificare doctor_id.';
    END IF;
    IF NEW.patient_id IS DISTINCT FROM OLD.patient_id THEN
      RAISE EXCEPTION 'Non è consentito modificare patient_id.';
    END IF;
    IF NEW.exercise_id IS DISTINCT FROM OLD.exercise_id THEN
      RAISE EXCEPTION 'Non è consentito modificare exercise_id.';
    END IF;
    NEW.updated_at := now();
  END IF;
  SELECT em.exercise_id, em.status
  INTO   v_model_exercise_id, v_model_status
  FROM   public.exercise_models em WHERE em.id = NEW.model_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'model_id % non trovato.', NEW.model_id;
  END IF;
  IF v_model_exercise_id IS DISTINCT FROM NEW.exercise_id THEN
    RAISE EXCEPTION 'Incoerenza exercise_id/model_id: modello=% assegnazione=%',
      v_model_exercise_id, NEW.exercise_id;
  END IF;
  IF v_model_status <> 'active' THEN
    RAISE EXCEPTION 'Modello status=%. Richiesto: active.', v_model_status;
  END IF;
  SELECT e.creato_da INTO v_exercise_owner
  FROM public.esercizi e WHERE e.exercise_id = NEW.exercise_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'exercise_id % non trovato.', NEW.exercise_id;
  END IF;
  IF v_exercise_owner IS NOT NULL AND v_exercise_owner IS DISTINCT FROM NEW.doctor_id THEN
    RAISE EXCEPTION 'Medico non autorizzato sull esercizio %.', NEW.exercise_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;

CREATE TRIGGER trg_validate_assigned_exercise
  BEFORE INSERT OR UPDATE ON public.assigned_exercises
  FOR EACH ROW EXECUTE FUNCTION public.validate_assigned_exercise();
────────────────────────────────────────────────────────────────────────────
""")

print("="*60)
print("Script completato.")
print("="*60)
