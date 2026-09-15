import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / 'src' / '.env')

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY") or ""

supabase_client = None
if SUPABASE_URL and SUPABASE_URL.startswith("http") and SUPABASE_KEY:
    try:
        from supabase import create_client, Client
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"[WARNING] Warning initializing Supabase python client: {e}")


class DatabaseService:
    """
    Servizio per la persistenza e gestione dati su Supabase
    (esercizi, exercise_profiles, ripetizioni_generate, exercise_models).
    """

    def __init__(self, client: Optional[Any] = supabase_client):
        self.client = client
        self._local_esercizi: Dict[str, dict] = {}
        self._local_profiles: Dict[str, dict] = {}
        self._local_reps: Dict[str, list] = {}
        self._local_models: Dict[str, list] = {}

    def get_user_client(self, jwt_token: str = None):
        """Restituisce un client Supabase con il JWT dell'utente o il client di default."""
        if not jwt_token or not self.client:
            return self.client
        try:
            from supabase import create_client, ClientOptions
            options = ClientOptions(headers={"Authorization": f"Bearer {jwt_token}"})
            scoped_client = create_client(SUPABASE_URL, SUPABASE_KEY, options=options)
            # Forza l'Authorization anche sul wrapper postgrest
            scoped_client.postgrest.auth(jwt_token)
            return scoped_client
        except Exception as e:
            print(f"[WARNING] Fallita creazione client Supabase scoped: {e}")
            return self.client

    def create_exercise(self, exercise_data: dict, profile_data: dict, jwt_token: str = None) -> dict:
        exercise_id = exercise_data["exercise_id"]
        creato_da = exercise_data.get("creato_da", "SCONOSCIUTO")
        existing_exercise_found = False
        
        client = self.get_user_client(jwt_token)
        if client:
            if jwt_token:
                try:
                    user_res = client.auth.get_user(jwt_token)
                    user_id = user_res.user.id
                    print(f"AUTH DEBUG user_id={user_id}")
                    
                    prof_res = client.table("profili").select("id, ruolo").eq("id", user_id).limit(1).execute()
                    profile_role = prof_res.data[0].get("ruolo") if prof_res.data and len(prof_res.data) > 0 else "null"
                    print(f"AUTH DEBUG profile_role={profile_role}")
                    
                    try:
                        is_medico_res = client.rpc("is_medico").execute()
                        print(f"AUTH DEBUG is_medico={is_medico_res.data}")
                    except Exception as e_rpc:
                        print(f"AUTH DEBUG is_medico=fallito ({e_rpc})")
                        
                    print(f"AUTH DEBUG creato_da={creato_da}")
                    
                    # 2. CONTROLLA CONFLITTO ESERCIZIO
                    check_ex = client.table("esercizi").select("exercise_id, creato_da").eq("exercise_id", exercise_id).limit(1).execute()
                    existing_exercise_found = len(check_ex.data) > 0 if check_ex.data else False
                    existing_creato_da = check_ex.data[0].get("creato_da") if existing_exercise_found else "null"
                    print(f"AUTH DEBUG existing_exercise_found={str(existing_exercise_found).lower()}")
                    print(f"AUTH DEBUG existing_creato_da={existing_creato_da}")
                    
                except Exception as e_debug:
                    print(f"AUTH DEBUG ERRORE DURANTE I LOG: {e_debug}")
                    # Assicuriamoci che existing_exercise_found venga comunque calcolato in caso di errore log
                    try:
                        check_ex = client.table("esercizi").select("exercise_id").eq("exercise_id", exercise_id).limit(1).execute()
                        existing_exercise_found = len(check_ex.data) > 0 if check_ex.data else False
                    except:
                        pass

            try:
                if existing_exercise_found:
                    ex_res = client.table("esercizi").update(exercise_data).eq("exercise_id", exercise_id).execute()
                    prof_res = client.table("exercise_profiles").update(profile_data).eq("exercise_id", exercise_id).execute()
                else:
                    ex_res = client.table("esercizi").insert(exercise_data).execute()
                    prof_res = client.table("exercise_profiles").insert(profile_data).execute()
                return {"esercizi": ex_res.data, "exercise_profiles": prof_res.data}
            except Exception as e:
                print(f"[ERROR] Errore DB Supabase create_exercise: {e}")
                raise e

        self._local_esercizi[exercise_id] = exercise_data
        self._local_profiles[exercise_id] = profile_data
        return {"esercizi": [exercise_data], "exercise_profiles": [profile_data]}

    def get_exercise(self, exercise_id: str) -> Optional[dict]:
        if self.client:
            try:
                res = self.client.table("esercizi").select("*, exercise_profiles(*)").eq("exercise_id", exercise_id).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
            except Exception as e:
                print(f"[WARNING] Errore DB Supabase get_exercise: {e}")

        ex = self._local_esercizi.get(exercise_id)
        if ex:
            ex_copy = dict(ex)
            ex_copy["exercise_profiles"] = self._local_profiles.get(exercise_id)
            return ex_copy
        return None

    def save_generated_reps(self, exercise_id: str, video_source: str, reps: List[dict], jwt_token: str = None) -> List[dict]:
        import uuid
        records = []
        for rep in reps:
            records.append({
                "id": rep.get("id") or str(uuid.uuid4()),
                "exercise_id": exercise_id,
                "video_source": video_source,
                "rep_index": rep["rep_index"],
                "start_frame": rep["start_frame"],
                "end_frame": rep["end_frame"],
                "peak_frame": rep.get("peak_frame"),
                "doctor_validation": rep.get("doctor_validation", "not_confirmed"),
                "confermata_medico": rep.get("doctor_validation") == "confirmed",
                "accettata_medico": False
            })

        client = self.get_user_client(jwt_token)
        if client and records:
            try:
                res = client.table("ripetizioni_generate").insert(records).execute()
                return res.data
            except Exception as e:
                print(f"[ERROR] Errore DB Supabase save_generated_reps: {e}")
                raise e

        existing = self._local_reps.setdefault(exercise_id, [])
        existing.extend(records)
        return records

    def get_generated_reps(self, exercise_id: str, jwt_token: str = None) -> List[dict]:
        client = self.get_user_client(jwt_token)
        if client:
            try:
                res = client.table("ripetizioni_generate").select("*").eq("exercise_id", exercise_id).order("created_at").execute()
                return res.data
            except Exception as e:
                print(f"[ERROR] Errore DB Supabase get_generated_reps: {e}")
                raise e

        return self._local_reps.get(exercise_id, [])

    def update_rep_reviews(self, exercise_id: str, reviews: List[dict], jwt_token: str = None) -> int:
        updated_count = 0
        client = self.get_user_client(jwt_token)
        
        # LOGS E DIAGNOSTICA INIZIALE
        print(f"REVIEW AUTH jwt_present={bool(jwt_token)}")
        if jwt_token and client:
            try:
                user_res = client.auth.get_user(jwt_token)
                print(f"REVIEW AUTH user_id={user_res.user.id}")
            except Exception as e:
                print(f"REVIEW AUTH user_id=error({e})")
                
        if client:
            try:
                # 3. Logga visible_rows
                res_vis = client.table("ripetizioni_generate").select("id").eq("exercise_id", exercise_id).execute()
                print(f"REVIEW DB visible_rows={len(res_vis.data) if res_vis.data else 0}")
                
                if reviews:
                    first_id = reviews[0].get("id")
                    if first_id:
                        res_first = client.table("ripetizioni_generate").select("*").eq("id", first_id).limit(1).execute()
                        first_id_found = bool(res_first.data)
                        print(f"REVIEW DB first_id_found={first_id_found}")
                        
                        if first_id_found:
                            # 5. Esegui UPDATE SOLO di quella riga e rileggi
                            acc = bool(reviews[0].get("accettata"))
                            update_data = {
                                "accettata_medico": acc,
                                "confermata_medico": acc,
                                "doctor_validation": "accepted" if acc else "rejected"
                            }
                            client.table("ripetizioni_generate").update(update_data).eq("id", first_id).execute()
                            res_after = client.table("ripetizioni_generate").select("*").eq("id", first_id).execute()
                            print(f"REVIEW DB first_after_update={res_after.data[0] if res_after.data else None}")
                            # Interrompiamo la normale esecuzione del ciclo come richiesto dalla diagnostica
                            # ma lo faremo solo se il log diagnostico va a buon fine, per isolare il problema.

                # Procediamo con l'aggiornamento reale
                for r in reviews:
                    accettata = bool(r["accettata"])
                    update_data = {
                        "accettata_medico": accettata,
                        "confermata_medico": accettata,
                        "doctor_validation": "accepted" if accettata else "rejected"
                    }
                    query = client.table("ripetizioni_generate").update(update_data)
                    if r.get("id"):
                        res = query.eq("id", r["id"]).execute()
                    elif r.get("video_source"):
                        res = query.eq("exercise_id", exercise_id).eq("video_source", r["video_source"]).eq("rep_index", r["rep_index"]).execute()
                    else:
                        res = query.eq("exercise_id", exercise_id).eq("rep_index", r["rep_index"]).execute()
                    if res.data:
                        updated_count += len(res.data)
                return updated_count
            except Exception as e:
                print(f"[ERROR] Errore DB Supabase update_rep_reviews: {e}")
                raise e

        reps = self._local_reps.get(exercise_id, [])
        for r in reviews:
            target_id = r.get("id")
            v_src = r.get("video_source")
            r_idx = r.get("rep_index")
            accettata = bool(r["accettata"])
            for rep in reps:
                if target_id and rep.get("id") == target_id:
                    rep["accettata_medico"] = accettata
                    updated_count += 1
                    break
                elif v_src and rep.get("video_source") == v_src and rep.get("rep_index") == r_idx:
                    rep["accettata_medico"] = accettata
                    updated_count += 1
                    break
                elif not target_id and not v_src and rep.get("rep_index") == r_idx:
                    rep["accettata_medico"] = accettata
                    updated_count += 1
        return updated_count

    def save_exercise_model(
        self,
        exercise_id: str,
        model_uri: str,
        normalization_stats_uri: str,
        metrics: dict,
        config: dict,
        version: int = 1,
        status: str = "active",
        jwt_token: str = None
    ) -> dict:
        record = {
            "exercise_id": exercise_id,
            "model_uri": model_uri,
            "normalization_stats_uri": normalization_stats_uri,
            "version": version,
            "status": status,
            "metrics": metrics,
            "segmentation_version": "v11",
            "config": config
        }

        client = self.get_user_client(jwt_token)
        print(f"MODEL SAVE DEBUG jwt_present={bool(jwt_token)}")
        print(f"MODEL SAVE DEBUG exercise_id={exercise_id}")

        if client:
            try:
                if jwt_token:
                    user_res = client.auth.get_user(jwt_token)
                    print(f"MODEL SAVE DEBUG user_id={user_res.user.id}")
                    
                    ex_res = client.table("esercizi").select("exercise_id, creato_da").eq("exercise_id", exercise_id).execute()
                    found = bool(ex_res.data)
                    print(f"MODEL SAVE DEBUG exercise_found={found}")
                    if found:
                        print(f"MODEL SAVE DEBUG exercise_creato_da={ex_res.data[0].get('creato_da')}")
                        
                res = client.table("exercise_models").upsert(record, on_conflict="exercise_id,version").execute()
                
                if res.data:
                    saved_row = res.data[0]
                    print(f"MODEL SAVE DEBUG saved=true")
                    print(f"MODEL SAVE DEBUG model_id={saved_row.get('id')}")
                    print(f"MODEL SAVE DEBUG status={saved_row.get('status')}")
                    return saved_row
                return record
            except Exception as e:
                print(f"[ERROR] Errore DB Supabase save_exercise_model: {e}")
                raise e

        models = self._local_models.setdefault(exercise_id, [])
        models.append(record)
        return record

    def get_doctor_exercises(self, jwt_token: str) -> List[dict]:
        client = self.get_user_client(jwt_token)
        if not client:
            return []
        try:
            # Recuperiamo tutti gli esercizi. RLS garantisce visibilità solo dei propri se configurato, 
            # altrimenti o in dev restituisce quelli accessibili
            res = client.table("esercizi").select("*").order("created_at", desc=True).execute()
            return res.data
        except Exception as e:
            print(f"[ERROR] Errore DB Supabase get_doctor_exercises: {e}")
            raise e

    def get_doctor_exercise_details(self, exercise_id: str, jwt_token: str) -> dict:
        client = self.get_user_client(jwt_token)
        if not client:
            raise Exception("Supabase client non inizializzato o token non valido")
            
        try:
            # Dati base
            ex_res = client.table("esercizi").select("*").eq("exercise_id", exercise_id).single().execute()
            exercise = ex_res.data
            
            # Profilo
            prof_res = client.table("exercise_profiles").select("*").eq("exercise_id", exercise_id).maybe_single().execute()
            profile = prof_res.data
            
            # Reps
            reps_res = client.table("ripetizioni_generate").select("*").eq("exercise_id", exercise_id).execute()
            reps = reps_res.data if reps_res.data else []
            
            # Modelli
            models_res = client.table("exercise_models").select("*").eq("exercise_id", exercise_id).eq("status", "active").order("version", desc=True).order("created_at", desc=True).limit(1).execute()
            model = models_res.data[0] if models_res.data else None
            
            return {
                "exercise": exercise,
                "profile": profile,
                "reps": reps,
                "model": model
            }
        except Exception as e:
            print(f"[ERROR] Errore DB Supabase get_doctor_exercise_details: {e}")
            raise e


db_service = DatabaseService()
