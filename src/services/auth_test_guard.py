"""
Modulo di protezione e sicurezza per i test automatici.
Garantisce che nessun test possa MAI modificare, alterare la password o cancellare
gli account reali usati dal browser.
"""

PROTECTED_REAL_EMAILS = {
    "angelastark121@gmail.com",
    "angela.brunooc12@gmail.com",
    "francescopiocapano2004@gmail.com",
}

def assert_safe_test_user_operation(email: str, operation: str = "modify"):
    """
    Blocca categoricamente qualsiasi operazione di modifica, reset password o cancellazione
    su account utente reali. Le operazioni distruttive sono permesse ESCLUSIVAMENTE su account
    dedicati che iniziano con il prefisso 'test_runner_'.
    """
    if not email:
        raise PermissionError(f"[SAFETY GUARD] Operazione '{operation}' bloccata: email utente non specificata.")

    email_clean = email.strip().lower()

    if email_clean in PROTECTED_REAL_EMAILS or not email_clean.startswith("test_runner_"):
        raise PermissionError(
            f"[SAFETY GUARD BLOCKED] Operazione distruttiva '{operation}' BLOCCATA su account: '{email}'. "
            f"Gli account reali del browser non possono essere modificati dai test automatici. "
            f"I test possono alterare solo account temporanei con prefisso 'test_runner_'."
        )
