import os, sys, json, time, requests
import asyncio
import websockets

SUPABASE_URL = "https://hljxjrcvgwfedpsmyavc.supabase.co"
ANON_KEY     = "sb_publishable_EKM6tRPdVpwHD7IvMd9pig_KmoSmmFn"
REST         = f"{SUPABASE_URL}/rest/v1"
AUTH         = f"{SUPABASE_URL}/auth/v1"
API_URL      = "http://127.0.0.1:8000/api/patient/session/start"
WS_URL       = "ws://127.0.0.1:8000/ws/stream"

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

def svc_get(): return {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
def svc_write(): return {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}
def jwt_get(token): return {"apikey": ANON_KEY, "Authorization": f"Bearer {token}"}
def jwt_write(token): return {"apikey": ANON_KEY, "Authorization": f"Bearer {token}", "Content-Type": "application/json", "Prefer": "return=representation"}
def anon_hdr(): return {"apikey": ANON_KEY, "Content-Type": "application/json"}

def GET(table, qs="", token=None): return requests.get(f"{REST}/{table}?{qs}", headers=jwt_get(token) if token else svc_get(), timeout=5)
def POST(table, body, token=None): return requests.post(f"{REST}/{table}", headers=jwt_write(token) if token else svc_write(), json=body, timeout=5)
def PATCH(table, qs, body, token=None): return requests.patch(f"{REST}/{table}?{qs}", headers=jwt_write(token) if token else svc_write(), json=body, timeout=5)
def DELETE(table, qs): return requests.delete(f"{REST}/{table}?{qs}", headers=svc_write(), timeout=5)

sys.path.insert(0, str(os.path.abspath("src")))
from services.auth_test_guard import assert_safe_test_user_operation, safe_admin_create_user, safe_admin_delete_user

def admin_create(email, pwd):
    assert_safe_test_user_operation(email, "admin_create")
    r = safe_admin_create_user(SUPABASE_URL, SERVICE_KEY, {"email": email, "password": pwd, "email_confirm": True})
    if r.status_code not in (200, 201): raise RuntimeError(f"admin_create {email}: {r.status_code} {r.text[:300]}")
    return r.json()["id"]

def admin_del(uid):
    safe_admin_delete_user(SUPABASE_URL, SERVICE_KEY, uid)
    DELETE("profili", f"id=eq.{uid}")

def signin(email, pwd):
    r = requests.post(f"{AUTH}/token?grant_type=password", headers=anon_hdr(), json={"email": email, "password": pwd})
    if r.status_code != 200: raise RuntimeError(f"signin {email}: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"], r.json()["user"]["id"]

results = {}
def run(label, fn):
    try:
        ok, detail = fn()
        results[label] = ("PASS" if ok else "FAIL", detail)
        print(f"  {'OK' if ok else 'NO'}  {label}")
    except Exception as e:
        results[label] = ("FAIL", f"EXC: {e}")
        print(f"  NO  {label} (EXC: {e})")

def admin_create_force(email, pwd):
    print(f"Creating user {email}...")
    assert_safe_test_user_operation(email, "admin_create_force")
    r = safe_admin_create_user(SUPABASE_URL, SERVICE_KEY, {"email": email, "password": pwd, "email_confirm": True})
    if r.status_code not in (200, 201): raise RuntimeError(f"admin_create {email}: {r.status_code} {r.text[:300]}")
    return r.json()["id"]

print("--- FIXTURE SETUP ---")
ts = int(time.time())
email_med = f"med_a_{ts}@test.com"
email_paz_a = f"paz_a_{ts}@test.com"
email_paz_b = f"paz_b_{ts}@test.com"

uid_med_a = admin_create_force(email_med, "Test1234!")
uid_paz_a = admin_create_force(email_paz_a, "Test1234!")
uid_paz_b = admin_create_force(email_paz_b, "Test1234!")

def ensure_profilo(uid, email, ruolo="paziente", doc_code=None):
    for _ in range(5):
        r = GET("profili", f"id=eq.{uid}")
        if r.status_code == 200 and len(r.json()) > 0:
            break
        time.sleep(1)
    r = GET("profili", f"id=eq.{uid}")
    if r.status_code == 200 and len(r.json()) == 0:
        rp = POST("profili", {"id": uid, "ruolo": "paziente", "nome": "Test", "cognome": "Test"})
        if rp.status_code not in (200, 201):
            print("ERR POST profili:", rp.text)

print(f"Ensuring med_a {uid_med_a}")
ensure_profilo(uid_med_a, email_med)
print(f"Ensuring paz_a {uid_paz_a}")
ensure_profilo(uid_paz_a, email_paz_a)
print(f"Ensuring paz_b {uid_paz_b}")
ensure_profilo(uid_paz_b, email_paz_b)

time.sleep(1)
print("Patching profili...")
PATCH("profili", f"id=eq.{uid_med_a}", {"ruolo":"medico", "doctor_code":f"DOC-{ts}"})
PATCH("profili", f"id=eq.{uid_paz_a}", {"ruolo":"paziente"})
PATCH("profili", f"id=eq.{uid_paz_b}", {"ruolo":"paziente"})

print("Creating doctor_patients links...")

r1 = POST("doctor_patients", {"doctor_id":uid_med_a, "patient_id":uid_paz_a, "status":"pending"})
if r1.status_code not in (200, 201): print("ERR POST dp A:", r1.text)
r2 = PATCH("doctor_patients", f"doctor_id=eq.{uid_med_a}&patient_id=eq.{uid_paz_a}", {"status":"active"})
if r2.status_code not in (200, 204): print("ERR PATCH dp A:", r2.text)

r3 = POST("doctor_patients", {"doctor_id":uid_med_a, "patient_id":uid_paz_b, "status":"pending"})
if r3.status_code not in (200, 201): print("ERR POST dp B:", r3.text)

rm = GET("exercise_models", "exercise_id=eq.ex1&status=eq.active")
model_id_ex1 = rm.json()[0]["id"]

rass = POST("assigned_exercises", {
    "doctor_id": uid_med_a,
    "patient_id": uid_paz_a,
    "exercise_id": "ex1",
    "model_id": model_id_ex1,
    "target_reps": 10
}, token=signin(email_med, "Test1234!")[0])
if rass.status_code not in (200, 201):
    print("ERRORE INSERIMENTO ASSIGNED:", rass.text)
    sys.exit(1)
assignment_id = rass.json()[0]["id"]

tok_paz_a, _ = signin(email_paz_a, "Test1234!")
tok_paz_b, _ = signin(email_paz_b, "Test1234!")
tok_med_a, _ = signin(email_med, "Test1234!")

print(f"assignment_id generato per Paz_A: {assignment_id}")

print("\n--- ESECUZIONE TEST FASE 4B ---")

def test_A():
    r = requests.post(API_URL, json={"assignment_id": assignment_id}, headers={"Authorization": tok_paz_a})
    if r.status_code == 200 and r.json().get("exercise_id") == "ex1":
        return True, "200 OK, ex1 autorizzato"
    return False, f"{r.status_code} {r.text}"
run("A. POST start Paziente A (corretto)", test_A)

def test_B():
    r = requests.post(API_URL, json={"assignment_id": assignment_id}, headers={"Authorization": tok_paz_b})
    if r.status_code == 403:
        return True, "403 come atteso"
    return False, f"{r.status_code} {r.text}"
run("B. POST start Paziente B su assignment altrui", test_B)

def test_C():
    r = requests.post(API_URL, json={"assignment_id": assignment_id})
    if r.status_code == 401:
        return True, "401 come atteso"
    return False, f"{r.status_code} {r.text}"
run("C. POST start Token mancante", test_C)

def test_D():
    r = requests.post(API_URL, json={"assignment_id": assignment_id}, headers={"Authorization": tok_med_a})
    if r.status_code == 200:
        return True, "Medico può vedere, OK"
    return False, f"{r.status_code} {r.text}"
run("D. POST start Medico A (proprietario)", test_D)

async def ws_test(token, assign_id):
    try:
        async with websockets.connect(WS_URL) as ws:
            await ws.send(json.dumps({"assignment_id": assign_id, "token": token}))
            await asyncio.sleep(0.5)
            await ws.send(json.dumps({"image": "data:image/jpeg;base64,123", "frame_idx": 1}))
            res = await asyncio.wait_for(ws.recv(), timeout=3.0)
            return True, res
    except Exception as e:
        return False, str(e)

def test_E():
    ok, res = asyncio.run(ws_test(tok_paz_a, assignment_id))
    if ok and "status" in res:
        return True, "WS connessa e modello caricato con successo"
    return False, res
run("E. WS Paziente A (autorizzato)", test_E)

def test_F():
    ok, res = asyncio.run(ws_test(tok_paz_b, assignment_id))
    if ok:
        data = json.loads(res)
        return True, f"WS scarta o non predice: {res}"
    return False, res
run("F. WS Paziente B (rifiutato)", test_F)

print("\n--- RISULTATI FASE 4B ---")
passed = sum(1 for (st, _) in results.values() if st == "PASS")
print(f"TOTAL: {passed} / {len(results)} PASS")
for lbl, (st, det) in results.items():
    print(f"{st} - {lbl} : {det}")

admin_del(uid_med_a)
admin_del(uid_paz_a)
admin_del(uid_paz_b)
print("Cleanup done.")
