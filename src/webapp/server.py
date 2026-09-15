import os
import sys
import json
import asyncio
import time
import shutil
from pathlib import Path
import base64
import cv2
import numpy as np
import torch
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, File, UploadFile, Form, HTTPException, Body, Header
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from groq import AsyncGroq

# Assicura che src/ sia nel PYTHONPATH
SERVER_DIR = Path(__file__).resolve().parent
SRC_DIR = SERVER_DIR.parent
PROJECT_ROOT = SRC_DIR.parent

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from logic import util, reps_tracker
from models_pytorch import device
from frame import Frame
from services.model_registry import model_registry, LoadedModelEntry
from services.pipeline_runner import RehabPipelineRunner
from services.db_service import db_service, supabase_client
from supabase import AuthApiError
from fastapi import Depends

def get_doctor_auth(authorization: str = Header(None)) -> tuple[str, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token mancante o invalido")
    token = authorization.split(" ")[1]
    
    if not supabase_client:
        raise HTTPException(status_code=500, detail="Supabase client non inizializzato")
        
    try:
        res = supabase_client.auth.get_user(token)
        user = res.user
        if not user:
            raise HTTPException(status_code=401, detail="Utente non trovato")
            
        if user.user_metadata.get("ruolo") != "medico":
            raise HTTPException(status_code=403, detail="Accesso negato: richiesto ruolo medico")
            
        return user.id, token
    except AuthApiError as e:
        print(f"[ERROR] AuthApiError: {e}")
        raise HTTPException(status_code=401, detail="Token invalido o scaduto")
    except Exception as e:
        print(f"[ERROR] Eccezione validazione token: {e}")
        raise HTTPException(status_code=401, detail="Errore di validazione token")

load_dotenv(dotenv_path=SRC_DIR / '.env')

SKIP_INTERVAL = 6

# --- CLIENT GROQ ---
_groq_api_key = os.getenv("GROQ_API_KEY")
groq_client = AsyncGroq(api_key=_groq_api_key) if _groq_api_key else None
if not groq_client:
    print("⚠️  GROQ_API_KEY non trovata: il feedback vocale LLM è disabilitato.")

CORRECTION_COOLDOWN = 5
LLM_INTERVAL = 15
DEFAULT_TARGET_REPS = 5

_KNEE_FORWARD_CORRECTION = ""
_KNEE_FORWARD_SEVERE_RATIO = 1.6
_ARMS_BENT_CORRECTION = ""
_ARMS_BENT_SEVERE_DEFICIT_DEG = 20.0

_SYSTEM_PROMPT_CORREZIONE = (
    "Sei un trainer fitness. Riformula il messaggio di correzione che ti viene dato in modo "
    "naturale, diretto e incoraggiante in italiano. Massimo 10 parole, 1 frase. "
    "Mantieni il significato preciso della correzione — non inventare correzioni diverse. "
    "Rispondi SOLO con la frase riformulata, senza saluti, emoji o prefissi."
)

_SYSTEM_PROMPT_MOTIVAZIONE = (
    "Sei un trainer fitness. Dai un breve incoraggiamento in italiano (massimo 10 parole, 1 frase). "
    "Incita l'utente o ricordagli le ripetizioni mancanti. "
    "Rispondi SOLO con la frase, senza saluti, emoji o prefissi."
)

def _correction_severity(tracker: reps_tracker.ExerciseTracker) -> str | None:
    return None

async def genera_feedback_llm(
    esercizio: str,
    angolo: float,
    reps: int,
    is_correcting: bool,
    correction_phrase: str | None,
    gravita: str | None = None,
) -> str | None:
    if groq_client is None:
        return None
    try:
        rimanenti = max(DEFAULT_TARGET_REPS - reps, 0)
        if is_correcting and correction_phrase:
            system_prompt = _SYSTEM_PROMPT_CORREZIONE
            user_msg = (
                f"Esercizio: {esercizio.replace('_', ' ')}\n"
                f"Correzione da comunicare: \"{correction_phrase}\"\n"
                f"Gravità: {gravita}\n"
                f"Riformula questa correzione specifica in modo naturale e diretto."
            )
        else:
            system_prompt = _SYSTEM_PROMPT_MOTIVAZIONE
            user_msg = (
                f"Esercizio: {esercizio.replace('_', ' ')}\n"
                f"Ripetizioni completate: {reps} su {DEFAULT_TARGET_REPS} (mancano {rimanenti})\n"
                f"Angolo rilevato: {angolo:.1f}°"
            )
        resp = await groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=30,
            temperature=0.8,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️  Groq errore: {e}")
        return None

app = FastAPI(title="AriuFitness & Rehab-AI AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOADS_DIR = PROJECT_ROOT / "uploads"
(UPLOADS_DIR / "videos").mkdir(parents=True, exist_ok=True)
app.mount("/uploads/videos", StaticFiles(directory=str(UPLOADS_DIR / "videos")), name="videos")


# --- SCHEMA REQUEST PYDANTIC PER IL MEDICO ---
class CreateExerciseSchema(BaseModel):
    exercise_id: str
    nome: str
    descrizione: Optional[str] = ""
    categoria: Optional[str] = "Riabilitazione"
    signal_selection_mode: str = "auto"
    doctor_selected_joints: List[str] = []
    expected_reps: Optional[int] = None

class SegmentVideoSchema(BaseModel):
    video_path: str
    signal_selection_mode: Optional[str] = "auto"
    doctor_selected_joints: Optional[List[str]] = []
    expected_reps: Optional[int] = None

class ReviewItemSchema(BaseModel):
    rep_index: int
    accettata: bool
    id: Optional[str] = None
    video_source: Optional[str] = None

class ReviewRepsSchema(BaseModel):
    reviews: List[ReviewItemSchema]

class TrainModelSchema(BaseModel):
    epochs: Optional[int] = 25
    batch_size: Optional[int] = 32
    seed: Optional[int] = 42


# --- ENDPOINT REST PER IL MEDICO & REHAB-AI PIPELINE ---

@app.get("/api/doctor/exercises")
async def get_doctor_exercises(auth_data: tuple[str, str] = Depends(get_doctor_auth)):
    user_id, token = auth_data
    
    # 1. Recupera gli esercizi dal DB
    exercises = db_service.get_doctor_exercises(jwt_token=token)
    
    result = []
    for ex in exercises:
        ex_id = ex["exercise_id"]
        
        # Recupera tutti i dettagli per fare i conteggi
        details = db_service.get_doctor_exercise_details(ex_id, jwt_token=token)
        reps = details.get("reps", [])
        model = details.get("model")
        
        total_reps = len(reps)
        accepted_reps = sum(1 for r in reps if r.get("accettata_medico") is True)
        rejected_reps = sum(1 for r in reps if r.get("confermata_medico") is True and r.get("accettata_medico") is False)
        
        # Conta i video sul filesystem
        video_count = 0
        video_dir = UPLOADS_DIR / "videos" / ex_id
        if video_dir.exists() and video_dir.is_dir():
            video_count = len([f for f in os.listdir(video_dir) if os.path.isfile(video_dir / f)])
            
        result.append({
            "id": ex.get("id"),
            "exercise_id": ex_id,
            "nome": ex.get("nome"),
            "descrizione": ex.get("descrizione"),
            "categoria": ex.get("categoria"),
            "created_at": ex.get("created_at"),
            "video_count": video_count,
            "reps_total": total_reps,
            "reps_accepted": accepted_reps,
            "reps_rejected": rejected_reps,
            "model_status": model.get("status") if model else None,
            "model_version": model.get("version") if model else None
        })
        
    return {"exercises": result}

@app.get("/api/doctor/exercises/{exercise_id}/details")
async def get_doctor_exercise_details(exercise_id: str, auth_data: tuple[str, str] = Depends(get_doctor_auth)):
    user_id, token = auth_data
    
    try:
        details = db_service.get_doctor_exercise_details(exercise_id, jwt_token=token)
        
        # Verifica RLS: se non trova l'esercizio, solleva eccezione
        if not details.get("exercise"):
            raise HTTPException(status_code=404, detail="Esercizio non trovato o accesso negato")
            
        # Recupera video da filesystem
        videos = []
        video_dir = UPLOADS_DIR / "videos" / exercise_id
        if video_dir.exists() and video_dir.is_dir():
            for filename in os.listdir(video_dir):
                if os.path.isfile(video_dir / filename):
                    videos.append({
                        "filename": filename,
                        "url": f"http://localhost:8000/uploads/videos/{exercise_id}/{filename}"
                    })
                    
        reps = details.get("reps", [])
        total_reps = len(reps)
        accepted_reps = sum(1 for r in reps if r.get("accettata_medico") is True)
        rejected_reps = sum(1 for r in reps if r.get("confermata_medico") is True and r.get("accettata_medico") is False)
        
        # Mappa della cache FPS per i video sorgente dell'esercizio
        video_fps_cache: Dict[str, Optional[float]] = {}

        def resolve_video_fps(video_source: Optional[str]) -> Optional[float]:
            if not video_source:
                return None
            if video_source in video_fps_cache:
                return video_fps_cache[video_source]

            fps: Optional[float] = None
            # 1. Prova a leggere l'FPS dal metadata.json generato dalla pipeline
            try:
                video_stem = Path(video_source).stem
                meta_path = UPLOADS_DIR / "runs" / exercise_id / video_stem / "metadata.json"
                if meta_path.exists():
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta_data = json.load(f)
                        raw_fps = float(meta_data.get("fps", 0))
                        if raw_fps > 0:
                            fps = raw_fps
            except Exception as e:
                print(f"[WARN] Impossibile leggere fps da metadata.json per {exercise_id}/{video_source}: {e}")

            # 2. Fallback reale: leggi direttamente dal video originale con OpenCV
            if not fps:
                try:
                    video_file = UPLOADS_DIR / "videos" / exercise_id / video_source
                    if video_file.exists():
                        cap = cv2.VideoCapture(str(video_file))
                        if cap.isOpened():
                            raw_fps = float(cap.get(cv2.CAP_PROP_FPS))
                            cap.release()
                            if raw_fps > 0:
                                fps = raw_fps
                except Exception as e:
                    print(f"[WARN] Fallback OpenCV fallito per {exercise_id}/{video_source}: {e}")

            video_fps_cache[video_source] = fps
            return fps

        # Filtra campi essenziali per la UI e calcola start_sec ed end_sec
        reps_summary_list = []
        for r in reps:
            v_src = r.get("video_source")
            fps = resolve_video_fps(v_src)
            s_frame = r.get("start_frame")
            e_frame = r.get("end_frame")

            start_sec = round(s_frame / fps, 2) if (fps and s_frame is not None) else None
            end_sec = round(e_frame / fps, 2) if (fps and e_frame is not None) else None

            reps_summary_list.append({
                "rep_index": r.get("rep_index"),
                "video_source": v_src,
                "start_frame": s_frame,
                "end_frame": e_frame,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "doctor_validation": r.get("doctor_validation"),
                "accettata_medico": r.get("accettata_medico")
            })
        
        return {
            "exercise": details["exercise"],
            "profile": details["profile"],
            "videos": videos,
            "reps_summary": {
                "total": total_reps,
                "accepted": accepted_reps,
                "rejected": rejected_reps,
                "list": reps_summary_list
            },
            "model": details["model"]
        }
    except Exception as e:
        print(f"[ERROR] Errore in get_doctor_exercise_details: {e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Errore nel recupero dei dettagli dell'esercizio")

@app.get("/api/exercises")
async def get_exercises():
    """Restituisce l'elenco degli esercizi e dei modelli registrati."""
    models = model_registry.get_registered_models()
    return {"exercises": models}


@app.post("/api/doctor/exercises")
async def doctor_create_exercise(payload: CreateExerciseSchema, auth_data: tuple[str, str] = Depends(get_doctor_auth)):
    """
    1. Creazione esercizio e profilo clinico nel DB Supabase (esercizi, exercise_profiles).
    """
    user_id, token = auth_data
    
    exercise_data = {
        "exercise_id": payload.exercise_id,
        "nome": payload.nome,
        "descrizione": payload.descrizione,
        "categoria": payload.categoria,
        "creato_da": user_id
    }
    profile_data = {
        "exercise_id": payload.exercise_id,
        "signal_selection_mode": payload.signal_selection_mode,
        "doctor_selected_joints": payload.doctor_selected_joints,
        "rep_mode": "fixed" if payload.expected_reps else "auto",
        "expected_reps": payload.expected_reps
    }
    
    try:
        result = db_service.create_exercise(exercise_data, profile_data, jwt_token=token)
        return {"status": "success", "data": result}
    except Exception as e:
        print(f"[ERROR] Eccezione backend in create_exercise: {e}")
        raise HTTPException(status_code=500, detail="Errore durante il salvataggio dell'esercizio")


@app.post("/api/doctor/exercises/{exercise_id}/upload-video")
async def doctor_upload_video(exercise_id: str, file: UploadFile = File(...)):
    """
    2. Upload video dell'esercizio per il processamento.
    """
    target_dir = UPLOADS_DIR / "videos" / exercise_id
    target_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = target_dir / file.filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {
        "status": "success",
        "exercise_id": exercise_id,
        "filename": file.filename,
        "video_path": str(file_path)
    }


@app.post("/api/doctor/exercises/{exercise_id}/segment-video")
async def doctor_segment_video(exercise_id: str, payload: SegmentVideoSchema, auth_data: tuple[str, str] = Depends(get_doctor_auth)):
    """
    3. Esegue la pipeline di segmentazione Rehab-AI ed estrazione pose sul video caricato.
       Salva le REP generate nella tabella Supabase `ripetizioni_generate`.
    """
    user_id, token = auth_data
    video_path = Path(payload.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"File video non trovato: {payload.video_path}")

    run_dir = UPLOADS_DIR / "runs" / exercise_id / video_path.stem
    
    res = RehabPipelineRunner.process_video(
        exercise_id=exercise_id,
        video_path=video_path,
        output_dir=run_dir,
        signal_selection_mode=payload.signal_selection_mode or "auto",
        doctor_selected_joints=payload.doctor_selected_joints or [],
        expected_reps=payload.expected_reps
    )
    
    reps = res.get("reps", [])
    print(f"Segmenter produced: {len(reps)} reps for exercise_id={exercise_id}, doctor_user_id={user_id}")

    try:
        saved_reps = db_service.save_generated_reps(exercise_id, str(video_path.name), reps, jwt_token=token)
        print(f"DB saved: {len(saved_reps)} reps for exercise_id={exercise_id}, doctor_user_id={user_id}")
        return {"status": "success", "result": res}
    except Exception as e:
        print(f"[ERROR] Eccezione backend in segment-video (save_generated_reps): {e}")
        raise HTTPException(status_code=500, detail="Errore durante il salvataggio delle ripetizioni")


@app.get("/api/doctor/exercises/{exercise_id}/reps")
async def doctor_get_reps(exercise_id: str, auth_data: tuple[str, str] = Depends(get_doctor_auth)):
    """
    4. Lettura delle REP generate da sottoporre a review del medico.
    """
    user_id, token = auth_data
    try:
        reps = db_service.get_generated_reps(exercise_id, jwt_token=token)
        print(f"GET /reps returned: {len(reps)} reps for exercise_id={exercise_id}, doctor_user_id={user_id}")
        return {"exercise_id": exercise_id, "reps": reps}
    except Exception as e:
        print(f"[ERROR] Eccezione backend in get_reps: {e}")
        raise HTTPException(status_code=500, detail="Errore durante il caricamento delle ripetizioni")


@app.post("/api/doctor/exercises/{exercise_id}/reps/review")
async def doctor_review_reps(exercise_id: str, payload: ReviewRepsSchema, auth_data: tuple[str, str] = Depends(get_doctor_auth)):
    """
    5. Approvazione / Rifiuto delle REP proposte da parte del medico.
    """
    user_id, token = auth_data
    reviews = [r.dict() for r in payload.reviews]
    updated_count = db_service.update_rep_reviews(exercise_id, reviews, jwt_token=token)
    
    # Restituisci errore se non aggiorna niente
    if updated_count == 0 and len(payload.reviews) > 0:
        print(f"[ERROR] Nessuna riga aggiornata in update_rep_reviews per exercise_id={exercise_id}")
        raise HTTPException(status_code=400, detail="Nessuna riga aggiornata (possibile mismatch ID o blocco RLS)")
    
    return {"status": "success", "exercise_id": exercise_id, "updated": updated_count, "accepted": sum(1 for r in reviews if r["accettata"])}


@app.post("/api/doctor/exercises/{exercise_id}/train")
async def doctor_train_model(exercise_id: str, payload: TrainModelSchema, auth_data: tuple[str, str] = Depends(get_doctor_auth)):
    """
    6. Avvio training LSTM: usa SOLO le REP accettate dal medico (`accettata_medico = True`),
       applica data augmentation, addestra `TwoBranchLSTM`, salva in
       `models/production_models/<exercise_id>/` e registra il modello nel DB `exercise_models`.
    """
    user_id, token = auth_data
    # Passiamo il token JWT al DB per leggere il contesto isolato per questo medico
    all_reps = db_service.get_generated_reps(exercise_id, jwt_token=token)
    accepted_indices = [r["rep_index"] for r in all_reps if r.get("accettata_medico") is True]

    if not accepted_indices:
        raise HTTPException(
            status_code=400,
            detail="Nessuna REP accettata dal medico. Accetta almeno 1 REP prima di avviare il training."
        )

    run_dir = UPLOADS_DIR / "runs" / exercise_id
    output_model_dir = PROJECT_ROOT / "models" / "production_models" / exercise_id

    res = RehabPipelineRunner.train_model_from_accepted_reps(
        exercise_id=exercise_id,
        run_dir=run_dir,
        accepted_rep_indices=accepted_indices,
        output_model_dir=output_model_dir,
        epochs=payload.epochs or 25,
        batch_size=payload.batch_size or 32,
        seed=payload.seed or 42
    )

    model_record = db_service.save_exercise_model(
        exercise_id=exercise_id,
        model_uri=res["model_path"],
        normalization_stats_uri=res["stats_path"],
        metrics=res["metrics"],
        config=res["config"],
        version=1,
        status="active",
        jwt_token=token
    )

    model_registry.load_model(exercise_id)

    return {"status": "success", "train_result": res, "db_model_record": model_record}


import requests

@app.post("/api/patient/session/start")
def start_session(assignment: dict = Body(...), authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Token missing")
    assignment_id = assignment.get("assignment_id")
    
    anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")
    headers = {
        "apikey": anon_key,
        "Authorization": authorization if authorization.startswith("Bearer") else f"Bearer {authorization}"
    }
    url = f"{os.getenv('SUPABASE_URL')}/rest/v1/assigned_exercises?id=eq.{assignment_id}&select=*"
    
    try:
        auth_url = f"{os.getenv('SUPABASE_URL')}/auth/v1/user"
        auth_resp = requests.get(auth_url, headers=headers, timeout=5)
        if auth_resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Token non valido")
        uid = auth_resp.json().get("id")

        profili_url = f"{os.getenv('SUPABASE_URL')}/rest/v1/profili?id=eq.{uid}&select=ruolo,id"
        profili_resp = requests.get(profili_url, headers=headers, timeout=5)
        if profili_resp.status_code != 200 or not profili_resp.json():
            raise HTTPException(status_code=403, detail="Profilo non trovato o non autorizzato")
        
        profilo = profili_resp.json()[0]
        if profilo.get("ruolo") != "paziente":
            raise HTTPException(status_code=403, detail="Solo i pazienti possono avviare questa sessione")
        
        user_id = profilo.get("id")

        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code != 200 or not resp.json():
            print("ERR /api/patient/session/start (assigned_exercises):", resp.status_code, resp.text)
            raise HTTPException(status_code=403, detail="Assignment non trovato o non autorizzato")
        
        data = resp.json()[0]
        if data.get("patient_id") != user_id:
            raise HTTPException(status_code=403, detail="L'assignment non appartiene a questo paziente")
        
        model_id = data.get("model_id")
        
        # Carica il service key se disponibile
        service_key = os.getenv("SUPABASE_SERVICE_KEY")
        if not service_key:
            from dotenv import load_dotenv
            from pathlib import Path
            env_svc = Path(__file__).parent.parent.parent / '.env.service'
            if env_svc.exists():
                load_dotenv(dotenv_path=env_svc)
                service_key = os.getenv("SUPABASE_SERVICE_KEY")
        
        svc_headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}"
        } if service_key else headers

        # Recupera il modello con il service key
        model_data = None
        if service_key and model_id:
            try:
                m_url = f"{os.getenv('SUPABASE_URL')}/rest/v1/exercise_models?id=eq.{model_id}&select=*"
                m_resp = requests.get(m_url, headers=svc_headers, timeout=5)
                if m_resp.status_code == 200 and m_resp.json():
                    model_data = m_resp.json()[0]
            except Exception as me:
                print(f"[WARN] Errore recupero model_data: {me}")
        if not model_data or model_data.get("status") not in ("active", "production"):
            raise HTTPException(status_code=400, detail="Modello non attivo o non valido")
        
        # Recupera il nome leggibile dell'esercizio dalla tabella esercizi (con fallback sicuro)
        exercise_name = data.get("exercise_id", "Esercizio")
        if service_key:
            try:
                ex_url = f"{os.getenv('SUPABASE_URL')}/rest/v1/esercizi?exercise_id=eq.{data['exercise_id']}&select=nome"
                ex_resp = requests.get(ex_url, headers=svc_headers, timeout=3)
                if ex_resp.status_code == 200 and ex_resp.json():
                    exercise_name = ex_resp.json()[0].get("nome") or exercise_name
            except Exception as ee:
                print(f"[WARN] Errore risoluzione nome esercizio: {ee}")

        # Recupera video associati all'exercise_id in ordine alfabetico deterministico
        exercise_id = data["exercise_id"]
        video_dir = UPLOADS_DIR / "videos" / exercise_id
        videos = []
        if video_dir.exists() and video_dir.is_dir():
            filenames = sorted([f for f in os.listdir(video_dir) if os.path.isfile(video_dir / f)])
            for f in filenames:
                videos.append({
                    "filename": f,
                    "url": f"http://127.0.0.1:8000/uploads/videos/{exercise_id}/{f}"
                })
        
        return {
            "status": "ok",
            "exercise_id": exercise_id,
            "exercise_name": exercise_name,
            "target_reps": data.get("target_reps", 5),
            "videos": videos,
            "reference_video_url": videos[0]["url"] if videos else None
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


class SessionCompleteRequest(BaseModel):
    assignment_id: str
    reps_completed: int


def _record_patient_rehab_session(payload: SessionCompleteRequest, authorization: str, force_status: Optional[str] = None):
    if not authorization:
        raise HTTPException(status_code=401, detail="Token missing")
    assignment_id = payload.assignment_id
    reps_completed = payload.reps_completed
    
    anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")
    headers = {
        "apikey": anon_key,
        "Authorization": authorization if authorization.startswith("Bearer") else f"Bearer {authorization}"
    }
    
    try:
        # 1. Verifica token utente
        auth_url = f"{os.getenv('SUPABASE_URL')}/auth/v1/user"
        auth_resp = requests.get(auth_url, headers=headers, timeout=5)
        if auth_resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Token non valido")
        uid = auth_resp.json().get("id")

        # 2. Verifica ruolo paziente
        profili_url = f"{os.getenv('SUPABASE_URL')}/rest/v1/profili?id=eq.{uid}&select=ruolo,id"
        profili_resp = requests.get(profili_url, headers=headers, timeout=5)
        if profili_resp.status_code != 200 or not profili_resp.json():
            raise HTTPException(status_code=403, detail="Profilo non trovato o non autorizzato")
        
        profilo = profili_resp.json()[0]
        if profilo.get("ruolo") != "paziente":
            raise HTTPException(status_code=403, detail="Solo i pazienti possono registrare la sessione")
        
        user_id = profilo.get("id")

        # 3. Leggi assigned_exercises
        url = f"{os.getenv('SUPABASE_URL')}/rest/v1/assigned_exercises?id=eq.{assignment_id}&select=*"
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code != 200 or not resp.json():
            raise HTTPException(status_code=403, detail="Assignment non trovato o non autorizzato")
        
        data = resp.json()[0]
        if data.get("patient_id") != user_id:
            raise HTTPException(status_code=403, detail="L'assignment non appartiene a questo paziente")
        
        patient_id = data.get("patient_id")
        doctor_id = data.get("doctor_id")
        exercise_id = data.get("exercise_id")
        target_reps = data.get("target_reps", 5)

        # 4. Determina status ('completed' o 'interrupted')
        if force_status:
            status = force_status
        else:
            status = "completed" if reps_completed >= target_reps else "interrupted"

        # 5. Evita duplicati accidentali ravvicinati (< 15 secondi per lo stesso assignment e stesso status)
        check_url = f"{os.getenv('SUPABASE_URL')}/rest/v1/rehab_sessions?assignment_id=eq.{assignment_id}&patient_id=eq.{patient_id}&order=completed_at.desc&limit=1"
        check_resp = requests.get(check_url, headers=headers, timeout=5)
        if check_resp.status_code == 200 and check_resp.json():
            latest = check_resp.json()[0]
            from datetime import datetime, timezone
            try:
                comp_str = latest.get("completed_at") or latest.get("created_at")
                if comp_str:
                    comp_time = datetime.fromisoformat(comp_str.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    if (now - comp_time).total_seconds() < 15 and latest.get("status") == status:
                        return {
                            "status": "ok",
                            "message": f"Sessione {status} già registrata recentemente",
                            "session_id": latest.get("id"),
                            "assignment_id": assignment_id,
                            "reps_completed": latest.get("reps_completed", reps_completed),
                            "target_reps": target_reps,
                            "session_status": status
                        }
            except Exception:
                pass

        # 6. Inserisci in rehab_sessions
        session_body = {
            "assignment_id": assignment_id,
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "exercise_id": exercise_id,
            "reps_completed": reps_completed,
            "target_reps": target_reps,
            "status": status
        }
        
        insert_url = f"{os.getenv('SUPABASE_URL')}/rest/v1/rehab_sessions"
        insert_headers = {
            **headers,
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        insert_resp = requests.post(insert_url, headers=insert_headers, json=session_body, timeout=5)
        if insert_resp.status_code not in (200, 201):
            print(f"[ERR] Errore inserimento rehab_sessions: {insert_resp.status_code} {insert_resp.text}")
            raise HTTPException(status_code=500, detail="Impossibile registrare la sessione riabilitativa nel database")
        
        inserted_row = insert_resp.json()[0] if insert_resp.json() else session_body
        return {
            "status": "ok",
            "message": f"Sessione {status} registrata con successo",
            "session_id": inserted_row.get("id"),
            "assignment_id": assignment_id,
            "reps_completed": reps_completed,
            "target_reps": target_reps,
            "session_status": status
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/patient/session/complete")
def complete_session(payload: SessionCompleteRequest, authorization: str = Header(None)):
    return _record_patient_rehab_session(payload, authorization, force_status="completed")


@app.post("/api/patient/session/interrupt")
def interrupt_session(payload: SessionCompleteRequest, authorization: str = Header(None)):
    return _record_patient_rehab_session(payload, authorization, force_status="interrupted")

# --- WEBSOCKET E INFERENZA LIVE DINAMICA ---

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connesso al canale WebSocket.")

    tracker = reps_tracker.ExerciseTracker()
    raw_history_buffer: list = []
    max_history_length = 50
    is_fully_visible_at_start = False

    selected_exercise: str | None = None
    loaded_entry: LoadedModelEntry | None = None

    llm_task = None
    pending_llm_feedback: tuple | None = None
    llm_feedback_id: int = 0
    last_feedback_time: float = time.time()
    llm_enabled: bool = True
    target_reps: int = 0

    INDICI_CORPO = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
    MIN_FRAMES = (8 - 1) * SKIP_INTERVAL + 1
    SOGLIA_STASI = 0.0001

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if "selected_exercise" in message:
                nuovo = message["selected_exercise"]
                if nuovo == selected_exercise:
                    continue

                selected_exercise = nuovo
                llm_enabled = bool(message.get("llm_enabled", True))
                print(f"\nEsercizio selezionato: '{selected_exercise}' (LLM {'ON' if llm_enabled else 'OFF'})")

                loaded_entry = model_registry.load_model(selected_exercise)
                if loaded_entry is None:
                    print(f"⚠️  AVVISO: nessun modello addestrato nel registro per '{selected_exercise}'.")

                tracker = reps_tracker.ExerciseTracker()
                raw_history_buffer = []
                is_fully_visible_at_start = False

                if llm_task is not None:
                    llm_task.cancel()
                    llm_task = None
                pending_llm_feedback = None
                last_feedback_time = time.time()
                continue
                
            if "assignment_id" in message and "token" in message:
                assignment_id = message["assignment_id"]
                token = message["token"]
                llm_enabled = bool(message.get("llm_enabled", True))
                
                anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")
                headers = {
                    "apikey": anon_key,
                    "Authorization": token if token.startswith("Bearer") else f"Bearer {token}"
                }
                url = f"{os.getenv('SUPABASE_URL')}/rest/v1/assigned_exercises?id=eq.{assignment_id}&select=*"
                try:
                    import requests
                    
                    auth_url = f"{os.getenv('SUPABASE_URL')}/auth/v1/user"
                    auth_resp = requests.get(auth_url, headers=headers)
                    if auth_resp.status_code != 200:
                        print(f"⚠️ AVVISO WS: Token non valido.")
                        continue
                    uid = auth_resp.json().get("id")

                    profili_url = f"{os.getenv('SUPABASE_URL')}/rest/v1/profili?id=eq.{uid}&select=ruolo,id"
                    profili_resp = requests.get(profili_url, headers=headers)
                    if profili_resp.status_code != 200 or not profili_resp.json():
                        print(f"⚠️ AVVISO WS: Profilo non trovato o non autorizzato.")
                        continue
                    
                    profilo = profili_resp.json()[0]
                    if profilo.get("ruolo") != "paziente":
                        print(f"⚠️ AVVISO WS: Solo i pazienti possono avviare questa sessione.")
                        continue
                    
                    user_id = profilo.get("id")

                    resp = requests.get(url, headers=headers)
                    if resp.status_code == 200 and resp.json():
                        data = resp.json()[0]
                        if data.get("patient_id") != user_id:
                            print(f"⚠️ AVVISO WS: L'assignment non appartiene a questo paziente.")
                            continue
                            
                        model_id = data.get("model_id")
                        
                        service_key = os.getenv("SUPABASE_SERVICE_KEY")
                        if not service_key:
                            from dotenv import load_dotenv
                            from pathlib import Path
                            env_svc = Path(__file__).parent.parent.parent / '.env.service'
                            if env_svc.exists():
                                load_dotenv(dotenv_path=env_svc)
                                service_key = os.getenv("SUPABASE_SERVICE_KEY")
                        
                        model_data = None
                        if service_key and model_id:
                            svc_headers = {
                                "apikey": service_key,
                                "Authorization": f"Bearer {service_key}"
                            }
                            m_url = f"{os.getenv('SUPABASE_URL')}/rest/v1/exercise_models?id=eq.{model_id}&select=*"
                            m_resp = requests.get(m_url, headers=svc_headers)
                            if m_resp.status_code == 200 and m_resp.json():
                                model_data = m_resp.json()[0]

                        if model_data and model_data.get("status") in ("active", "production"):
                            selected_exercise = data["exercise_id"]
                            target_reps = data.get("target_reps", 0)
                            print(f"\n[WS] Caricamento dinamico: model_id '{model_id}' per '{selected_exercise}' (LLM {'ON' if llm_enabled else 'OFF'})")
                            loaded_entry = model_registry.load_model_by_row(model_id, model_data)
                            if loaded_entry is None:
                                print(f"⚠️ AVVISO: impossibile caricare il modello autorizzato {model_id}.")
                        else:
                            print(f"⚠️ AVVISO: modello non attivo per assignment {assignment_id}.")
                    else:
                        print(f"⚠️ AVVISO: assignment {assignment_id} non trovato o non autorizzato.")
                except Exception as e:
                    print(f"Errore WS fetch assignment: {e}")

                tracker = reps_tracker.ExerciseTracker()
                raw_history_buffer = []
                is_fully_visible_at_start = False

                if llm_task is not None:
                    llm_task.cancel()
                    llm_task = None
                pending_llm_feedback = None
                last_feedback_time = time.time()
                continue

            image_base64 = message.get("image")
            if not image_base64:
                continue

            if loaded_entry is None:
                nome_leggibile = (selected_exercise or "").replace("_", " ").title()
                await websocket.send_text(json.dumps({
                    "status": "no_model",
                    "frames_stacked": 0,
                    "exercise": "Modello non disponibile",
                    "confidence": 0.0,
                    "reps": 0,
                    "target_reps": target_reps,
                    "phrase": f"L'esercizio '{nome_leggibile}' non ha un modello addestrato attivo." if selected_exercise else "Seleziona un esercizio."
                }))
            if "," in image_base64:
                image_base64 = image_base64.split(",")[1]
            frame_bgr = cv2.imdecode(
                np.frombuffer(base64.b64decode(image_base64), dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
            if frame_bgr is None:
                continue

            frame_obj = Frame(frame_bgr)
            frame_obj.interpolate_keypoints(None, None)
            frame_obj.extract_angles()

            kp_data = frame_obj.process_keypoints()
            an_data = frame_obj.process_angles()
            landmarks = frame_obj.get_landmarks()

            pose_detected = bool(landmarks and len(landmarks) >= 13)
            num_landmarks = len(landmarks) if landmarks else 0
            vis_media = float(np.mean([getattr(lm, "visibility", 1.0) for lm in landmarks])) if landmarks else 0.0

            if not pose_detected:
                raw_history_buffer.clear()
                tracker.update(selected_exercise, None, 0.0)
                await websocket.send_text(json.dumps({
                    "status": "buffering",
                    "frames_stacked": 0,
                    "max_frames": 8,
                    "exercise": selected_exercise or "In attesa...",
                    "confidence": 0.0,
                    "reps": tracker.get_reps(),
                    "target_reps": target_reps,
                    "phrase": tracker.get_phrase(),
                    "landmarks": [],
                    "llm_feedback": None,
                    "llm_feedback_id": llm_feedback_id,
                }))
                continue

            raw_history_buffer.append((kp_data, an_data))
            if len(raw_history_buffer) > 32:
                raw_history_buffer.pop(0)

            landmarks_payload = [
                {"x": float(lm.x), "y": float(lm.y), "visibility": float(getattr(lm, "visibility", 1.0))}
                for lm in landmarks
            ] if landmarks else []

            if len(raw_history_buffer) < 8:
                await websocket.send_text(json.dumps({
                    "status": "buffering",
                    "frames_stacked": len(raw_history_buffer),
                    "max_frames": 8,
                    "exercise": selected_exercise or "In attesa...",
                    "confidence": 0.0,
                    "reps": tracker.get_reps(),
                    "target_reps": target_reps,
                    "phrase": f"Inizializzazione... ({len(raw_history_buffer)}/8)",
                    "landmarks": landmarks_payload,
                }))
                continue

            sampled = raw_history_buffer[-8:]

            # --- INFERENZA DINAMICA CON IL TUO MODELLO PHYSIOVISION E NORMALIZZAZIONE Z-SCORE ---
            raw_kp_seq = np.expand_dims(np.array([f[0] for f in sampled]), 0) # (1, 8, 36)
            raw_ang_seq = np.expand_dims(np.array([f[1] for f in sampled]), 0) # (1, 8, 8)

            norm_kp_seq, norm_ang_seq = loaded_entry.normalize(raw_kp_seq, raw_ang_seq)

            t_kp = torch.tensor(norm_kp_seq, dtype=torch.float32).to(device)
            t_ang = torch.tensor(norm_ang_seq, dtype=torch.float32).to(device)

            confidence_percentage = loaded_entry.predict_confidence(t_kp, t_ang)

            # Aggiorna la macchina a stati 0 -> 1 -> 0 con la confidenza del modello
            tracker.update(selected_exercise, landmarks, confidence_percentage)

            current_time = time.time()
            if llm_task is not None and llm_task.done():
                try:
                    result = llm_task.result()
                    if result:
                        llm_feedback_id += 1
                        pending_llm_feedback = (result, llm_feedback_id)
                except Exception:
                    pass
                llm_task = None

            if (
                groq_client is not None
                and llm_enabled
                and confidence_percentage > 70.0
                and llm_task is None
                and tracker.get_last_angle() is not None
                and (
                    (tracker.get_is_correcting() and current_time - last_feedback_time >= CORRECTION_COOLDOWN)
                    or (current_time - last_feedback_time >= LLM_INTERVAL)
                )
            ):
                gravita = _correction_severity(tracker) if tracker.get_is_correcting() else None
                last_feedback_time = current_time
                llm_task = asyncio.create_task(
                    genera_feedback_llm(
                        selected_exercise,
                        tracker.get_last_angle(),
                        tracker.get_reps(),
                        tracker.get_is_correcting(),
                        tracker.get_last_correction_phrase(),
                        gravita,
                    )
                )

            if pending_llm_feedback is not None:
                llm_text, llm_id = pending_llm_feedback
                pending_llm_feedback = None
            else:
                llm_text = None
                llm_id = llm_feedback_id

            await websocket.send_text(json.dumps({
                "status": "predicted",
                "frames_stacked": 8,
                "exercise": selected_exercise,
                "confidence": confidence_percentage,
                "reps": tracker.get_reps(),
                "target_reps": target_reps,
                "phrase": tracker.get_phrase(),
                "landmarks": landmarks_payload,
                "llm_feedback": llm_text,
                "llm_feedback_id": llm_id,
            }))

    except WebSocketDisconnect:
        print("Client disconnesso.")
    except Exception as e:
        print(f"Errore nel loop WebSocket: {e}")
