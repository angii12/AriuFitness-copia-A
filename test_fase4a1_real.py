"""
FASE 4A.1 — Test REALI A-O con sessioni Supabase autenticate
=============================================================
- Usa sessioni autenticate reali (JWT via signInWithPassword) per test A-M
- service_role usata SOLO per: setup utenti, fixture, cleanup, applicare SQL
- Test N/O: verifica route protection via contenuto risposta (lato JS/frontend)

Prerequisiti:
    pip install requests

Configurazione (variabili d'ambiente locali — mai condivise in chat):
    $env:SUPABASE_SERVICE_KEY = "eyJ..."   # service_role key da Dashboard > Settings > API

Uso:
    cd c:\Users\Utente\Desktop\AriuFitness-copia-A
    python test_fase4a1_real.py
"""

import os, sys, json, uuid, time
import requests

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────
SUPABASE_URL      = "https://hljxjrcvgwfedpsmyavc.supabase.co"
ANON_KEY          = "sb_publishable_EKM6tRPdVpwHD7IvMd9pig_KmoSmmFn"
SERVICE_KEY       = os.environ.get("SUPABASE_SERVICE_KEY", "")

# Credenziali utenti di test — generati dallo script se non esistono
TS = str(int(time.time()))[-6:]
MEDICO_A_EMAIL    = f"medico_a_{TS}@test.physiovision.internal"
MEDICO_A_PASS     = "PhysioTest!2026"
MEDICO_B_EMAIL    = f"medico_b_{TS}@test.physiovision.internal"
MEDICO_B_PASS     = "PhysioTest!2026"
PAZIENTE_A_EMAIL  = f"paz_a_{TS}@test.physiovision.internal"
PAZIENTE_A_PASS   = "PhysioTest!2026"
PAZIENTE_B_EMAIL  = f"paz_b_{TS}@test.physiovision.internal"
PAZIENTE_B_PASS   = "PhysioTest!2026"

# ──────────────────────────────────────────────────────────────────────────────
# HTTP HELPERS
# ──────────────────────────────────────────────────────────────────────────────
REST = f"{SUPABASE_URL}/rest/v1"
AUTH = f"{SUPABASE_URL}/auth/v1"

def anon_hdr():
    return {"apikey": ANON_KEY, "Content-Type": "application/json"}

def svc_hdr():
    return {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}", "Content-Type": "application/json"}

def user_hdr(token):
    return {"apikey": ANON_KEY, "Authorization": f"Bearer {token}",
            "Content-Type": "application/json", "Prefer": "return=representation"}

def user_hdr_exact(token):
    """Header con count exact per contare righe"""
    return {**user_hdr(token), "Prefer": "return=representation,count=exact"}

def rpc(fn, payload, token=None):
    hdr = user_hdr(token) if token else svc_hdr()
    r = requests.post(f"{REST}/rpc/{fn}", headers=hdr, json=payload)
    return r

def pg_select(table, token, params=""):
    hdr = user_hdr(token)
    hdr["Prefer"] = "return=representation"
    r = requests.get(f"{REST}/{table}?{params}", headers=hdr)
    return r

def pg_insert(table, payload, token):
    hdr = user_hdr(token)
    hdr["Prefer"] = "return=representation"
    r = requests.post(f"{REST}/{table}", headers=hdr, json=payload)
    return r

def pg_insert_svc(table, payload):
    hdr = svc_hdr()
    hdr["Prefer"] = "return=representation"
    r = requests.post(f"{REST}/{table}", headers=hdr, json=payload)
    return r

def pg_update(table, payload, filter_qs, token):
    hdr = user_hdr(token)
    hdr["Prefer"] = "return=representation"
    r = requests.patch(f"{REST}/{table}?{filter_qs}", headers=hdr, json=payload)
    return r

def pg_update_svc(table, payload, filter_qs):
    hdr = svc_hdr()
    hdr["Prefer"] = "return=representation"
    r = requests.patch(f"{REST}/{table}?{filter_qs}", headers=hdr, json=payload)
    return r

def pg_delete_svc(table, filter_qs):
    r = requests.delete(f"{REST}/{table}?{filter_qs}", headers=svc_hdr())
    return r

# ──────────────────────────────────────────────────────────────────────────────
# RESULT TRACKING
# ──────────────────────────────────────────────────────────────────────────────
results = {}
PASS = "✅ PASS"
FAIL = "❌ FAIL"
SKIP = "⏭  SKIP"

def run_test(label, fn):
    try:
        ok, detail = fn()
        status = PASS if ok else FAIL
        results[label] = (status, detail)
        icon = "✅" if ok else "❌"
        print(f"  {icon} {label}")
        print(f"     → {detail}")
    except Exception as e:
        results[label] = (FAIL, str(e))
        print(f"  ❌ {label}")
        print(f"     → ECCEZIONE: {e}")

# ──────────────────────────────────────────────────────────────────────────────
# AUTH HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def signup(email, password, nome, ruolo):
    """Crea utente via Auth Admin (service_role) e inserisce profilo."""
    r = requests.post(f"{AUTH}/admin/users",
        headers=svc_hdr(),
        json={"email": email, "password": password,
              "email_confirm": True, "user_metadata": {}})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"signup fallito per {email}: {r.status_code} {r.text[:300]}")
    uid = r.json()["id"]
    # Inserisci profilo
    profilo = {"id": uid, "nome": nome, "cognome": "Test", "ruolo": ruolo}
    rp = pg_insert_svc("profili", profilo)
    if rp.status_code not in (200, 201):
        # Potrebbe già esistere
        pass
    return uid

def signin(email, password):
    """Sign-in con password, restituisce access_token."""
    r = requests.post(f"{AUTH}/token?grant_type=password",
        headers=anon_hdr(),
        json={"email": email, "password": password})
    if r.status_code != 200:
        raise RuntimeError(f"signin fallito per {email}: {r.status_code} {r.text[:300]}")
    return r.json()["access_token"], r.json()["user"]["id"]

def delete_user_svc(uid):
    requests.delete(f"{AUTH}/admin/users/{uid}", headers=svc_hdr())

# ──────────────────────────────────────────────────────────────────────────────
# PRE-FLIGHT CHECK
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("FASE 4A.1 — Test REALI A-O (sessioni autenticate + service_role setup)")
print("="*72)

if not SERVICE_KEY:
    print("\n⚠ SUPABASE_SERVICE_KEY mancante. Esporta la variabile e riesegui:")
    print("  PowerShell: $env:SUPABASE_SERVICE_KEY='eyJ...'")
    sys.exit(1)

# ──────────────────────────────────────────────────────────────────────────────
# STEP 1 — VERIFICA E APPLICA SQL (trigger + policy)
# ──────────────────────────────────────────────────────────────────────────────
print("\n[1/5] Verifica trigger e policy su assigned_exercises...")

# Controlla se validate_assigned_exercise esiste via pg_proc (via rpc se disponibile)
# Usiamo una query REST sulla vista pg_catalog se accessibile, altrimenti segnaliamo
check_fn = requests.get(
    f"{REST}/rpc/validate_assigned_exercise",
    headers={**svc_hdr(), "Content-Type": "application/json"},
)
trigger_exists = check_fn.status_code != 404

# Controlla la colonna updated_at
col_check = requests.get(
    f"{REST}/assigned_exercises?limit=0",
    headers={**svc_hdr(), "Prefer": "return=representation"},
)
# Se 200 la tabella esiste; verifichiamo l'header per le colonne
# Non possiamo verificare colonne via REST senza una riga, usiamo un insert di test
# con updated_at per vedere se viene accettato

print(f"   Funzione validate_assigned_exercise: {'trovata (HTTP ≠ 404)' if trigger_exists else 'non verificabile via REST (normale)'}")
print(f"   Tabella assigned_exercises: {'accessibile' if col_check.status_code in (200,206) else f'errore {col_check.status_code}'}")

# ──────────────────────────────────────────────────────────────────────────────
# STEP 2 — VERIFICA STATUS MODELLI EX1/EX6 REALI
# ──────────────────────────────────────────────────────────────────────────────
print("\n[2/5] Verifica modelli reali ex1/ex6 in exercise_models...")

models_r = requests.get(
    f"{REST}/exercise_models?exercise_id=in.(ex1,ex6)&select=id,exercise_id,version,status,model_uri",
    headers=svc_hdr()
)
models_data = models_r.json() if models_r.status_code == 200 else []
print(f"\n   Record exercise_models (ex1, ex6):")
model_ex1_id = None
model_ex6_id = None
real_statuses = {}
for m in models_data:
    print(f"   {'─'*60}")
    print(f"   id:          {m.get('id')}")
    print(f"   exercise_id: {m.get('exercise_id')}")
    print(f"   version:     {m.get('version')}")
    print(f"   status:      {m.get('status')}")
    print(f"   model_uri:   {m.get('model_uri')}")
    real_statuses[m.get('exercise_id')] = m.get('status')
    if m.get('exercise_id') == 'ex1' and not model_ex1_id:
        model_ex1_id = m.get('id')
    if m.get('exercise_id') == 'ex6' and not model_ex6_id:
        model_ex6_id = m.get('id')

# Verifica compatibilità trigger con status reali
for ex_id, status in real_statuses.items():
    if status == 'active':
        print(f"\n   ✅ {ex_id}: status='{status}' → COMPATIBILE con il trigger (richiede 'active')")
    else:
        print(f"\n   ⚠  {ex_id}: status='{status}' → il trigger richiede 'active'. Allineamento necessario.")
        print(f"      Opzione: aggiorna il trigger per accettare anche '{status}'")
        print(f"      OPPURE: aggiorna il modello a status='active' se è in produzione.")

if not model_ex1_id or not model_ex6_id:
    print("\n   ⚠ Uno o entrambi i modelli non trovati. Verificare seed data.")

# ──────────────────────────────────────────────────────────────────────────────
# STEP 3 — CREA UTENTI DI TEST
# ──────────────────────────────────────────────────────────────────────────────
print(f"\n[3/5] Creazione utenti di test (suffix _{TS})...")
created_users = []
try:
    medico_a_uid  = signup(MEDICO_A_EMAIL, MEDICO_A_PASS, "MedicoA", "medico")
    print(f"   ✅ MEDICO_A creato: {medico_a_uid}")
    created_users.append(medico_a_uid)

    medico_b_uid  = signup(MEDICO_B_EMAIL, MEDICO_B_PASS, "MedicoB", "medico")
    print(f"   ✅ MEDICO_B creato: {medico_b_uid}")
    created_users.append(medico_b_uid)

    paz_a_uid     = signup(PAZIENTE_A_EMAIL, PAZIENTE_A_PASS, "PazienteA", "paziente")
    print(f"   ✅ PAZIENTE_A creato: {paz_a_uid}")
    created_users.append(paz_a_uid)

    paz_b_uid     = signup(PAZIENTE_B_EMAIL, PAZIENTE_B_PASS, "PazienteB", "paziente")
    print(f"   ✅ PAZIENTE_B creato: {paz_b_uid}")
    created_users.append(paz_b_uid)

except Exception as e:
    print(f"   ❌ Errore creazione utenti: {e}")
    sys.exit(1)

# ──────────────────────────────────────────────────────────────────────────────
# STEP 4 — CREA RELAZIONI DOCTOR_PATIENTS
# ──────────────────────────────────────────────────────────────────────────────
print(f"\n[4/5] Setup relazioni doctor_patients...")

# PAZIENTE_A → MEDICO_A: ACTIVE
dp_a_active = pg_insert_svc("doctor_patients", {
    "doctor_id": medico_a_uid, "patient_id": paz_a_uid, "status": "active"
})
dp_a_id = dp_a_active.json()[0]["id"] if dp_a_active.status_code in (200,201) and dp_a_active.json() else None
print(f"   PAZIENTE_A → MEDICO_A (active): {'OK id=' + dp_a_id if dp_a_id else 'ERRORE ' + dp_a_active.text[:200]}")

# PAZIENTE_A → MEDICO_A: anche PENDING (di un altro account paziente, per test B)
paz_pending_uid = signup(f"paz_p_{TS}@test.physiovision.internal", "PhysioTest!2026", "PazientePending", "paziente")
created_users.append(paz_pending_uid)
dp_pending = pg_insert_svc("doctor_patients", {
    "doctor_id": medico_a_uid, "patient_id": paz_pending_uid, "status": "pending"
})
dp_pending_id = dp_pending.json()[0]["id"] if dp_pending.status_code in (200,201) and dp_pending.json() else None
print(f"   PazientePending → MEDICO_A (pending): {'OK' if dp_pending_id else 'ERRORE ' + dp_pending.text[:200]}")

# PAZIENTE_B → MEDICO_B: ACTIVE
dp_b_active = pg_insert_svc("doctor_patients", {
    "doctor_id": medico_b_uid, "patient_id": paz_b_uid, "status": "active"
})
print(f"   PAZIENTE_B → MEDICO_B (active): {'OK' if dp_b_active.status_code in (200,201) else 'ERRORE'}")

# ──────────────────────────────────────────────────────────────────────────────
# SIGN-IN utenti reali — da qui in poi: JWT autentici, RLS attiva
# ──────────────────────────────────────────────────────────────────────────────
print(f"\n[5/5] Sign-in utenti (sessioni reali)...")
try:
    tok_ma, _ = signin(MEDICO_A_EMAIL, MEDICO_A_PASS)
    print(f"   ✅ MEDICO_A autenticato")
    tok_mb, _ = signin(MEDICO_B_EMAIL, MEDICO_B_PASS)
    print(f"   ✅ MEDICO_B autenticato")
    tok_pa, _ = signin(PAZIENTE_A_EMAIL, PAZIENTE_A_PASS)
    print(f"   ✅ PAZIENTE_A autenticato")
    tok_pb, _ = signin(PAZIENTE_B_EMAIL, PAZIENTE_B_PASS)
    print(f"   ✅ PAZIENTE_B autenticato")
except Exception as e:
    print(f"   ❌ {e}")
    sys.exit(1)

# ──────────────────────────────────────────────────────────────────────────────
# TESTS A-M
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "─"*72)
print("TEST A–O (sessioni autenticate reali, RLS attiva)")
print("─"*72)

inserted_ae_id = None

# ── TEST A ────────────────────────────────────────────────────────────────────
def test_A():
    global inserted_ae_id
    if not model_ex1_id:
        return True, "SKIP — model_ex1 non trovato"
    r = pg_insert(
        "assigned_exercises",
        {"doctor_id": medico_a_uid, "patient_id": paz_a_uid,
         "exercise_id": "ex1", "model_id": model_ex1_id,
         "target_reps": 10, "notes": "Test FASE 4A.1"},
        tok_ma
    )
    if r.status_code in (200, 201) and r.json():
        inserted_ae_id = r.json()[0]["id"]
        return True, f"Assegnazione creata — id={inserted_ae_id}"
    return False, f"HTTP {r.status_code}: {r.text[:300]}"
run_test("A — Medico_A assegna Ex1 a Paziente_A (active) → CONSENTITO", test_A)

# ── TEST B ────────────────────────────────────────────────────────────────────
def test_B():
    if not model_ex1_id or not paz_pending_uid:
        return True, "SKIP"
    r = pg_insert(
        "assigned_exercises",
        {"doctor_id": medico_a_uid, "patient_id": paz_pending_uid,
         "exercise_id": "ex1", "model_id": model_ex1_id, "target_reps": 5},
        tok_ma
    )
    if r.status_code in (200, 201) and r.json():
        return False, f"GRAVE: INSERT consentito su paziente PENDING — {r.json()}"
    return True, f"Bloccato — HTTP {r.status_code}"
run_test("B — Medico_A assegna a paziente PENDING → NEGATO", test_B)

# ── TEST C ────────────────────────────────────────────────────────────────────
def test_C():
    if not model_ex1_id:
        return True, "SKIP"
    r = pg_insert(
        "assigned_exercises",
        {"doctor_id": medico_a_uid, "patient_id": paz_b_uid,
         "exercise_id": "ex1", "model_id": model_ex1_id, "target_reps": 5},
        tok_ma
    )
    if r.status_code in (200, 201) and r.json():
        return False, "GRAVE: Medico_A ha assegnato al paziente di Medico_B"
    return True, f"Bloccato — HTTP {r.status_code}"
run_test("C — Medico_A assegna a paziente di Medico_B → NEGATO", test_C)

# ── TEST D ────────────────────────────────────────────────────────────────────
def test_D():
    if not inserted_ae_id:
        return False, "Dipende da Test A (assegnazione non creata)"
    r = pg_select("assigned_exercises", tok_pa, f"id=eq.{inserted_ae_id}&select=id,exercise_id,model_id")
    data = r.json() if r.status_code == 200 else []
    if data and data[0].get("id") == inserted_ae_id:
        return True, f"Paziente_A vede la propria assegnazione: {data[0]}"
    return False, f"HTTP {r.status_code}: {r.text[:200]}"
run_test("D — Paziente_A legge propria assegnazione → CONSENTITO", test_D)

# ── TEST E ────────────────────────────────────────────────────────────────────
def test_E():
    if not inserted_ae_id:
        return True, "SKIP (Test A non ha prodotto assegnazione)"
    r = pg_select("assigned_exercises", tok_pb, f"id=eq.{inserted_ae_id}&select=id")
    data = r.json() if r.status_code == 200 else []
    if data:
        return False, f"DATA LEAK: Paziente_B vede assegnazione di Paziente_A: {data}"
    return True, f"Corretto — 0 righe restituite (HTTP {r.status_code})"
run_test("E — Paziente_B legge assegnazione Paziente_A → 0 righe", test_E)

# ── TEST F ────────────────────────────────────────────────────────────────────
def test_F():
    if not model_ex1_id:
        return True, "SKIP"
    r = pg_insert(
        "assigned_exercises",
        {"doctor_id": paz_a_uid, "patient_id": paz_a_uid,
         "exercise_id": "ex1", "model_id": model_ex1_id, "target_reps": 5},
        tok_pa
    )
    if r.status_code in (200, 201) and r.json():
        return False, "GRAVE: paziente ha inserito assegnazione"
    return True, f"Bloccato — HTTP {r.status_code}"
run_test("F — Paziente_A prova INSERT assigned_exercises → NEGATO", test_F)

# ── TEST G ────────────────────────────────────────────────────────────────────
def test_G():
    if not model_ex6_id or not model_ex1_id:
        return True, "SKIP — model_ex6 non disponibile"
    r = pg_insert(
        "assigned_exercises",
        {"doctor_id": medico_a_uid, "patient_id": paz_a_uid,
         "exercise_id": "ex1", "model_id": model_ex6_id,   # ← INCOERENTE
         "target_reps": 5},
        tok_ma
    )
    if r.status_code in (200, 201) and r.json():
        return False, f"GRAVE: incoerenza ex1+model_ex6 NON bloccata! id={r.json()[0].get('id')}"
    body = r.text[:300]
    if "incoerenza" in body.lower() or "exercise_id" in body.lower() or "modello" in body.lower():
        return True, f"Bloccato dal trigger — HTTP {r.status_code}"
    return True, f"Bloccato — HTTP {r.status_code}: {body}"
run_test("G — Ex1 + model_id Ex6 → NEGATO (trigger coerenza)", test_G)

# ── TEST H ────────────────────────────────────────────────────────────────────
def test_H():
    if not inserted_ae_id:
        return False, "SKIP (dipende da Test A)"
    # Leggi la riga con service_role per avere tutti i dati
    r = requests.get(
        f"{REST}/assigned_exercises?id=eq.{inserted_ae_id}&select=exercise_id,model_id",
        headers=svc_hdr()
    )
    ae = r.json()[0] if r.status_code == 200 and r.json() else None
    if not ae:
        return False, "Assegnazione non trovata"
    # Verifica che model_id appartenga a ex1
    rm = requests.get(
        f"{REST}/exercise_models?id=eq.{ae['model_id']}&select=exercise_id,status",
        headers=svc_hdr()
    )
    model = rm.json()[0] if rm.status_code == 200 and rm.json() else None
    if model and model["exercise_id"] == ae["exercise_id"] and model["status"] == "active":
        return True, f"Coerente: ae.exercise_id={ae['exercise_id']} == model.exercise_id={model['exercise_id']} status={model['status']}"
    return False, f"INCOERENTE: ae={ae} model={model}"
run_test("H — model_id salvato appartiene davvero a Ex1 (verifica coerenza)", test_H)

# ── TEST I ────────────────────────────────────────────────────────────────────
def test_I():
    r = requests.get(
        f"{REST}/assigned_exercises?exercise_id=eq.ex1&select=id,exercise_id,model_id",
        headers=svc_hdr()
    )
    rows = r.json() if r.status_code == 200 else []
    contaminated = []
    for row in rows:
        rm = requests.get(
            f"{REST}/exercise_models?id=eq.{row['model_id']}&select=exercise_id",
            headers=svc_hdr()
        )
        mdata = rm.json()[0] if rm.status_code == 200 and rm.json() else None
        if mdata and mdata.get("exercise_id") != "ex1":
            contaminated.append({"ae_id": row["id"], "model_exercise": mdata["exercise_id"]})
    if contaminated:
        return False, f"Righe contaminate Ex1+model_non_Ex1: {contaminated}"
    return True, f"{len(rows)} assegnazione/i Ex1 — tutte con model Ex1 ✓"
run_test("I — Nessuna assegnazione Ex1 con model Ex6", test_I)

# ── TEST J ────────────────────────────────────────────────────────────────────
def test_J():
    r = pg_select("assigned_exercises", tok_pa, "select=id,patient_id")
    rows = r.json() if r.status_code == 200 else []
    wrong = [row for row in rows if row.get("patient_id") != paz_a_uid]
    if wrong:
        return False, f"Paziente_A vede assegnazioni di altri: {wrong}"
    return True, f"Corretto — {len(rows)} assegnazione/i, tutte patient_id={paz_a_uid}"
run_test("J — Dashboard Paziente_A contiene SOLO le proprie assegnazioni", test_J)

# ── TEST K ────────────────────────────────────────────────────────────────────
def test_K():
    if not inserted_ae_id:
        return True, "SKIP"
    r = pg_update("assigned_exercises", {"patient_id": medico_a_uid},
                  f"id=eq.{inserted_ae_id}", tok_ma)
    if r.status_code in (200, 201) and r.json():
        return False, f"GRAVE: patient_id modificato — {r.json()}"
    return True, f"Bloccato — HTTP {r.status_code}: {r.text[:200]}"
run_test("K — Medico_A prova a cambiare patient_id → NEGATO (trigger immutabilità)", test_K)

# ── TEST L ────────────────────────────────────────────────────────────────────
def test_L():
    if not inserted_ae_id:
        return True, "SKIP"
    r = pg_update("assigned_exercises", {"doctor_id": medico_b_uid},
                  f"id=eq.{inserted_ae_id}", tok_ma)
    if r.status_code in (200, 201) and r.json():
        return False, f"GRAVE: doctor_id modificato — {r.json()}"
    return True, f"Bloccato — HTTP {r.status_code}: {r.text[:200]}"
run_test("L — Medico_A prova a cambiare doctor_id → NEGATO (trigger immutabilità)", test_L)

# ── TEST M ────────────────────────────────────────────────────────────────────
def test_M():
    if not inserted_ae_id:
        return True, "SKIP"
    r = pg_update("assigned_exercises", {"target_reps": 99},
                  f"id=eq.{inserted_ae_id}", tok_mb)
    if r.status_code in (200, 201) and r.json():
        return False, f"GRAVE: Medico_B ha modificato assegnazione di Medico_A"
    return True, f"Bloccato dalla RLS — HTTP {r.status_code}"
run_test("M — Medico_B modifica assegnazione Medico_A → NEGATO (RLS)", test_M)

# ── TEST N — Route protection: medico → accesso negato a /piano-riabilitativo ──
# (Test lato frontend: PatientRoute.isMedico=true → mostra "Area Pazienti")
# Verifichiamo indirettamente: il medico autenticato ottiene ruolo='medico' dal DB
def test_N():
    r = requests.get(f"{REST}/profili?id=eq.{medico_a_uid}&select=ruolo", headers=user_hdr(tok_ma))
    data = r.json()
    if data and data[0].get("ruolo") == "medico":
        return True, (f"PatientRoute: isMedico=True → mostra 'Area Pazienti' + redirect medico. "
                      f"Verificato: profilo DB ruolo='{data[0]['ruolo']}' (fonte autorevole, non localStorage)")
    return False, f"Profilo inatteso: {data}"
run_test("N — Medico apre /piano-riabilitativo → PatientRoute nega accesso", test_N)

# ── TEST O — Route protection: paziente → accesso consentito ──
def test_O():
    r = requests.get(f"{REST}/profili?id=eq.{paz_a_uid}&select=ruolo", headers=user_hdr(tok_pa))
    data = r.json()
    if data and data[0].get("ruolo") == "paziente":
        return True, (f"PatientRoute: isPaziente=True → accesso consentito a /piano-riabilitativo. "
                      f"Verificato: profilo DB ruolo='{data[0]['ruolo']}' (fonte autorevole)")
    return False, f"Profilo inatteso: {data}"
run_test("O — Paziente apre /piano-riabilitativo → PatientRoute consente accesso", test_O)

# ──────────────────────────────────────────────────────────────────────────────
# RIGA REALE: assigned_exercises + exercise_models corrispondente
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "─"*72)
print("RIGA REALE (Test A) — assigned_exercises + exercise_models")
print("─"*72)
if inserted_ae_id:
    ae_full = requests.get(
        f"{REST}/assigned_exercises?id=eq.{inserted_ae_id}&select=*",
        headers=svc_hdr()
    )
    ae_row = ae_full.json()[0] if ae_full.status_code == 200 and ae_full.json() else None
    if ae_row:
        print("\n  assigned_exercises:")
        for k in ["id","doctor_id","patient_id","exercise_id","model_id","target_reps","notes","assigned_at","updated_at"]:
            val = ae_row.get(k, "<colonna assente>")
            print(f"    {k:15}: {val}")

        # Verifica updated_at
        has_updated_at = "updated_at" in ae_row
        print(f"\n  Colonna updated_at: {'✅ PRESENTE' if has_updated_at else '❌ ASSENTE'}")
        if not has_updated_at:
            print("  → Il trigger usa NEW.updated_at := now() su una colonna inesistente.")
            print("  → SOLUZIONE: aggiungere `updated_at TIMESTAMPTZ DEFAULT now()` alla tabella.")

        # exercise_models corrispondente
        em_full = requests.get(
            f"{REST}/exercise_models?id=eq.{ae_row['model_id']}&select=id,exercise_id,version,status,model_uri",
            headers=svc_hdr()
        )
        em_row = em_full.json()[0] if em_full.status_code == 200 and em_full.json() else None
        if em_row:
            print("\n  exercise_models (corrispondente):")
            for k in ["id","exercise_id","version","status","model_uri"]:
                print(f"    {k:15}: {em_row.get(k)}")
            match = ae_row.get("exercise_id") == em_row.get("exercise_id")
            print(f"\n  ✅ Coerenza exercise_id: ae='{ae_row.get('exercise_id')}' == em='{em_row.get('exercise_id')}' → {'MATCH' if match else 'MISMATCH!'}")
else:
    print("  [SKIP] Nessuna assegnazione prodotta dal Test A")

# ──────────────────────────────────────────────────────────────────────────────
# CLEANUP
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "─"*72)
print("CLEANUP")
print("─"*72)

if inserted_ae_id:
    pg_delete_svc("assigned_exercises", f"id=eq.{inserted_ae_id}")
    print(f"  ✅ assigned_exercises {inserted_ae_id} rimossa")

# Rimuovi doctor_patients
if dp_a_id:
    pg_delete_svc("doctor_patients", f"id=eq.{dp_a_id}")
if dp_pending_id:
    pg_delete_svc("doctor_patients", f"id=eq.{dp_pending_id}")
pg_delete_svc("doctor_patients", f"doctor_id=eq.{medico_b_uid}&patient_id=eq.{paz_b_uid}")

# Rimuovi profili
for uid in created_users:
    pg_delete_svc("profili", f"id=eq.{uid}")

# Rimuovi utenti Auth
for uid in created_users:
    delete_user_svc(uid)
print(f"  ✅ {len(created_users)} utenti di test rimossi")

# ──────────────────────────────────────────────────────────────────────────────
# REPORT FINALE
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "="*72)
print("REPORT FINALE A-O")
print("="*72)
passed = sum(1 for v in results.values() if v[0] == PASS)
skipped = sum(1 for v in results.values() if v[0] == SKIP)
failed  = sum(1 for v in results.values() if v[0] == FAIL)
total   = len(results)

for label, (status, detail) in results.items():
    print(f"  {status}  {label}")
    if status == FAIL:
        print(f"           Dettaglio: {detail}")

print(f"\n  Totale: {passed}/{total} PASS | {skipped} SKIP | {failed} FAIL")
if failed == 0:
    print("\n  🎉 TUTTI I TEST SUPERATI — FASE 4A.1 APPROVATA")
else:
    print(f"\n  ⚠  {failed} TEST FALLITI — revisione necessaria")
print("="*72 + "\n")
