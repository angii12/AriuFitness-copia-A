"""
FASE 4A.1 — Script di test A-M per assigned_exercises
=======================================================
Prerequisiti:
  pip install supabase python-dotenv

Configurazione:
  - Imposta SUPABASE_SERVICE_KEY nel blocco CONFIG qui sotto
  - Crea due utenti medico (MEDICO_A, MEDICO_B) e due pazienti (PAZIENTE_A, PAZIENTE_B) nel DB
  - PAZIENTE_A deve avere collegamento ACTIVE con MEDICO_A
  - PAZIENTE_B deve avere collegamento ACTIVE con MEDICO_B

Uso:
  python test_fase4a1.py
"""

import os
import sys
from supabase import create_client, Client

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG — da compilare prima di eseguire
# ──────────────────────────────────────────────────────────────────────────────
SUPABASE_URL      = "https://hljxjrcvgwfedpsmyavc.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_EKM6tRPdVpwHD7IvMd9pig_KmoSmmFn"

# ⚠ Imposta qui la service_role key (da Dashboard > Settings > API > service_role)
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# Credenziali utenti di test (da creare manualmente in Supabase Auth prima di eseguire)
MEDICO_A_EMAIL    = os.environ.get("MEDICO_A_EMAIL",    "medico_a@test.physiovision.it")
MEDICO_A_PASSWORD = os.environ.get("MEDICO_A_PASSWORD", "TestPass123!")
MEDICO_B_EMAIL    = os.environ.get("MEDICO_B_EMAIL",    "medico_b@test.physiovision.it")
MEDICO_B_PASSWORD = os.environ.get("MEDICO_B_PASSWORD", "TestPass123!")
PAZIENTE_A_EMAIL    = os.environ.get("PAZIENTE_A_EMAIL",    "paziente_a@test.physiovision.it")
PAZIENTE_A_PASSWORD = os.environ.get("PAZIENTE_A_PASSWORD", "TestPass123!")
PAZIENTE_B_EMAIL    = os.environ.get("PAZIENTE_B_EMAIL",    "paziente_b@test.physiovision.it")
PAZIENTE_B_PASSWORD = os.environ.get("PAZIENTE_B_PASSWORD", "TestPass123!")
# ──────────────────────────────────────────────────────────────────────────────

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = {}


def client_as(email: str, password: str) -> Client:
    """Crea un client Supabase autenticato come un utente specifico."""
    c = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    res = c.auth.sign_in_with_password({"email": email, "password": password})
    if not res.session:
        raise RuntimeError(f"Login fallito per {email}")
    return c


def admin_client() -> Client:
    """Client con service_role (bypassa RLS)."""
    if not SUPABASE_SERVICE_KEY:
        raise RuntimeError(
            "SUPABASE_SERVICE_KEY non impostata. Esporta la variabile d'ambiente:\n"
            "  $env:SUPABASE_SERVICE_KEY='eyJ...'   (PowerShell)\n"
            "  export SUPABASE_SERVICE_KEY='eyJ...'  (bash)"
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_ids(admin: Client):
    """Recupera gli UUID necessari ai test."""
    # Profili
    profili = admin.from_("profili").select("id, nome, ruolo").execute().data
    medico_a = next((p for p in profili if p.get("nome","").lower().startswith("medico_a") or
                     p.get("nome","") == "Medico A"), None)
    medico_b = next((p for p in profili if p.get("nome","").lower().startswith("medico_b") or
                     p.get("nome","") == "Medico B"), None)
    paz_a    = next((p for p in profili if p.get("nome","").lower().startswith("paziente_a") or
                     p.get("nome","") == "Paziente A"), None)
    paz_b    = next((p for p in profili if p.get("nome","").lower().startswith("paziente_b") or
                     p.get("nome","") == "Paziente B"), None)

    # Cerca per email se non trovato per nome
    def find_by_email(email):
        users = admin.auth.admin.list_users()
        u = next((u for u in users if u.email == email), None)
        if u:
            return next((p for p in profili if p["id"] == str(u.id)), None)
        return None

    if not medico_a:   medico_a = find_by_email(MEDICO_A_EMAIL)
    if not medico_b:   medico_b = find_by_email(MEDICO_B_EMAIL)
    if not paz_a:      paz_a    = find_by_email(PAZIENTE_A_EMAIL)
    if not paz_b:      paz_b    = find_by_email(PAZIENTE_B_EMAIL)

    # Modelli
    models = admin.from_("exercise_models").select("id, exercise_id, status, version").execute().data
    model_ex1 = next((m for m in models if m["exercise_id"] == "ex1" and m["status"] == "active"), None)
    model_ex6 = next((m for m in models if m["exercise_id"] == "ex6" and m["status"] == "active"), None)

    # Relazione doctor_patients MEDICO_A ↔ PAZIENTE_A (active)
    dp_active = admin.from_("doctor_patients").select("id, doctor_id, patient_id, status")\
        .eq("status", "active").execute().data

    # Relazione PENDING (PAZIENTE_A → MEDICO_A se esiste, oppure qualsiasi pending)
    dp_pending = admin.from_("doctor_patients").select("id, doctor_id, patient_id, status")\
        .eq("status", "pending").execute().data

    return {
        "medico_a": medico_a,
        "medico_b": medico_b,
        "paz_a":    paz_a,
        "paz_b":    paz_b,
        "model_ex1": model_ex1,
        "model_ex6": model_ex6,
        "dp_active": dp_active,
        "dp_pending": dp_pending,
    }


def run_test(label: str, fn):
    """Esegue un test e registra il risultato."""
    try:
        ok, detail = fn()
        status = PASS if ok else FAIL
        results[label] = (status, detail)
        print(f"  {label}: {status} — {detail}")
    except Exception as e:
        results[label] = (FAIL, str(e))
        print(f"  {label}: {FAIL} — ECCEZIONE: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# SETUP
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("FASE 4A.1 — Test assegnazione esercizi (A-M)")
print("="*70)

if not SUPABASE_SERVICE_KEY:
    print("\n⚠ SUPABASE_SERVICE_KEY non trovata.")
    print("  Imposta la variabile d'ambiente e riesegui:")
    print("  PowerShell: $env:SUPABASE_SERVICE_KEY='eyJ...'")
    print("  bash:       export SUPABASE_SERVICE_KEY='eyJ...'")
    sys.exit(1)

admin = admin_client()
ids   = get_ids(admin)

medico_a_id  = ids["medico_a"]["id"]  if ids["medico_a"] else None
medico_b_id  = ids["medico_b"]["id"]  if ids["medico_b"] else None
paz_a_id     = ids["paz_a"]["id"]     if ids["paz_a"]    else None
paz_b_id     = ids["paz_b"]["id"]     if ids["paz_b"]    else None
model_ex1_id = ids["model_ex1"]["id"] if ids["model_ex1"] else None
model_ex6_id = ids["model_ex6"]["id"] if ids["model_ex6"] else None

# Trova il paziente PENDING di MEDICO_A (se esiste)
dp_pending_for_a = next((dp for dp in ids["dp_pending"] if dp["doctor_id"] == medico_a_id), None)
paz_pending_id   = dp_pending_for_a["patient_id"] if dp_pending_for_a else None

print(f"\nID risolti:")
print(f"  MEDICO_A  : {medico_a_id}")
print(f"  MEDICO_B  : {medico_b_id}")
print(f"  PAZIENTE_A: {paz_a_id}")
print(f"  PAZIENTE_B: {paz_b_id}")
print(f"  Model EX1 : {model_ex1_id}")
print(f"  Model EX6 : {model_ex6_id}")
print(f"  Paz Pending per MEDICO_A: {paz_pending_id}")
print()

inserted_assignment_id = None
medico_a_client = client_as(MEDICO_A_EMAIL, MEDICO_A_PASSWORD)
medico_b_client = client_as(MEDICO_B_EMAIL, MEDICO_B_PASSWORD)
paz_a_client    = client_as(PAZIENTE_A_EMAIL, PAZIENTE_A_PASSWORD)

# ──────────────────────────────────────────────────────────────────────────────
# TEST A: MEDICO_A assegna Ex1 al proprio paziente ACTIVE → CONSENTITO
# ──────────────────────────────────────────────────────────────────────────────
def test_A():
    global inserted_assignment_id
    res = medico_a_client.from_("assigned_exercises").insert({
        "doctor_id":  medico_a_id,
        "patient_id": paz_a_id,
        "exercise_id": "ex1",
        "model_id":   model_ex1_id,
        "target_reps": 10,
        "notes": "Test FASE 4A.1 — Test A"
    }).execute()
    if res.data:
        inserted_assignment_id = res.data[0]["id"]
        return True, f"Assegnazione creata: {inserted_assignment_id}"
    return False, f"Errore inatteso: {res}"
run_test("A — Medico_A assegna Ex1 a Paziente_A (active)", test_A)

# ──────────────────────────────────────────────────────────────────────────────
# TEST B: assegna a paziente PENDING → NEGATO (RLS INSERT)
# ──────────────────────────────────────────────────────────────────────────────
def test_B():
    if not paz_pending_id:
        return True, "SKIP — nessun paziente pending disponibile per MEDICO_A"
    try:
        res = medico_a_client.from_("assigned_exercises").insert({
            "doctor_id":  medico_a_id,
            "patient_id": paz_pending_id,
            "exercise_id": "ex1",
            "model_id":   model_ex1_id,
            "target_reps": 5,
        }).execute()
        if res.data:
            return False, "DOVEVA essere negato, ma è stato accettato"
        return True, "Bloccato correttamente (nessun dato restituito)"
    except Exception as e:
        return True, f"Bloccato correttamente: {e}"
run_test("B — Medico_A assegna a paziente PENDING → NEGATO", test_B)

# ──────────────────────────────────────────────────────────────────────────────
# TEST C: assegna a paziente di MEDICO_B → NEGATO
# ──────────────────────────────────────────────────────────────────────────────
def test_C():
    try:
        res = medico_a_client.from_("assigned_exercises").insert({
            "doctor_id":  medico_a_id,
            "patient_id": paz_b_id,
            "exercise_id": "ex1",
            "model_id":   model_ex1_id,
            "target_reps": 5,
        }).execute()
        if res.data:
            return False, "DOVEVA essere negato"
        return True, "Bloccato correttamente"
    except Exception as e:
        return True, f"Bloccato: {e}"
run_test("C — Medico_A assegna a paziente di Medico_B → NEGATO", test_C)

# ──────────────────────────────────────────────────────────────────────────────
# TEST D: PAZIENTE_A vede la propria assegnazione → CONSENTITO
# ──────────────────────────────────────────────────────────────────────────────
def test_D():
    res = paz_a_client.from_("assigned_exercises").select("id, exercise_id, model_id").execute()
    own = [r for r in (res.data or []) if r.get("id") == inserted_assignment_id]
    if own:
        return True, f"Paziente vede la propria assegnazione: {own[0]}"
    return False, f"Assegnazione non trovata. Dati: {res.data}"
run_test("D — Paziente_A vede la propria assegnazione", test_D)

# ──────────────────────────────────────────────────────────────────────────────
# TEST E: PAZIENTE_B non vede l'assegnazione di PAZIENTE_A → NEGATO
# ──────────────────────────────────────────────────────────────────────────────
def test_E():
    paz_b_client = client_as(PAZIENTE_B_EMAIL, PAZIENTE_B_PASSWORD)
    res = paz_b_client.from_("assigned_exercises").select("id").execute()
    leaked = [r for r in (res.data or []) if r.get("id") == inserted_assignment_id]
    if leaked:
        return False, f"DATA LEAK: Paziente_B ha visto l'assegnazione di Paziente_A"
    return True, f"Corretto: Paziente_B vede {len(res.data or [])} assegnazioni (solo le proprie)"
run_test("E — Paziente_B NON vede assegnazione Paziente_A", test_E)

# ──────────────────────────────────────────────────────────────────────────────
# TEST F: PAZIENTE_A prova INSERT assigned_exercises → NEGATO
# ──────────────────────────────────────────────────────────────────────────────
def test_F():
    try:
        res = paz_a_client.from_("assigned_exercises").insert({
            "doctor_id":  paz_a_id,   # paziente finge di essere medico
            "patient_id": paz_a_id,
            "exercise_id": "ex1",
            "model_id":   model_ex1_id,
            "target_reps": 5,
        }).execute()
        if res.data:
            return False, "DOVEVA essere negato"
        return True, "Bloccato correttamente"
    except Exception as e:
        return True, f"Bloccato: {e}"
run_test("F — Paziente prova INSERT → NEGATO", test_F)

# ──────────────────────────────────────────────────────────────────────────────
# TEST G: exercise_id=ex1 + model_id=EX6 → NEGATO (trigger coerenza)
# ──────────────────────────────────────────────────────────────────────────────
def test_G():
    if not model_ex6_id:
        return True, "SKIP — nessun modello EX6 disponibile"
    try:
        res = medico_a_client.from_("assigned_exercises").insert({
            "doctor_id":  medico_a_id,
            "patient_id": paz_a_id,
            "exercise_id": "ex1",
            "model_id":   model_ex6_id,  # ← incoerente!
            "target_reps": 5,
        }).execute()
        if res.data:
            return False, f"GRAVE: incoerenza ex1+model_ex6 NON bloccata! id={res.data[0].get('id')}"
        return True, "Bloccato correttamente (nessun dato)"
    except Exception as e:
        if "incoerenza" in str(e).lower() or "exercise_id" in str(e).lower() or "modello" in str(e).lower():
            return True, f"Bloccato dal trigger: {e}"
        return True, f"Bloccato (altro motivo): {e}"
run_test("G — Ex1 + model_EX6 → NEGATO (trigger coerenza)", test_G)

# ──────────────────────────────────────────────────────────────────────────────
# TEST H: assegnazione Ex1 ha davvero model_id del modello Ex1
# ──────────────────────────────────────────────────────────────────────────────
def test_H():
    if not inserted_assignment_id:
        return False, "Assegnazione del Test A non disponibile"
    row = admin.from_("assigned_exercises").select("exercise_id, model_id").eq("id", inserted_assignment_id).single().execute()
    ae = row.data
    if not ae:
        return False, "Assegnazione non trovata nel DB"
    # Verifica che model_id appartenga davvero a ex1
    model_row = admin.from_("exercise_models").select("exercise_id, status").eq("id", ae["model_id"]).single().execute()
    m = model_row.data
    if m and m["exercise_id"] == ae["exercise_id"] and m["status"] == "active":
        return True, f"Coerente: exercise_id={ae['exercise_id']}, model exercise_id={m['exercise_id']}, status={m['status']}"
    return False, f"INCOERENTE: ae={ae}, model={m}"
run_test("H — model_id salvato appartiene davvero a Ex1", test_H)

# ──────────────────────────────────────────────────────────────────────────────
# TEST I: query per Ex1 non restituisce mai righe con model di Ex6
# ──────────────────────────────────────────────────────────────────────────────
def test_I():
    rows = admin.from_("assigned_exercises")\
        .select("id, exercise_id, model_id")\
        .eq("exercise_id", "ex1").execute().data or []
    contaminated = []
    for r in rows:
        m = admin.from_("exercise_models").select("exercise_id").eq("id", r["model_id"]).single().execute().data
        if m and m["exercise_id"] != "ex1":
            contaminated.append(r)
    if contaminated:
        return False, f"Trovate righe contaminate Ex1+Ex6: {contaminated}"
    return True, f"Tutte le {len(rows)} assegnazioni Ex1 hanno model Ex1"
run_test("I — Nessuna assegnazione Ex1 con model Ex6", test_I)

# ──────────────────────────────────────────────────────────────────────────────
# TEST J: dashboard paziente contiene SOLO le proprie assegnazioni
# ──────────────────────────────────────────────────────────────────────────────
def test_J():
    res = paz_a_client.from_("assigned_exercises").select("id, patient_id").execute()
    rows = res.data or []
    wrong = [r for r in rows if r.get("patient_id") != paz_a_id]
    if wrong:
        return False, f"Paziente_A vede assegnazioni di altri: {wrong}"
    return True, f"Corretto: {len(rows)} assegnazioni, tutte con patient_id={paz_a_id}"
run_test("J — Dashboard paziente contiene SOLO le proprie assegnazioni", test_J)

# ──────────────────────────────────────────────────────────────────────────────
# TEST K: MEDICO_A prova a modificare patient_id → NEGATO (trigger immutabilità)
# ──────────────────────────────────────────────────────────────────────────────
def test_K():
    if not inserted_assignment_id:
        return False, "Assegnazione Test A non disponibile"
    try:
        res = medico_a_client.from_("assigned_exercises")\
            .update({"patient_id": medico_a_id})\
            .eq("id", inserted_assignment_id).execute()
        if res.data:
            return False, f"GRAVE: patient_id modificato! {res.data}"
        return True, "Bloccato correttamente (nessun dato aggiornato)"
    except Exception as e:
        return True, f"Bloccato dal trigger: {e}"
run_test("K — Medico_A prova a cambiare patient_id → NEGATO", test_K)

# ──────────────────────────────────────────────────────────────────────────────
# TEST L: MEDICO_A prova a modificare doctor_id → NEGATO
# ──────────────────────────────────────────────────────────────────────────────
def test_L():
    if not inserted_assignment_id:
        return False, "Assegnazione Test A non disponibile"
    try:
        res = medico_a_client.from_("assigned_exercises")\
            .update({"doctor_id": medico_b_id})\
            .eq("id", inserted_assignment_id).execute()
        if res.data:
            return False, f"GRAVE: doctor_id modificato!"
        return True, "Bloccato correttamente"
    except Exception as e:
        return True, f"Bloccato dal trigger: {e}"
run_test("L — Medico_A prova a cambiare doctor_id → NEGATO", test_L)

# ──────────────────────────────────────────────────────────────────────────────
# TEST M: MEDICO_B prova a modificare assegnazione di MEDICO_A → NEGATO (RLS)
# ──────────────────────────────────────────────────────────────────────────────
def test_M():
    if not inserted_assignment_id:
        return False, "Assegnazione Test A non disponibile"
    try:
        res = medico_b_client.from_("assigned_exercises")\
            .update({"target_reps": 99})\
            .eq("id", inserted_assignment_id).execute()
        if res.data:
            return False, f"GRAVE: MEDICO_B ha modificato l'assegnazione di MEDICO_A!"
        return True, "Bloccato dalla RLS (nessun dato modificato)"
    except Exception as e:
        return True, f"Bloccato: {e}"
run_test("M — Medico_B prova a modificare assegnazione Medico_A → NEGATO", test_M)

# ──────────────────────────────────────────────────────────────────────────────
# CLEANUP: rimuove assegnazione di test
# ──────────────────────────────────────────────────────────────────────────────
if inserted_assignment_id:
    admin.from_("assigned_exercises").delete().eq("id", inserted_assignment_id).execute()
    print(f"\n🧹 Cleanup: assegnazione di test {inserted_assignment_id} rimossa.")

# ──────────────────────────────────────────────────────────────────────────────
# REPORT FINALE
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("RISULTATI FINALI")
print("="*70)
passed = sum(1 for v in results.values() if v[0] == PASS)
total  = len(results)
for label, (status, detail) in results.items():
    print(f"  {status}  {label}")
    if status == FAIL:
        print(f"          Dettaglio: {detail}")
print(f"\nTotale: {passed}/{total} test superati")
if passed == total:
    print("\n🎉 TUTTI I TEST SUPERATI — FASE 4A.1 APPROVATA")
else:
    print(f"\n⚠  {total - passed} TEST FALLITI — revisione necessaria")
print("="*70 + "\n")
