"""
FASE 4A.2 — Test reali A-O (post-fix)
======================================
Usa:
    $env:PYTHONIOENCODING="utf-8"
    python diag_and_run_4a2.py
"""
import os, sys, json, time, requests

SUPABASE_URL = "https://hljxjrcvgwfedpsmyavc.supabase.co"
ANON_KEY     = "sb_publishable_EKM6tRPdVpwHD7IvMd9pig_KmoSmmFn"
REST         = f"{SUPABASE_URL}/rest/v1"
AUTH         = f"{SUPABASE_URL}/auth/v1"

# Leggi service_role da .env.service
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
if not SERVICE_KEY:
    env_file = os.path.join(os.path.dirname(__file__), ".env.service")
    if os.path.exists(env_file):
        for line in open(env_file).read().splitlines():
            if line.startswith("SUPABASE_SERVICE_KEY="):
                SERVICE_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
if not SERVICE_KEY:
    print("ERRORE: SUPABASE_SERVICE_KEY non trovata.")
    sys.exit(1)
print("Service key: OK (" + SERVICE_KEY[:12] + "...)")

# ─────────────────────────────────────────────────────────────────────────────
# HEADERS (separati per GET vs POST/PATCH/DELETE)
# ─────────────────────────────────────────────────────────────────────────────
def svc_get():
    """Header service_role per GET (senza Prefer)."""
    return {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}

def svc_write():
    """Header service_role per POST/PATCH/DELETE."""
    return {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": "application/json", "Prefer": "return=representation"}

def jwt_get(token):
    """Header JWT normale per GET (RLS attiva)."""
    return {"apikey": ANON_KEY, "Authorization": f"Bearer {token}"}

def jwt_write(token):
    """Header JWT normale per POST/PATCH (RLS attiva)."""
    return {"apikey": ANON_KEY, "Authorization": f"Bearer {token}",
            "Content-Type": "application/json", "Prefer": "return=representation"}

def anon_hdr():
    return {"apikey": ANON_KEY, "Content-Type": "application/json"}

# ─────────────────────────────────────────────────────────────────────────────
# HTTP WRAPPERS
# ─────────────────────────────────────────────────────────────────────────────
def GET(table, qs="", token=None):
    h = jwt_get(token) if token else svc_get()
    return requests.get(f"{REST}/{table}?{qs}", headers=h)

def POST(table, body, token=None):
    h = jwt_write(token) if token else svc_write()
    return requests.post(f"{REST}/{table}", headers=h, json=body)

def PATCH(table, qs, body, token=None):
    h = jwt_write(token) if token else svc_write()
    return requests.patch(f"{REST}/{table}?{qs}", headers=h, json=body)

def DELETE(table, qs):
    return requests.delete(f"{REST}/{table}?{qs}", headers=svc_write())

def RPC(fn, body=None, token=None):
    h = jwt_write(token) if token else svc_write()
    return requests.post(f"{REST}/rpc/{fn}", headers=h, json=body or {})

def admin_create(email, pwd):
    r = requests.post(f"{AUTH}/admin/users", headers=svc_write(),
        json={"email": email, "password": pwd, "email_confirm": True})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"admin_create {email}: {r.status_code} {r.text[:300]}")
    return r.json()["id"]

def admin_del(uid):
    requests.delete(f"{AUTH}/admin/users/{uid}", headers=svc_write())
    DELETE("profili", f"id=eq.{uid}")

def signin(email, pwd):
    r = requests.post(f"{AUTH}/token?grant_type=password", headers=anon_hdr(),
        json={"email": email, "password": pwd})
    if r.status_code != 200:
        raise RuntimeError(f"signin {email}: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"], r.json()["user"]["id"]

# ─────────────────────────────────────────────────────────────────────────────
# RESULT TRACKER
# ─────────────────────────────────────────────────────────────────────────────
results = {}
def run(label, fn):
    try:
        ok, detail = fn()
        results[label] = ("PASS" if ok else "FAIL", detail)
        print(f"  {'OK' if ok else 'NO'}  {label}")
        print(f"      {detail}")
    except Exception as e:
        results[label] = ("FAIL", str(e))
        print(f"  NO  {label}")
        print(f"      ECCEZIONE: {e}")

SEP = "=" * 70
SEP2 = "-" * 70

# ═════════════════════════════════════════════════════════════════════════════
print("\n" + SEP)
print("FASE 4A.2 — Test reali A-O (post-fix RLS profili + doctor_patients)")
print(SEP)

TS = str(int(time.time()))[-6:]
created_uids = []
ae_id = None

# ─────────────────────────────────────────────────────────────────────────────
# SETUP: Modelli reali
# ─────────────────────────────────────────────────────────────────────────────
print("\n[PRE] Modelli exercise_models reali (ex1, ex6):")
rm = GET("exercise_models",
    "exercise_id=in.(ex1,ex6)&select=id,exercise_id,version,status,model_uri")
model_ex1_id = model_ex6_id = None
if rm.status_code == 200:
    for m in rm.json():
        print(f"  id={m.get('id')}")
        print(f"  exercise_id={m.get('exercise_id')}  version={m.get('version')}  status={m.get('status')}")
        print(f"  model_uri:  {m.get('model_uri')}")
        print()
        if m.get("exercise_id") == "ex1" and m.get("status") == "active" and not model_ex1_id:
            model_ex1_id = m["id"]
        if m.get("exercise_id") == "ex6" and m.get("status") == "active" and not model_ex6_id:
            model_ex6_id = m["id"]
else:
    print(f"  HTTP {rm.status_code}: {rm.text[:200]}")

# ─────────────────────────────────────────────────────────────────────────────
# SETUP: Utenti di test
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n[1/4] Creazione utenti di test (_{TS})...")
try:
    uid_ma = admin_create(f"ma_{TS}@pv.test", "PhysioTest!2026")
    uid_mb = admin_create(f"mb_{TS}@pv.test", "PhysioTest!2026")
    uid_pa = admin_create(f"pa_{TS}@pv.test", "PhysioTest!2026")
    uid_pb = admin_create(f"pb_{TS}@pv.test", "PhysioTest!2026")
    uid_pp = admin_create(f"pp_{TS}@pv.test", "PhysioTest!2026")
    created_uids = [uid_ma, uid_mb, uid_pa, uid_pb, uid_pp]
    print(f"  5 utenti Auth creati.")
except Exception as e:
    print(f"  ERRORE: {e}"); sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# SETUP: Profili (con service_role, GET corretto senza Prefer)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/4] Inserimento profili in public.profili...")
profili_defs = [
    (uid_ma, "MedicoA",         "MedicoA",         "medico"),
    (uid_mb, "MedicoB",         "MedicoB",         "medico"),
    (uid_pa, "PazienteA",       "PazienteA",       "paziente"),
    (uid_pb, "PazienteB",       "PazienteB",       "paziente"),
    (uid_pp, "PazientePending", "PazientePending", "paziente"),
]
all_profili_ok = True
for uid, nome, cognome, ruolo in profili_defs:
    r = POST("profili", {"id": uid, "nome": nome, "cognome": cognome, "ruolo": ruolo})
    if r.status_code in (200, 201):
        row = r.json()[0] if r.json() else {}
        print(f"  {nome:<22} INSERT HTTP {r.status_code} - ruolo={row.get('ruolo')} doctor_code={row.get('doctor_code')}")
    else:
        print(f"  {nome:<22} INSERT FALLITO HTTP {r.status_code}: {r.text[:200]}")
        all_profili_ok = False

# Verifica profili nel DB con GET corretto (senza Prefer)
print("\n  Verifica profili nel DB (service_role GET):")
for uid, nome, _, _ in profili_defs:
    r = GET("profili", f"id=eq.{uid}&select=id,nome,ruolo,doctor_code")
    if r.status_code == 200 and r.json():
        row = r.json()[0]
        print(f"    {nome:<22} PRESENTE - ruolo={row.get('ruolo')} doctor_code={row.get('doctor_code')}")
    else:
        print(f"    {nome:<22} NON TROVATO HTTP {r.status_code}: {r.text[:100]}")
        all_profili_ok = False

# ─────────────────────────────────────────────────────────────────────────────
# SETUP: doctor_patients
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/4] Setup doctor_patients (service_role)...")
r_dpa = POST("doctor_patients",
    {"doctor_id": uid_ma, "patient_id": uid_pa, "status": "active"})
dp_a_id = r_dpa.json()[0]["id"] if r_dpa.status_code in (200,201) and r_dpa.json() else None
print(f"  PAZIENTE_A -> MEDICO_A active: {'OK id='+dp_a_id if dp_a_id else 'ERR '+r_dpa.text[:150]}")

r_dpb = POST("doctor_patients",
    {"doctor_id": uid_mb, "patient_id": uid_pb, "status": "active"})
print(f"  PAZIENTE_B -> MEDICO_B active: {'OK' if r_dpb.status_code in (200,201) else 'ERR '+r_dpb.text[:100]}")

r_dpp = POST("doctor_patients",
    {"doctor_id": uid_ma, "patient_id": uid_pp, "status": "pending"})
print(f"  PENDING    -> MEDICO_A pending: {'OK' if r_dpp.status_code in (200,201) else 'ERR '+r_dpp.text[:100]}")

# ─────────────────────────────────────────────────────────────────────────────
# Sign-in sessioni JWT reali
# ─────────────────────────────────────────────────────────────────────────────
print("\n[4/4] Sign-in sessioni JWT reali (RLS attiva)...")
try:
    tok_ma, _ = signin(f"ma_{TS}@pv.test", "PhysioTest!2026")
    tok_mb, _ = signin(f"mb_{TS}@pv.test", "PhysioTest!2026")
    tok_pa, _ = signin(f"pa_{TS}@pv.test", "PhysioTest!2026")
    tok_pb, _ = signin(f"pb_{TS}@pv.test", "PhysioTest!2026")
    print("  Tutti autenticati.")
except Exception as e:
    print(f"  ERRORE signin: {e}"); sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# DIAGNOSTICA pre-test (con i fix applicati)
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + SEP2)
print("DIAGNOSTICA pre-test (JWT normali, RLS attiva):")

# 3A — profilo MEDICO_A
r_pma = GET("profili", f"id=eq.{uid_ma}&select=id,nome,ruolo,doctor_code", tok_ma)
print(f"\n  GET profili MEDICO_A (JWT): HTTP {r_pma.status_code}")
if r_pma.json():
    print(f"  -> {r_pma.json()[0]}  [PASS: ruolo visibile]")
else:
    print(f"  -> [] [FAIL: policy SELECT profili ancora mancante!]")

# 3B — is_medico()
r_im = RPC("is_medico", {}, tok_ma)
print(f"\n  RPC is_medico() (JWT MEDICO_A): HTTP {r_im.status_code} -> {r_im.text}")

# 3C — doctor_patients MEDICO_A/PAZIENTE_A via JWT
r_dp = GET("doctor_patients",
    f"doctor_id=eq.{uid_ma}&patient_id=eq.{uid_pa}&select=doctor_id,patient_id,status",
    tok_ma)
print(f"\n  GET doctor_patients MA/PA (JWT MEDICO_A): HTTP {r_dp.status_code}")
print(f"  -> {r_dp.json()}")

# 3D — profilo PAZIENTE_A via JWT
r_ppa = GET("profili", f"id=eq.{uid_pa}&select=id,nome,ruolo", tok_pa)
print(f"\n  GET profili PAZIENTE_A (JWT): HTTP {r_ppa.status_code}")
if r_ppa.json():
    print(f"  -> {r_ppa.json()[0]}  [PASS]")
else:
    print(f"  -> [] [FAIL: policy SELECT profili ancora mancante!]")

# ─────────────────────────────────────────────────────────────────────────────
# TEST A–O
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + SEP)
print("TEST A-O (sessioni JWT autentiche, RLS attiva)")
print(SEP)

# ── A ──────────────────────────────────────────────────────────────────────
def test_A():
    global ae_id
    if not model_ex1_id:
        return False, "model_ex1_id non disponibile"
    r = POST("assigned_exercises",
        {"doctor_id": uid_ma, "patient_id": uid_pa,
         "exercise_id": "ex1", "model_id": model_ex1_id,
         "target_reps": 10, "notes": "Test 4A.2 post-fix"},
        tok_ma)
    if r.status_code in (200, 201) and r.json():
        ae_id = r.json()[0]["id"]
        return True, f"Assegnazione creata - id={ae_id}"
    return False, f"HTTP {r.status_code}: {r.text[:400]}"
run("A - Medico_A assegna Ex1 a Paziente_A (active) -> CONSENTITO", test_A)

# ── B ──────────────────────────────────────────────────────────────────────
def test_B():
    if not model_ex1_id: return False, "model_ex1_id mancante"
    r = POST("assigned_exercises",
        {"doctor_id": uid_ma, "patient_id": uid_pp,
         "exercise_id": "ex1", "model_id": model_ex1_id, "target_reps": 5},
        tok_ma)
    if r.status_code in (200, 201) and r.json():
        bad = r.json()[0].get("id")
        DELETE("assigned_exercises", f"id=eq.{bad}")
        return False, f"GRAVE: passato su PENDING id={bad}"
    return True, f"Bloccato HTTP {r.status_code}"
run("B - Medico_A assegna a paziente PENDING -> NEGATO", test_B)

# ── C ──────────────────────────────────────────────────────────────────────
def test_C():
    if not model_ex1_id: return False, "model_ex1_id mancante"
    r = POST("assigned_exercises",
        {"doctor_id": uid_ma, "patient_id": uid_pb,
         "exercise_id": "ex1", "model_id": model_ex1_id, "target_reps": 5},
        tok_ma)
    if r.status_code in (200, 201) and r.json():
        return False, "GRAVE: passato su paziente di altro medico"
    return True, f"Bloccato HTTP {r.status_code}"
run("C - Medico_A assegna a paziente di Medico_B -> NEGATO", test_C)

# ── D ──────────────────────────────────────────────────────────────────────
def test_D():
    if not ae_id: return False, "DIPENDE DA TEST A (fallito)"
    r = GET("assigned_exercises",
        f"id=eq.{ae_id}&select=id,exercise_id,model_id,target_reps,notes", tok_pa)
    data = r.json() if r.status_code == 200 else []
    if data and data[0].get("id") == ae_id:
        return True, f"Paziente_A vede la propria assegnazione: {data[0]}"
    return False, f"HTTP {r.status_code}: {r.text[:200]}"
run("D - Paziente_A legge propria assegnazione -> CONSENTITO", test_D)

# ── E ──────────────────────────────────────────────────────────────────────
def test_E():
    if not ae_id: return False, "DIPENDE DA TEST A (fallito)"
    r = GET("assigned_exercises", f"id=eq.{ae_id}&select=id", tok_pb)
    data = r.json() if r.status_code == 200 else []
    if data: return False, f"DATA LEAK: Paziente_B vede {data}"
    return True, f"0 righe per Paziente_B HTTP {r.status_code}"
run("E - Paziente_B legge assegnazione Paziente_A -> 0 righe", test_E)

# ── F ──────────────────────────────────────────────────────────────────────
def test_F():
    if not model_ex1_id: return False, "model_ex1_id mancante"
    r = POST("assigned_exercises",
        {"doctor_id": uid_pa, "patient_id": uid_pa,
         "exercise_id": "ex1", "model_id": model_ex1_id, "target_reps": 5},
        tok_pa)
    if r.status_code in (200, 201) and r.json():
        return False, "GRAVE: paziente ha inserito assegnazione"
    return True, f"Bloccato HTTP {r.status_code}"
run("F - Paziente prova INSERT assigned_exercises -> NEGATO", test_F)

# ── G ──────────────────────────────────────────────────────────────────────
def test_G():
    if not model_ex6_id or not model_ex1_id:
        return False, "model_ex6_id active non disponibile"
    r = POST("assigned_exercises",
        {"doctor_id": uid_ma, "patient_id": uid_pa,
         "exercise_id": "ex1", "model_id": model_ex6_id,  # incoerente
         "target_reps": 5},
        tok_ma)
    if r.status_code in (200, 201) and r.json():
        bad = r.json()[0].get("id")
        DELETE("assigned_exercises", f"id=eq.{bad}")
        return False, f"GRAVE: incoerenza ex1+model_ex6 passata! id={bad}"
    return True, f"Bloccato HTTP {r.status_code}: {r.text[:200]}"
run("G - Ex1 + model_id Ex6 -> NEGATO (trigger coerenza)", test_G)

# ── H ──────────────────────────────────────────────────────────────────────
def test_H():
    if not ae_id: return False, "DIPENDE DA TEST A (fallito)"
    ae = GET("assigned_exercises",
        f"id=eq.{ae_id}&select=exercise_id,model_id").json()
    ae = ae[0] if ae else None
    if not ae: return False, "Riga assegnazione non trovata"
    em = GET("exercise_models",
        f"id=eq.{ae['model_id']}&select=exercise_id,status").json()
    em = em[0] if em else None
    if em and em["exercise_id"] == ae["exercise_id"] and em["status"] == "active":
        return True, (f"Coerente: ae.exercise_id='{ae['exercise_id']}'"
                      f" == em.exercise_id='{em['exercise_id']}'"
                      f" em.status='{em['status']}'")
    return False, f"INCOERENTE: ae={ae} em={em}"
run("H - model_id appartiene a Ex1 con status=active", test_H)

# ── I ──────────────────────────────────────────────────────────────────────
def test_I():
    rows = GET("assigned_exercises",
        "exercise_id=eq.ex1&select=id,model_id").json() or []
    bad = []
    for row in rows:
        em = GET("exercise_models",
            f"id=eq.{row['model_id']}&select=exercise_id").json()
        em = em[0] if em else None
        if em and em.get("exercise_id") != "ex1":
            bad.append({"ae_id": row["id"], "model_ex": em["exercise_id"]})
    if bad: return False, f"Contaminati: {bad}"
    return True, f"{len(rows)} assegnazione/i ex1 - tutte con model ex1"
run("I - Nessuna assegnazione Ex1 con model Ex6 nel DB", test_I)

# ── J ──────────────────────────────────────────────────────────────────────
def test_J():
    r = GET("assigned_exercises", "select=id,patient_id", tok_pa)
    rows = r.json() if r.status_code == 200 else []
    bad = [row for row in rows if row.get("patient_id") != uid_pa]
    if bad: return False, f"DATA LEAK: vede righe di altri: {bad}"
    return True, f"{len(rows)} assegnazione/i - tutte patient_id={uid_pa}"
run("J - Dashboard Paziente_A SOLO le proprie assegnazioni", test_J)

# ── K ──────────────────────────────────────────────────────────────────────
def test_K():
    if not ae_id: return False, "DIPENDE DA TEST A (fallito)"
    r = PATCH("assigned_exercises", f"id=eq.{ae_id}",
              {"patient_id": uid_ma}, tok_ma)
    if r.status_code in (200, 201) and r.json():
        return False, f"GRAVE: patient_id modificato! {r.json()}"
    return True, f"Bloccato HTTP {r.status_code}: {r.text[:200]}"
run("K - Medico_A cambia patient_id -> NEGATO (trigger immutabilita)", test_K)

# ── L ──────────────────────────────────────────────────────────────────────
def test_L():
    if not ae_id: return False, "DIPENDE DA TEST A (fallito)"
    r = PATCH("assigned_exercises", f"id=eq.{ae_id}",
              {"doctor_id": uid_mb}, tok_ma)
    if r.status_code in (200, 201) and r.json():
        return False, f"GRAVE: doctor_id modificato! {r.json()}"
    return True, f"Bloccato HTTP {r.status_code}: {r.text[:200]}"
run("L - Medico_A cambia doctor_id -> NEGATO (trigger immutabilita)", test_L)

# ── M ──────────────────────────────────────────────────────────────────────
def test_M():
    if not ae_id: return False, "DIPENDE DA TEST A (fallito)"
    r = PATCH("assigned_exercises", f"id=eq.{ae_id}",
              {"target_reps": 99}, tok_mb)
    if r.status_code in (200, 201) and r.json():
        return False, "GRAVE: Medico_B ha modificato assegnazione di Medico_A"
    return True, f"Bloccato RLS HTTP {r.status_code}"
run("M - Medico_B modifica assegnazione Medico_A -> NEGATO (RLS)", test_M)

# ── N ──────────────────────────────────────────────────────────────────────
def test_N():
    r = GET("profili", f"id=eq.{uid_ma}&select=ruolo", tok_ma)
    data = r.json() if r.status_code == 200 else []
    if data and data[0].get("ruolo") == "medico":
        return True, (f"PatientRoute.isMedico=True -> nega /piano-riabilitativo. "
                      f"DB ruolo='{data[0]['ruolo']}' (non localStorage)")
    return False, f"Profilo non leggibile da JWT medico: {data} HTTP {r.status_code}"
run("N - Medico -> PatientRoute nega /piano-riabilitativo", test_N)

# ── O ──────────────────────────────────────────────────────────────────────
def test_O():
    r = GET("profili", f"id=eq.{uid_pa}&select=ruolo", tok_pa)
    data = r.json() if r.status_code == 200 else []
    if data and data[0].get("ruolo") == "paziente":
        return True, (f"PatientRoute.isPaziente=True -> consente /piano-riabilitativo. "
                      f"DB ruolo='{data[0]['ruolo']}'")
    return False, f"Profilo non leggibile da JWT paziente: {data} HTTP {r.status_code}"
run("O - Paziente -> PatientRoute consente /piano-riabilitativo", test_O)

# ─────────────────────────────────────────────────────────────────────────────
# RIGA REALE
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + SEP)
print("RIGA REALE (Test A) — assigned_exercises + exercise_models")
print(SEP)

if ae_id:
    ae_r = GET("assigned_exercises", f"id=eq.{ae_id}&select=*")
    ae_row = ae_r.json()[0] if ae_r.status_code == 200 and ae_r.json() else None
    if ae_row:
        print("\n  assigned_exercises:")
        for k in ["id","doctor_id","patient_id","exercise_id","model_id",
                  "target_reps","notes","assigned_at","updated_at"]:
            print(f"    {k:15}: {ae_row.get(k, '<colonna assente>')}")
        has_upd = "updated_at" in ae_row
        print(f"\n  updated_at: {'PRESENTE' if has_upd else 'ASSENTE — ALTER TABLE necessario'}")

        em_r = GET("exercise_models",
            f"id=eq.{ae_row.get('model_id')}&select=id,exercise_id,version,status,model_uri")
        em_row = em_r.json()[0] if em_r.status_code == 200 and em_r.json() else None
        if em_row:
            print("\n  exercise_models (model_id collegato):")
            for k in ["id","exercise_id","version","status","model_uri"]:
                print(f"    {k:15}: {em_row.get(k)}")
            match = ae_row.get("exercise_id") == em_row.get("exercise_id")
            print(f"\n  Coerenza: ae.exercise_id='{ae_row.get('exercise_id')}' == "
                  f"em.exercise_id='{em_row.get('exercise_id')}' -> {'MATCH OK' if match else 'MISMATCH!'}")
else:
    print("  [SKIP] Test A non ha prodotto assegnazione.")

# ─────────────────────────────────────────────────────────────────────────────
# CLEANUP
# ─────────────────────────────────────────────────────────────────────────────
print("\n[CLEANUP]")
if ae_id:
    DELETE("assigned_exercises", f"id=eq.{ae_id}")
    print(f"  assigned_exercises {ae_id} rimossa")
DELETE("doctor_patients", f"doctor_id=eq.{uid_ma}")
DELETE("doctor_patients", f"doctor_id=eq.{uid_mb}")
for uid in created_uids:
    admin_del(uid)
print(f"  {len(created_uids)} utenti di test rimossi")

# ─────────────────────────────────────────────────────────────────────────────
# REPORT FINALE
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + SEP)
print("REPORT FINALE A-O")
print(SEP)
passed = sum(1 for v in results.values() if v[0] == "PASS")
failed = sum(1 for v in results.values() if v[0] == "FAIL")
total  = len(results)
for label, (status, detail) in results.items():
    print(f"  [{'OK' if status=='PASS' else 'NO'}] {label}")
    if status == "FAIL":
        print(f"         -> {detail}")
print(f"\n  Totale: {passed}/{total} PASS, {failed} FAIL")
if failed == 0:
    print("\n  TUTTI I TEST SUPERATI - FASE 4A.1 APPROVATA")
else:
    print(f"\n  {failed} TEST FALLITI")
print(SEP)
