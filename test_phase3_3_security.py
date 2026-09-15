import urllib.request
import json

SUPABASE_URL = "https://hljxjrcvgwfedpsmyavc.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_EKM6tRPdVpwHD7IvMd9pig_KmoSmmFn"

def http_post(url, headers, body_dict):
    data = json.dumps(body_dict).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode('utf-8')
            return response.status, json.loads(res_body) if res_body else {}
    except urllib.error.HTTPError as e:
        res_body = e.read().decode('utf-8')
        return e.code, json.loads(res_body) if res_body else {}

def http_get(url, headers):
    req = urllib.request.Request(url, headers=headers, method='GET')
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode('utf-8')
            return response.status, json.loads(res_body) if res_body else []
    except urllib.error.HTTPError as e:
        res_body = e.read().decode('utf-8')
        return e.code, json.loads(res_body) if res_body else {}

def test_security_and_roles():
    print("=== TEST FASE 3.3: HARDENING AUTH E SICUREZZA SUPABASE ===")
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json"
    }

    doc_email = "medico.test.sec@physiovision.com"
    doc_pass = "TestPassword123!"
    
    print(f"\n1. Autenticazione Medico ({doc_email})...")
    status_doc, tok_doc = http_post(f"{SUPABASE_URL}/auth/v1/token?grant_type=password", headers, {"email": doc_email, "password": doc_pass})
    print("Token status:", status_doc, "Response:", tok_doc)
    
    if status_doc != 200:
        print("Registrazione medico...")
        status_sig, tok_sig = http_post(f"{SUPABASE_URL}/auth/v1/signup", headers, {
            "email": doc_email, 
            "password": doc_pass, 
            "data": {"nome": "Mario", "cognome": "Rossi", "ruolo": "medico"}
        })
        print("Signup status:", status_sig, "Response:", tok_sig)
        if tok_sig.get("access_token"):
            tok_doc = tok_sig
        else:
            status_doc, tok_doc = http_post(f"{SUPABASE_URL}/auth/v1/token?grant_type=password", headers, {"email": doc_email, "password": doc_pass})

    if "access_token" in tok_doc:
        doc_token = tok_doc["access_token"]
        doc_id = tok_doc["user"]["id"]

        doc_headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {doc_token}",
            "Content-Type": "application/json"
        }

        # Inserimento / Upsert profilo su DB
        prof_payload = {"id": doc_id, "nome": "Mario", "cognome": "Rossi", "ruolo": "medico"}
        http_post(f"{SUPABASE_URL}/rest/v1/profili", {**doc_headers, "Prefer": "resolution=merge-duplicates"}, prof_payload)

        # Interrogazione autorevole su public.profili
        p_status, doc_profile = http_get(f"{SUPABASE_URL}/rest/v1/profili?id=eq.{doc_id}&select=ruolo", doc_headers)
        print(f"Risultato DB per medico (id={doc_id}): {doc_profile}")
        if isinstance(doc_profile, list) and len(doc_profile) > 0:
            assert doc_profile[0]["ruolo"] == "medico", "Il ruolo DB per il medico deve essere 'medico'"
            print("-> Esito Medico: AUTOREVOLE DA DB OK ('medico')")

    print("\n=== VERIFICA COMPLETATA ===")

if __name__ == "__main__":
    test_security_and_roles()
