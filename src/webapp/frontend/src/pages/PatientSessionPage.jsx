import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { supabase } from '../SupabaseClient';
import { usePrediction } from '../context/PredictionContext';
import FitnessClassifier from '../components/FitnessClassifier';
import { API_BASE_URL } from '../config/api';
import './PatientSessionPage.css';

function PatientSessionPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { prediction, setPrediction } = usePrediction();
  
  // 1. Recupero assignmentId: prioritariamente da Query Parameter URL (?assignmentId=...), con fallback su location.state
  const queryParams = new URLSearchParams(location.search);
  const urlAssignmentId = queryParams.get('assignmentId') || queryParams.get('assignment_id');
  const stateAssignmentId = location.state?.assignment_id || location.state?.assignmentId;
  const assignmentId = urlAssignmentId || stateAssignmentId || null;

  const [sessionInfo, setSessionInfo] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [sessionToken, setSessionToken] = useState(null);
  const [saveStatus, setSaveStatus] = useState({ saved: false, error: null });
  const hasSavedRef = useRef(false);
  
  const [isEnding, setIsEnding] = useState(false);
  
  const reps = prediction.reps || 0;
  const phrase = prediction.phrase || "Inquadrati per iniziare l'esercizio.";
  const confidence = prediction.confidence || 0;

  const targetReps = sessionInfo?.target_reps;
  const isCompleted = Boolean(targetReps && targetReps > 0 && reps >= targetReps);

  // Gestione fine / interruzione sessione
  const handleEndSession = async () => {
    if (isEnding) return;

    // Se la sessione non è ancora completata (reps < targetReps), registra 'interrupted'
    if (!isCompleted && sessionToken && assignmentId && !hasSavedRef.current) {
      hasSavedRef.current = true;
      setIsEnding(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/patient/session/interrupt`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${sessionToken}`
          },
          body: JSON.stringify({
            assignment_id: assignmentId,
            reps_completed: reps
          })
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          console.warn("[SESSION INTERRUPT] Errore salvataggio:", errData.detail);
        } else {
          const result = await response.json();
          console.log("[SESSION INTERRUPT] Sessione interrotta registrata con successo:", result);
        }
      } catch (err) {
        console.error("[SESSION INTERRUPT] Errore chiamata endpoint:", err.message);
      }
    }

    navigate('/paziente/esercizi');
  };

  useEffect(() => {
    if (!assignmentId) {
      setError("Nessun esercizio selezionato. Torna alla dashboard per selezionare un esercizio.");
      setLoading(false);
      return;
    }

    const initSession = async () => {
      try {
        setLoading(true);
        setError('');

        // 2. Refresh / validazione sessione Supabase per ottenere un access_token fresco e non scaduto
        let token = null;
        try {
          const { data: refreshData, error: refreshError } = await supabase.auth.refreshSession();
          if (!refreshError && refreshData?.session?.access_token) {
            token = refreshData.session.access_token;
          }
        } catch (rErr) {
          console.warn("Refresh session non riuscito, fallback su getSession:", rErr);
        }

        if (!token) {
          const { data: sessionData } = await supabase.auth.getSession();
          token = sessionData?.session?.access_token;
        }

        if (!token) {
          throw new Error("Sessione scaduta. Accedi nuovamente per avviare la sessione.");
        }

        // Salva il token fresco per il WebSocket
        setSessionToken(token);

        // 3. Chiama endpoint FastAPI backend per inizializzare e verificare l'esercizio
        const response = await fetch(`${API_BASE_URL}/api/patient/session/start`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            assignment_id: assignmentId
          })
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || `Impossibile avviare la sessione (${response.status})`);
        }

        const data = await response.json();
        setSessionInfo(data);
      } catch (err) {
        console.error("Errore init session:", err);
        setError(err.message || "Impossibile avviare la sessione riabilitativa.");
      } finally {
        setLoading(false);
      }
    };

    initSession();
    
    // Pulizia prediction context all'unmount
    return () => setPrediction({});
  }, [assignmentId, setPrediction]);

  // Salvataggio persistente del completamento della sessione nel database
  useEffect(() => {
    if (isCompleted && !hasSavedRef.current && sessionToken && assignmentId) {
      hasSavedRef.current = true;
      const saveSessionCompletion = async () => {
        try {
          const response = await fetch(`${API_BASE_URL}/api/patient/session/complete`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${sessionToken}`
            },
            body: JSON.stringify({
              assignment_id: assignmentId,
              reps_completed: reps
            })
          });

          if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || "Errore salvataggio sessione nel database");
          }

          const result = await response.json();
          console.log("[SESSION COMPLETE] Sessione registrata con successo:", result);
          setSaveStatus({ saved: true, error: null });
        } catch (err) {
          console.error("[SESSION COMPLETE] Errore salvataggio completamento:", err.message);
          setSaveStatus({
            saved: false,
            error: "Sessione completata, ma il salvataggio non è riuscito. Riprova."
          });
        }
      };

      saveSessionCompletion();
    }
  }, [isCompleted, sessionToken, assignmentId, reps]);

  const exerciseDisplayName = sessionInfo?.exercise_name || location.state?.exercise_name || sessionInfo?.exercise_id || '';

  if (loading) {
    return (
      <div style={{ padding: '60px 20px', textAlign: 'center', color: '#5f6f67', fontFamily: "'Inter', system-ui, sans-serif" }}>
        <div style={{ fontSize: '1.2rem', fontWeight: '600' }}>Inizializzazione sessione riabilitativa in corso…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '60px 20px', maxWidth: '600px', margin: '40px auto', textAlign: 'center', background: '#ffffff', border: '1.5px solid #ef9a9a', borderRadius: '20px', boxShadow: '0 8px 24px rgba(0,0,0,0.06)', fontFamily: "'Inter', system-ui, sans-serif" }}>
        <div style={{ fontSize: '2.5rem', marginBottom: '12px' }}>⚠️</div>
        <h3 style={{ color: '#c62828', margin: '0 0 10px', fontSize: '1.3rem' }}>Errore avvio sessione</h3>
        <p style={{ color: '#5f6f67', margin: '0 0 24px', lineHeight: 1.5 }}>{error}</p>
        <button 
          onClick={handleEndSession} 
          style={{ 
            padding: '12px 26px', 
            borderRadius: '12px', 
            border: 'none', 
            backgroundColor: '#4d7c5f', 
            color: 'white', 
            fontWeight: '700', 
            cursor: 'pointer',
            boxShadow: '0 4px 12px rgba(77, 124, 95, 0.2)'
          }}
        >
          ← Torna ai miei esercizi
        </button>
      </div>
    );
  }

  if (isCompleted) {
    return (
      <div style={{ padding: '60px 20px', maxWidth: '600px', margin: '40px auto', textAlign: 'center', background: '#ffffff', border: '1.5px solid rgba(122, 171, 138, 0.35)', borderRadius: '24px', boxShadow: '0 12px 36px rgba(77, 124, 95, 0.12)', fontFamily: "'Inter', system-ui, sans-serif" }}>
        <div style={{ width: '72px', height: '72px', margin: '0 auto 20px', borderRadius: '50%', backgroundColor: '#e8f5e9', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '2.2rem', color: '#2e7d32' }}>
          ✓
        </div>
        <h2 style={{ color: '#2e7d32', margin: '0 0 8px', fontSize: '1.8rem', fontWeight: '800' }}>Sessione completata</h2>
        {exerciseDisplayName && (
          <div style={{ color: '#5f6f67', margin: '0 0 6px', fontSize: '1.05rem' }}>
            Esercizio: <strong style={{ color: '#2d3748', textTransform: 'capitalize' }}>{exerciseDisplayName}</strong>
          </div>
        )}
        <p style={{ color: '#5f6f67', margin: '0 0 24px', fontSize: '1rem', lineHeight: 1.5 }}>
          Hai completato tutte le ripetizioni previste. Ottimo lavoro.
        </p>
        
        <div style={{ backgroundColor: '#f4f8f5', border: '1px solid #d0e5d8', padding: '16px 28px', borderRadius: '16px', display: 'inline-block', marginBottom: '24px' }}>
          <span style={{ fontSize: '1rem', color: '#5f6f67', fontWeight: '600' }}>REP completate: </span>
          <span style={{ fontSize: '1.4rem', fontWeight: '800', color: '#2e7d32' }}>
            {reps} / {targetReps}
          </span>
        </div>

        {saveStatus.error && (
          <div style={{ color: '#c62828', backgroundColor: '#ffebee', border: '1px solid #ffcdd2', padding: '10px 16px', borderRadius: '10px', margin: '0 auto 24px', maxWidth: '440px', fontSize: '0.9rem', fontWeight: '500' }}>
            {saveStatus.error}
          </div>
        )}

        <div>
          <button 
            onClick={handleEndSession} 
            style={{ 
              padding: '14px 32px', 
              borderRadius: '14px', 
              border: 'none', 
              backgroundColor: '#4d7c5f', 
              color: 'white', 
              fontWeight: '700', 
              fontSize: '1rem',
              cursor: 'pointer',
              boxShadow: '0 4px 14px rgba(77, 124, 95, 0.25)',
              transition: 'transform 0.1s, background-color 0.15s'
            }}
          >
            Torna ai miei esercizi
          </button>
        </div>
      </div>
    );
  }

  const referenceVideoUrl = sessionInfo?.reference_video_url || (sessionInfo?.videos && sessionInfo.videos[0]?.url) || null;
  const displayReps = targetReps && targetReps > 0 ? Math.min(reps, targetReps) : reps;

  return (
    <div className="patient-session-container">
      
      {/* Header Sessione Live */}
      <div className="patient-session-header">
        <div>
          <h2 style={{ margin: 0, color: '#4d7c5f', fontSize: '1.4rem' }}>Sessione Live PhysioVision</h2>
          <p style={{ margin: '4px 0 0', color: '#5f6f67', fontSize: '0.95rem' }}>
            Esercizio: <strong style={{ color: '#2d3748', textTransform: 'capitalize' }}>{exerciseDisplayName || 'Inizializzazione…'}</strong>
          </p>
        </div>
        <button 
          onClick={handleEndSession}
          disabled={isEnding}
          style={{ padding: '10px 22px', borderRadius: '10px', border: '1.5px solid #b8d9c5', backgroundColor: '#fff', color: '#5f6f67', cursor: isEnding ? 'wait' : 'pointer', fontWeight: '700', fontSize: '0.9rem', transition: 'background 0.15s', opacity: isEnding ? 0.7 : 1 }}
        >
          {isEnding ? 'Salvataggio…' : 'Termina sessione'}
        </button>
      </div>

      {/* Riquadri Affiancati Fissi (~50%/50% su Desktop, 1 colonna su Smartphone <= 700px) */}
      <div className="patient-session-video-grid">
        
        {/* SINISTRA: Video di Riferimento */}
        <div className="patient-session-video-card">
          <div className="patient-session-card-header">
            <span>Video Guida di Riferimento</span>
            <span style={{ fontSize: '0.75rem', backgroundColor: '#4d7c5f', padding: '2px 8px', borderRadius: '6px', fontWeight: '600' }}>Riferimento</span>
          </div>
          
          <div className="patient-session-card-media-wrapper">
            {referenceVideoUrl ? (
              <video
                src={referenceVideoUrl}
                autoPlay
                loop
                muted
                playsInline
                controls
                className="patient-session-media-video"
              />
            ) : (
              <div className="patient-session-placeholder">
                <div style={{ fontSize: '2.8rem', marginBottom: '10px' }}>📹</div>
                <div style={{ fontSize: '1.05rem', fontWeight: '700', color: '#e0e0e0' }}>Video di riferimento non disponibile</div>
                <div style={{ fontSize: '0.85rem', marginTop: '6px', color: '#8fa99c' }}>Esegui l'esercizio seguendo le indicazioni</div>
              </div>
            )}
          </div>
        </div>

        {/* DESTRA: Tua Webcam Live */}
        <div className="patient-session-webcam-card">
          <div className="patient-session-card-header">
            <span>Tua Webcam Live</span>
            <span style={{ fontSize: '0.75rem', backgroundColor: '#2e7d32', padding: '2px 8px', borderRadius: '6px', fontWeight: '600' }}>AI Attiva</span>
          </div>

          <div className="patient-session-card-media-wrapper">
            {sessionInfo && sessionToken && (
              <FitnessClassifier 
                selectedExercise={sessionInfo.exercise_id} 
                assignmentId={assignmentId}
                sessionToken={sessionToken}
                isCountingActive={true}
                isExerciseFinished={isCompleted}
                reps={reps}
                targetReps={sessionInfo.target_reps}
              />
            )}
          </div>
        </div>

      </div>

      {/* Stats e Feedback Area */}
      <div className="patient-session-stats-grid">
        <div style={{ backgroundColor: '#fff', border: '1.5px solid rgba(122, 171, 138, 0.22)', padding: '20px 24px', borderRadius: '18px', boxShadow: '0 4px 14px rgba(77, 124, 95, 0.06)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h3 style={{ margin: '0 0 4px', color: '#5f6f67', fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Ripetizioni</h3>
            <div style={{ fontSize: '2.6rem', fontWeight: '800', color: '#4d7c5f', lineHeight: 1 }}>
              {displayReps} <span style={{ fontSize: '1.3rem', color: '#8fa99c' }}>/ {sessionInfo?.target_reps}</span>
            </div>
          </div>
          <div style={{ fontSize: '2rem', opacity: 0.7 }}>🎯</div>
        </div>

        <div style={{ backgroundColor: '#fff', border: '1.5px solid rgba(122, 171, 138, 0.22)', padding: '20px 24px', borderRadius: '18px', boxShadow: '0 4px 14px rgba(77, 124, 95, 0.06)' }}>
          <h3 style={{ margin: '0 0 6px', color: '#5f6f67', fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Feedback Live</h3>
          <p style={{ fontSize: '1.1rem', fontWeight: '600', color: confidence > 70 ? '#2e7d32' : '#f57c00', margin: 0, lineHeight: 1.4 }}>
            {phrase}
          </p>
        </div>
      </div>
      
    </div>
  );
}

export default PatientSessionPage;
