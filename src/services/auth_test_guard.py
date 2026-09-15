"""
Modulo di protezione e sicurezza per i test automatici e script diagnostici.
Garantisce in modo assoluto e categorico che nessun test o script possa MAI
modificare, alterare password o cancellare gli account reali dell'applicazione.
"""

import requests
import re
from typing import Optional, Set

PROTECTED_REAL_EMAILS: Set[str] = {
    "angelastark121@gmail.com",
    "angela.brunooc12@gmail.com",
    "francescopiocapano2004@gmail.com",
}

# Domini personali o reali vietati a prescindere per operazioni distruttive di test
FORBIDDEN_REAL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "yahoo.com",
    "yahoo.it",
    "icloud.com",
    "me.com",
    "libero.it",
    "virgilio.it",
    "tim.it",
    "alice.it",
    "fastwebnet.it",
    "tiscali.it",
    "proton.me",
    "protonmail.com"
}

ALLOWED_TEST_DOMAINS = {
    "test.physiovision.internal",
    "test.physiovision.it",
    "physiovision.com",
    "rehabai.test",
    "test.com",
    "test.org",
    "physiovision.internal",
    "wanaivideogenerator.com",  # Usato per account temporanei di test
}

def is_protected_account(email: str) -> bool:
    """Verifica se un'email appartiene a un account reale protetto."""
    if not email or not isinstance(email, str):
        return True
    email_clean = email.strip().lower()
    
    if email_clean in PROTECTED_REAL_EMAILS:
        return True
        
    parts = email_clean.split("@")
    if len(parts) == 2:
        domain = parts[1]
        if domain in FORBIDDEN_REAL_DOMAINS:
            return True
            
    return False

def is_valid_test_account(email: str) -> bool:
    """
    Verifica se un'email rispetta rigorosamente i pattern consentiti per account di test:
    - Inizia con 'test_runner_'
    - Oppure ha un prefisso esplicito di test ('test_', 'medico_a_', 'medico_b_', 'paz_a_', 'paz_b_', 'paz_p_', 'med_a_', 'paz_')
    - Ed ha un dominio di test consentito
    - E NON appartiene agli account protetti
    """
    if not email or not isinstance(email, str):
        return False
        
    email_clean = email.strip().lower()
    
    if is_protected_account(email_clean):
        return False
        
    if email_clean.startswith("test_runner_"):
        return True
        
    parts = email_clean.split("@")
    if len(parts) != 2:
        return False
        
    local_part, domain = parts[0], parts[1]
    
    # Se il dominio è esplicitamente di test
    if domain in ALLOWED_TEST_DOMAINS or domain.endswith(".test") or "test" in domain:
        # Verifica prefisso o struttura
        test_prefixes = (
            "test_", "test_runner_", "medico_a_", "medico_b_", "paziente_a_", "paziente_b_",
            "paz_a_", "paz_b_", "paz_p_", "med_a_", "paz_", "dr.test.", "paz.test.", "mu1"
        )
        if any(local_part.startswith(pref) for pref in test_prefixes) or "test" in local_part:
            return True

    return False

def assert_safe_test_user_operation(email: str, operation: str = "modify") -> None:
    """
    Solleva un'eccezione PermissionError bloccante se l'account specificato è reale
    o non rispetta i criteri di utente temporaneo di test.
    """
    if not email:
        raise PermissionError(f"[SAFETY GUARD] Operazione '{operation}' bloccata: email utente non specificata.")

    email_clean = email.strip().lower()

    if is_protected_account(email_clean) or not is_valid_test_account(email_clean):
        raise PermissionError(
            f"[SAFETY GUARD BLOCKED] Operazione distruttiva '{operation}' BLOCCATA su account: '{email}'.\n"
            f"Gli account reali e personali sono RIGOROSAMENTE PROTETTI e non possono essere alterati dai test.\n"
            f"I test automatici e diagnostici possono creare/modificare/eliminare solo account di test temporanei "
            f"(es. prefisso 'test_runner_' o domini di test dedicati)."
        )

def assert_safe_user_id_operation(
    user_id: str, 
    supabase_url: str, 
    service_key: str, 
    operation: str = "modify"
) -> str:
    """
    Dato un user_id, interroga Supabase Admin API per recuperare l'email associata
    e valida che l'operazione sia permessa. Restituisce l'email se sicura, altrimenti solleva eccezione.
    """
    if not user_id:
        raise PermissionError(f"[SAFETY GUARD] Operazione '{operation}' bloccata: user_id non specificato.")
        
    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}
    try:
        r = requests.get(f"{supabase_url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=10)
        if r.status_code == 200:
            email = r.json().get("email", "")
            assert_safe_test_user_operation(email, operation)
            return email
        else:
            raise PermissionError(f"[SAFETY GUARD] Impossibile verificare l'identità di user_id '{user_id}' (HTTP {r.status_code}). Operazione bloccata.")
    except PermissionError:
        raise
    except Exception as e:
        raise PermissionError(f"[SAFETY GUARD] Errore durante la verifica di sicurezza per user_id '{user_id}': {e}. Operazione bloccata.")

def safe_admin_update_user(
    supabase_url: str, 
    service_key: str, 
    user_id: str, 
    payload: dict, 
    email: Optional[str] = None
) -> requests.Response:
    """
    Wrapper sicuro per aggiornamento utente via Admin API (es. PUT /auth/v1/admin/users/{user_id}).
    Verifica prima che l'utente non sia un account reale protetto.
    """
    if email:
        assert_safe_test_user_operation(email, operation="admin_update_user")
    else:
        assert_safe_user_id_operation(user_id, supabase_url, service_key, operation="admin_update_user")
        
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json"
    }
    return requests.put(f"{supabase_url}/auth/v1/admin/users/{user_id}", headers=headers, json=payload, timeout=10)

def safe_admin_delete_user(
    supabase_url: str, 
    service_key: str, 
    user_id: str, 
    email: Optional[str] = None
) -> requests.Response:
    """
    Wrapper sicuro per cancellazione utente via Admin API (DELETE /auth/v1/admin/users/{user_id}).
    Verifica prima che l'utente non sia un account reale protetto.
    """
    if email:
        assert_safe_test_user_operation(email, operation="admin_delete_user")
    else:
        assert_safe_user_id_operation(user_id, supabase_url, service_key, operation="admin_delete_user")
        
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}"
    }
    return requests.delete(f"{supabase_url}/auth/v1/admin/users/{user_id}", headers=headers, timeout=10)

def safe_admin_create_user(
    supabase_url: str, 
    service_key: str, 
    payload: dict
) -> requests.Response:
    """
    Wrapper sicuro per creazione utente via Admin API (POST /auth/v1/admin/users).
    Verifica che l'email creata sia un account temporaneo di test consentito.
    """
    email = payload.get("email", "")
    assert_safe_test_user_operation(email, operation="admin_create_user")
    
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json"
    }
    return requests.post(f"{supabase_url}/auth/v1/admin/users", headers=headers, json=payload, timeout=10)

