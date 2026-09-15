import urllib.request
import json

SUPABASE_URL = "https://hljxjrcvgwfedpsmyavc.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_EKM6tRPdVpwHD7IvMd9pig_KmoSmmFn"

def http_get(url, headers):
    req = urllib.request.Request(url, headers=headers, method='GET')
    with urllib.request.urlopen(req) as response:
        res_body = response.read().decode('utf-8')
        return response.status, json.loads(res_body) if res_body else []

def test_verify_profili():
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json"
    }

    profili_url = f"{SUPABASE_URL}/rest/v1/profili?select=id,nome,cognome,ruolo"
    status, profili = http_get(profili_url, headers)
    print(f"Status: {status}")
    print("Profili attualmente presenti nel DB Supabase PhysioVision:")
    for p in profili:
        print(" -", p)

if __name__ == "__main__":
    test_verify_profili()
