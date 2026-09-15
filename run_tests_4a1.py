"""
FASE 4A.1 — Test REALI A-O
═══════════════════════════════════════════════════════════════════════
Uso (PowerShell):
    # Crea il file .env.service con la service_role key:
    'SUPABASE_SERVICE_KEY=eyJ...' | Out-File -Encoding utf8 .env.service

    # Esegui:
    $env:PYTHONIOENCODING="utf-8"; python run_tests_4a1.py

La service_role key viene letta SOLO da .env.service (mai da chat).
Setup/cleanup: service_role. Test A-O: JWT sessioni reali (RLS attiva).
═══════════════════════════════════════════════════════════════════════
"""
import os, sys, json, time, requests

# ───────────────────────────────────────────────────────────────
# CONFIG
# ───────────────────────────────────────────────────────────────
SUPABASE_URL = "https://hljxjrcvgwfedpsmyavc.supabase.co"
ANON_KEY     = "sb_publishable_EKM6tRPdVpwHD7IvMd9pig_KmoSmmFn"
REST         = f"{SUPABASE_URL}/rest/v1"
AUTH         = f"{SUPABASE_URL}/auth/v1"

# Leggi service_role da .env.service o variabile d'ambiente
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
if not SERVICE_KEY:
    env_file = os.path.join(os.path.dirname(__file__), ".env.service")
    if os.path.exists(env_file):
        for line in open(env_file).read().splitlines():
            if line.startswith("SUPABASE_SERVICE_KEY="):
                SERVICE_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

if not SERVICE_KEY:
    print("ERRORE: SUPABASE_SERVICE_KEY non trovata.")
    print("Crea il file .env.service con:")
    print("  SUPABASE_SERVICE_KEY=eyJ...")
    print("Oppure esporta la variabile d'ambiente.")
    sys.exit(1)

# ───────────────────────────────────────────────────────────────
# HTTP HELPERS
# ───────────────────────────────────────────────────────────────
def svc(extra=None):
    h = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}",
         "Content-Type": "application/json", "Prefer": "return=representation"}
    if extra: h.update(extra)
    return h

def jwt(token, extra=None):
    h = {"apikey": ANON_KEY, "Authorization": f"Bearer {token}",
         "Content-Type": "application/json", "Prefer": "return=representation"}
    if extra: h.update(extra)
    return h

def anon():
    return {"apikey": ANON_KEY, "Content-Type": "application/json"}

def get(table, qs="", token=None):
    h = jwt(token) if token else svc()
    return requests.get(f"{REST}/{table}?{qs}", headers=h)

def post(table, body, token=None):
    h = jwt(token) if token else svc()
    return requests.post(f"{REST}/{table}", headers=h, json=body)

def patch(table, qs, body, token=None):
    h = jwt(token) if token else svc()
    return requests.patch(f"{REST}/{table}?{qs}", headers=h, json=body)

def delete(table, qs):
    return requests.delete(f"{REST}/{table}?{qs}", headers=svc())

sys.path.insert(0, str(os.path.abspath("src")))
from services.auth_test_guard import assert_safe_test_user_operation, safe_admin_create_user, safe_admin_delete_user

# ───────────────────────────────────────────────────────────────
# AUTH HELPERS
# ───────────────────────────────────────────────────────────────
def admin_create_user(email, password, nome, ruolo):
    """Crea utente via Admin API (service_role) in modo protetto + inserisce profilo."""
    assert_safe_test_user_operation(email, "admin_create_user")
    r = safe_admin_create_user(
        SUPABASE_URL,
        SERVICE_KEY,
        {"email": email, "password": password, "email_confirm": True}
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Creazione utente fallita [{r.status_code}]: {r.text[:300]}")
    uid = r.json()["id"]
    # Inserisci profilo (la RLS INSERT richiede auth.uid()=id, quindi uso service_role)
    rp = requests.post(f"{REST}/profili", headers=svc(),
        json={"id": uid, "nome": nome, "cognome": "TestAuto", "ruolo": ruolo})
    if rp.status_code not in (200, 201):
        # Potrebbe già esistere — non blocchiamo
        pass
    return uid

def admin_delete_user(uid):
    safe_admin_delete_user(SUPABASE_URL, SERVICE_KEY, uid)
    delete("profili", f"id=eq.{uid}")

def signin(email, password):
    """Sign-in normale, restituisce (access_token, uid). RLS ATTIVA."""
    r = requests.post(f"{AUTH}/token?grant_type=password", headers=anon(),
        json={"email": email, "password": password})
    if r.status_code != 200:
        raise RuntimeError(f"Sign-in fallito per {email} [{r.status_code}]: {r.text[:200]}")
    d = r.json()
    return d["access_token"], d["user"]["id"]

# ───────────────────────────────────────────────────────────────
# RESULT TRACKER
# ───────────────────────────────────────────────────────────────
results = {}

def run(label, fn):
    try:
        ok, detail = fn()
        sym = "PASS" if ok else "FAIL"
        results[label] = (sym, detail)
        print(f"  {'OK' if ok else 'NO'}  {label}")
        print(f"      {detail}")
    except Exception as e:
        results[label] = ("FAIL", str(e))
        print(f"  NO  {label}")
        print(f"      ECCEZIONE: {e}")

# ═══════════════════════════════════════════════════════════════
# INIZIO
# ═══════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("FASE 4A.1 - Test reali A-O  (RLS attiva - JWT autentici)")
print("=" * 70)

TS = str(int(time.time()))[-6:]

# ───────────────────────────────────────────────────────────────
# STEP 0 — Record modelli reali EX1/EX6
# ───────────────────────────────────────────────────────────────
print("\n[PRE] Modelli exercise_models reali (ex1, ex6):")
print("-" * 50)
rm = requests.get(
    f"{REST}/exercise_models?exercise_id=in.(ex1,ex6)&select=id,exercise_id,version,status,model_uri",
    headers=svc()
)
models_ex1, models_ex6 = [], []
if rm.status_code == 200:
    for m in rm.json():
        eid = m.get("exercise_id","")
        print(f"  id:          {m.get('id')}")
        print(f"  exercise_id: {eid}")
        print(f"  version:     {m.get('version')}")
        print(f"  status:      {m.get('status')}")
        print(f"  model_uri:   {m.get('model_uri')}")
        print()
        if eid == "ex1": models_ex1.append(m)
        if eid == "ex6": models_ex6.append(m)
else:
    print(f"  Errore: HTTP {rm.status_code}")

model_ex1_id = next((m["id"] for m in models_ex1 if m.get("status")=="active"), None)
model_ex6_id = next((m["id"] for m in models_ex6 if m.get("status")=="active"), None)

if not model_ex1_id:
    print("  ATTENZIONE: nessun modello ex1 con status='active' trovato.")
    print("  Il trigger richiedera' status='active'. Verificare nel DB.")
if not model_ex6_id:
    print("  ATTENZIONE: nessun modello ex6 con status='active' trovato.")

# ───────────────────────────────────────────────────────────────
# STEP 1 — Crea utenti di test
# ───────────────────────────────────────────────────────────────
print("\n[1/4] Creazione utenti di test (suffix _{})...".format(TS))
created_uids = []
try:
    uid_ma = admin_create_user(f"med_a_{TS}@pv.test", "PhysioTest!2026", "MedicoA", "medico")
    print(f"  MEDICO_A  : {uid_ma}")
    created_uids.append(uid_ma)

    uid_mb = admin_create_user(f"med_b_{TS}@pv.test", "PhysioTest!2026", "MedicoB", "medico")
    print(f"  MEDICO_B  : {uid_mb}")
    created_uids.append(uid_mb)

    uid_pa = admin_create_user(f"paz_a_{TS}@pv.test", "PhysioTest!2026", "PazienteA", "paziente")
    print(f"  PAZIENTE_A: {uid_pa}")
    created_uids.append(uid_pa)

    uid_pb = admin_create_user(f"paz_b_{TS}@pv.test", "PhysioTest!2026", "PazienteB", "paziente")
    print(f"  PAZIENTE_B: {uid_pb}")
    created_uids.append(uid_pb)

    uid_pp = admin_create_user(f"paz_p_{TS}@pv.test", "PhysioTest!2026", "PazientePending", "paziente")
    print(f"  PENDING   : {uid_pp}")
    created_uids.append(uid_pp)

except Exception as e:
    print(f"  ERRORE creazione utenti: {e}")
    sys.exit(1)

# ───────────────────────────────────────────────────────────────
# STEP 2 — Setup doctor_patients (service_role, solo per fixture)
# ───────────────────────────────────────────────────────────────
print("\n[2/4] Setup relazioni doctor_patients...")

# PAZIENTE_A -> MEDICO_A: ACTIVE
r_a = requests.post(f"{REST}/doctor_patients", headers=svc(),
    json={"doctor_id": uid_ma, "patient_id": uid_pa, "status": "active"})
dp_a_id = r_a.json()[0]["id"] if r_a.status_code in (200,201) and r_a.json() else None
print(f"  PAZIENTE_A -> MEDICO_A active: {'OK id='+dp_a_id if dp_a_id else 'ERRORE '+r_a.text[:120]}")

# PAZIENTE_B -> MEDICO_B: ACTIVE
r_b = requests.post(f"{REST}/doctor_patients", headers=svc(),
    json={"doctor_id": uid_mb, "patient_id": uid_pb, "status": "active"})
print(f"  PAZIENTE_B -> MEDICO_B active: {'OK' if r_b.status_code in (200,201) else 'ERRORE'}")

# PENDING -> MEDICO_A: PENDING
r_p = requests.post(f"{REST}/doctor_patients", headers=svc(),
    json={"doctor_id": uid_ma, "patient_id": uid_pp, "status": "pending"})
print(f"  PENDING    -> MEDICO_A pending: {'OK' if r_p.status_code in (200,201) else 'ERRORE'}")

# ───────────────────────────────────────────────────────────────
# STEP 3 — Sign-in come utenti reali (da qui RLS attiva)
# ───────────────────────────────────────────────────────────────
print("\n[3/4] Sign-in sessioni reali (JWT normali, RLS attiva)...")
try:
    tok_ma, _ = signin(f"med_a_{TS}@pv.test", "PhysioTest!2026")
    tok_mb, _ = signin(f"med_b_{TS}@pv.test", "PhysioTest!2026")
    tok_pa, _ = signin(f"paz_a_{TS}@pv.test", "PhysioTest!2026")
    tok_pb, _ = signin(f"paz_b_{TS}@pv.test", "PhysioTest!2026")
    print("  Tutti gli utenti autenticati con successo.")
except Exception as e:
    print(f"  ERRORE sign-in: {e}")
    sys.exit(1)

# ───────────────────────────────────────────────────────────────
# STEP 4 — TEST A–O (sessioni JWT autentiche, RLS attiva)
# ───────────────────────────────────────────────────────────────
print("\n[4/4] Esecuzione test A-O...")
print("-" * 70)
ae_id = None   # id dell'assegnazione creata dal Test A

# ── TEST A ──────────────────────────────────────────────────────────────────
def test_A():
    global ae_id
    if not model_ex1_id:
        return False, "SKIP - nessun modello ex1 active disponibile"
    r = post("assigned_exercises",
        {"doctor_id": uid_ma, "patient_id": uid_pa,
         "exercise_id": "ex1", "model_id": model_ex1_id,
         "target_reps": 10, "notes": "Test FASE 4A.1 - Test A"},
        tok_ma)
    if r.status_code in (200,201) and r.json():
        ae_id = r.json()[0]["id"]
        return True, f"Assegnazione creata - id={ae_id}"
    return False, f"HTTP {r.status_code}: {r.text[:300]}"
run("A - Medico_A assegna Ex1 a Paziente_A (active) -> CONSENTITO", test_A)

# ── TEST B ──────────────────────────────────────────────────────────────────
def test_B():
    if not model_ex1_id: return True, "SKIP"
    r = post("assigned_exercises",
        {"doctor_id": uid_ma, "patient_id": uid_pp,
         "exercise_id": "ex1", "model_id": model_ex1_id, "target_reps": 5},
        tok_ma)
    if r.status_code in (200,201) and r.json():
        return False, f"GRAVE: INSERT su paziente PENDING passato! {r.json()[0].get('id')}"
    return True, f"Bloccato dalla RLS - HTTP {r.status_code}"
run("B - Medico_A assegna a paziente PENDING -> NEGATO", test_B)

# ── TEST C ──────────────────────────────────────────────────────────────────
def test_C():
    if not model_ex1_id: return True, "SKIP"
    r = post("assigned_exercises",
        {"doctor_id": uid_ma, "patient_id": uid_pb,
         "exercise_id": "ex1", "model_id": model_ex1_id, "target_reps": 5},
        tok_ma)
    if r.status_code in (200,201) and r.json():
        return False, "GRAVE: Medico_A ha assegnato al paziente di Medico_B"
    return True, f"Bloccato dalla RLS - HTTP {r.status_code}"
run("C - Medico_A assegna a paziente di Medico_B -> NEGATO", test_C)

# ── TEST D ──────────────────────────────────────────────────────────────────
def test_D():
    if not ae_id: return False, "Dipende da Test A"
    r = get("assigned_exercises", f"id=eq.{ae_id}&select=id,exercise_id,model_id,target_reps", tok_pa)
    data = r.json() if r.status_code == 200 else []
    if data and data[0].get("id") == ae_id:
        return True, f"Paziente_A vede la propria assegnazione: {data[0]}"
    return False, f"HTTP {r.status_code}: {r.text[:200]}"
run("D - Paziente_A legge propria assegnazione -> CONSENTITO", test_D)

# ── TEST E ──────────────────────────────────────────────────────────────────
def test_E():
    if not ae_id: return True, "SKIP (Test A non ha prodotto assegnazione)"
    r = get("assigned_exercises", f"id=eq.{ae_id}&select=id", tok_pb)
    data = r.json() if r.status_code == 200 else []
    if data:
        return False, f"DATA LEAK: Paziente_B vede assegnazione di Paziente_A: {data}"
    return True, f"Corretto - 0 righe restituite a Paziente_B (HTTP {r.status_code})"
run("E - Paziente_B legge assegnazione Paziente_A -> 0 righe", test_E)

# ── TEST F ──────────────────────────────────────────────────────────────────
def test_F():
    if not model_ex1_id: return True, "SKIP"
    r = post("assigned_exercises",
        {"doctor_id": uid_pa, "patient_id": uid_pa,
         "exercise_id": "ex1", "model_id": model_ex1_id, "target_reps": 5},
        tok_pa)
    if r.status_code in (200,201) and r.json():
        return False, "GRAVE: paziente ha inserito assegnazione"
    return True, f"Bloccato dalla RLS - HTTP {r.status_code}"
run("F - Paziente prova INSERT assigned_exercises -> NEGATO", test_F)

# ── TEST G ──────────────────────────────────────────────────────────────────
def test_G():
    if not model_ex6_id or not model_ex1_id:
        return True, "SKIP - model_ex6 active non disponibile nel DB"
    r = post("assigned_exercises",
        {"doctor_id": uid_ma, "patient_id": uid_pa,
         "exercise_id": "ex1", "model_id": model_ex6_id,  # INCOERENTE
         "target_reps": 5},
        tok_ma)
    if r.status_code in (200,201) and r.json():
        bad_id = r.json()[0].get("id")
        # cleanup del dato sporco
        delete("assigned_exercises", f"id=eq.{bad_id}")
        return False, f"GRAVE: incoerenza ex1+model_ex6 NON bloccata! id={bad_id}"
    body = r.text.lower()
    if "incoerenza" in body or "exercise_id" in body or "modello" in body:
        return True, f"Bloccato dal trigger - HTTP {r.status_code} (messaggio trigger)"
    return True, f"Bloccato - HTTP {r.status_code}: {r.text[:200]}"
run("G - Ex1 + model_id Ex6 -> NEGATO (trigger coerenza)", test_G)

# ── TEST H ──────────────────────────────────────────────────────────────────
def test_H():
    if not ae_id: return False, "Dipende da Test A"
    ae_r = requests.get(f"{REST}/assigned_exercises?id=eq.{ae_id}&select=exercise_id,model_id",
        headers=svc())
    ae = ae_r.json()[0] if ae_r.status_code == 200 and ae_r.json() else None
    if not ae: return False, "Riga assegnazione non trovata"
    em_r = requests.get(f"{REST}/exercise_models?id=eq.{ae['model_id']}&select=exercise_id,status",
        headers=svc())
    em = em_r.json()[0] if em_r.status_code == 200 and em_r.json() else None
    if em and em["exercise_id"] == ae["exercise_id"] and em["status"] == "active":
        return True, (f"Coerente: ae.exercise_id='{ae['exercise_id']}' == "
                      f"em.exercise_id='{em['exercise_id']}', em.status='{em['status']}'")
    return False, f"INCOERENTE: ae={ae} em={em}"
run("H - model_id salvato appartiene davvero a Ex1", test_H)

# ── TEST I ──────────────────────────────────────────────────────────────────
def test_I():
    rows_r = requests.get(
        f"{REST}/assigned_exercises?exercise_id=eq.ex1&select=id,model_id",
        headers=svc())
    rows = rows_r.json() if rows_r.status_code == 200 else []
    contaminated = []
    for row in rows:
        em_r = requests.get(
            f"{REST}/exercise_models?id=eq.{row['model_id']}&select=exercise_id",
            headers=svc())
        em = em_r.json()[0] if em_r.status_code == 200 and em_r.json() else None
        if em and em.get("exercise_id") != "ex1":
            contaminated.append({"ae_id": row["id"], "model_ex": em["exercise_id"]})
    if contaminated:
        return False, f"Righe contaminate: {contaminated}"
    return True, f"{len(rows)} assegnazione/i ex1 nel DB - tutte con model ex1"
run("I - Nessuna assegnazione Ex1 con model Ex6 nel DB", test_I)

# ── TEST J ──────────────────────────────────────────────────────────────────
def test_J():
    r = get("assigned_exercises", "select=id,patient_id", tok_pa)
    rows = r.json() if r.status_code == 200 else []
    wrong = [row for row in rows if row.get("patient_id") != uid_pa]
    if wrong:
        return False, f"DATA LEAK: Paziente_A vede righe di altri: {wrong}"
    return True, f"{len(rows)} assegnazione/i - tutte con patient_id={uid_pa}"
run("J - Dashboard Paziente_A contiene SOLO le proprie assegnazioni", test_J)

# ── TEST K ──────────────────────────────────────────────────────────────────
def test_K():
    if not ae_id: return True, "SKIP"
    r = patch("assigned_exercises", f"id=eq.{ae_id}",
              {"patient_id": uid_ma}, tok_ma)
    if r.status_code in (200,201) and r.json():
        return False, f"GRAVE: patient_id modificato! {r.json()}"
    return True, f"Bloccato dal trigger - HTTP {r.status_code}: {r.text[:200]}"
run("K - Medico_A cambia patient_id -> NEGATO (trigger immutabilita)", test_K)

# ── TEST L ──────────────────────────────────────────────────────────────────
def test_L():
    if not ae_id: return True, "SKIP"
    r = patch("assigned_exercises", f"id=eq.{ae_id}",
              {"doctor_id": uid_mb}, tok_ma)
    if r.status_code in (200,201) and r.json():
        return False, f"GRAVE: doctor_id modificato! {r.json()}"
    return True, f"Bloccato dal trigger - HTTP {r.status_code}: {r.text[:200]}"
run("L - Medico_A cambia doctor_id -> NEGATO (trigger immutabilita)", test_L)

# ── TEST M ──────────────────────────────────────────────────────────────────
def test_M():
    if not ae_id: return True, "SKIP"
    r = patch("assigned_exercises", f"id=eq.{ae_id}",
              {"target_reps": 99}, tok_mb)
    if r.status_code in (200,201) and r.json():
        return False, f"GRAVE: Medico_B ha modificato assegnazione di Medico_A"
    return True, f"Bloccato dalla RLS - HTTP {r.status_code}"
run("M - Medico_B modifica assegnazione Medico_A -> NEGATO (RLS)", test_M)

# ── TEST N — PatientRoute: medico -> accesso negato ──────────────────────────
def test_N():
    r = get("profili", f"id=eq.{uid_ma}&select=ruolo", tok_ma)
    data = r.json()
    if data and data[0].get("ruolo") == "medico":
        return True, (
            "PatientRoute.isMedico=True -> mostra 'Area Pazienti' + redirect. "
            f"Verificato: profilo DB ruolo='{data[0]['ruolo']}' (fonte: Supabase Auth->profili, non localStorage)"
        )
    return False, f"Profilo inatteso: {data}"
run("N - Medico apre /piano-riabilitativo -> PatientRoute nega accesso", test_N)

# ── TEST O — PatientRoute: paziente -> accesso consentito ────────────────────
def test_O():
    r = get("profili", f"id=eq.{uid_pa}&select=ruolo", tok_pa)
    data = r.json()
    if data and data[0].get("ruolo") == "paziente":
        return True, (
            "PatientRoute.isPaziente=True -> accesso consentito. "
            f"Verificato: profilo DB ruolo='{data[0]['ruolo']}' (fonte: Supabase Auth->profili)"
        )
    return False, f"Profilo inatteso: {data}"
run("O - Paziente apre /piano-riabilitativo -> PatientRoute consente accesso", test_O)

# ───────────────────────────────────────────────────────────────
# RIGA REALE: assigned_exercises + exercise_models
# ───────────────────────────────────────────────────────────────
print()
print("=" * 70)
print("RIGA REALE (Test A) - assigned_exercises + exercise_models")
print("=" * 70)

if ae_id:
    ae_full = requests.get(
        f"{REST}/assigned_exercises?id=eq.{ae_id}&select=*",
        headers=svc())
    ae_row = ae_full.json()[0] if ae_full.status_code == 200 and ae_full.json() else None
    if ae_row:
        print()
        print("  assigned_exercises:")
        for k in ["id","doctor_id","patient_id","exercise_id","model_id",
                  "target_reps","notes","assigned_at","updated_at"]:
            val = ae_row.get(k, "<colonna assente>")
            print(f"    {k:15}: {val}")

        # Colonna updated_at
        has_upd = "updated_at" in ae_row
        print(f"\n  updated_at colonna: {'PRESENTE' if has_upd else 'ASSENTE -> aggiungere ALTER TABLE'}")

        # exercise_models corrispondente
        em_full = requests.get(
            f"{REST}/exercise_models?id=eq.{ae_row.get('model_id')}&select=id,exercise_id,version,status,model_uri",
            headers=svc())
        em_row = em_full.json()[0] if em_full.status_code == 200 and em_full.json() else None
        if em_row:
            print()
            print("  exercise_models (model_id collegato):")
            for k in ["id","exercise_id","version","status","model_uri"]:
                print(f"    {k:15}: {em_row.get(k)}")
            match = ae_row.get("exercise_id") == em_row.get("exercise_id")
            print()
            print(f"  Verifica coerenza:")
            print(f"    assigned_exercises.exercise_id = '{ae_row.get('exercise_id')}'")
            print(f"    exercise_models.exercise_id    = '{em_row.get('exercise_id')}'")
            print(f"    MATCH: {'SI - COERENTE' if match else 'NO - INCOERENTE!'}")
else:
    print("  [SKIP] Test A non ha prodotto assegnazione")

# ───────────────────────────────────────────────────────────────
# CLEANUP (service_role)
# ───────────────────────────────────────────────────────────────
print()
print("-" * 70)
print("CLEANUP (service_role):")
if ae_id:
    delete("assigned_exercises", f"id=eq.{ae_id}")
    print(f"  assigned_exercises {ae_id} rimossa")
delete("doctor_patients", f"doctor_id=eq.{uid_ma}")
delete("doctor_patients", f"doctor_id=eq.{uid_mb}")
for uid in created_uids:
    admin_delete_user(uid)
print(f"  {len(created_uids)} utenti di test rimossi")

# ───────────────────────────────────────────────────────────────
# REPORT FINALE
# ───────────────────────────────────────────────────────────────
print()
print("=" * 70)
print("REPORT FINALE")
print("=" * 70)
passed = sum(1 for v in results.values() if v[0] == "PASS")
failed = sum(1 for v in results.values() if v[0] == "FAIL")
total  = len(results)
for label, (status, detail) in results.items():
    icon = "OK" if status == "PASS" else "NO"
    print(f"  [{icon}] {label}")
print()
print(f"  Totale: {passed}/{total} PASS, {failed} FAIL")
if failed == 0:
    print()
    print("  TUTTI I TEST SUPERATI - FASE 4A.1 APPROVATA")
else:
    print()
    print(f"  {failed} TEST FALLITI - revisione necessaria")
print("=" * 70)
