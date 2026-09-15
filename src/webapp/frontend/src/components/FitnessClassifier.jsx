import React, { useEffect, useRef, useState } from 'react';
import { usePrediction } from '../context/PredictionContext';
import { getWsStreamUrl } from '../config/api';
import './FitnessClassifier.css';

const SKELETON_CONNECTIONS = [
  // Torso e Spalle
  [11, 12], [11, 23], [12, 24], [23, 24],
  // Braccio sinistro
  [11, 13], [13, 15],
  // Braccio destro
  [12, 14], [14, 16],
  // Gamba sinistra
  [23, 25], [25, 27],
  // Gamba destra
  [24, 26], [26, 28],
];

const KEY_JOINTS = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28];

const FitnessClassifier = ({ selectedExercise, assignmentId, sessionToken, isCountingActive, isExerciseFinished, tutorialUrl, tutorialMode = 'sovrapposizione', reps, targetReps, ttsEnabled = true, gateActive = false }) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const skeletonCanvasRef = useRef(null);
  const wsRef = useRef(null);
  const intervalRef = useRef(null);
  const tutorialOverlayRef = useRef(null);
  const streamRef = useRef(null); // stream attivo, usato per stoppare i track senza dipendere dal DOM
  const firstFrameSentRef = useRef(false);
  const hasCompletedRef = useRef(false);

  const { prediction, setPrediction } = usePrediction();

  const [serverStatus, setServerStatus] = useState({ text: 'Disconnesso', color: '#dc3545' });
  const [connectionLost, setConnectionLost] = useState(false);
  const isIntentionalCloseRef = useRef(false);

  // Rendering dello skeleton leggero su overlay canvas
  useEffect(() => {
    const canvas = skeletonCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    if (!prediction.landmarks || prediction.landmarks.length < 29 || isExerciseFinished || connectionLost) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }

    if (videoRef.current && videoRef.current.videoWidth > 0) {
      if (canvas.width !== videoRef.current.videoWidth || canvas.height !== videoRef.current.videoHeight) {
        canvas.width = videoRef.current.videoWidth;
        canvas.height = videoRef.current.videoHeight;
      }
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const landmarks = prediction.landmarks;
    const w = canvas.width;
    const h = canvas.height;

    // Linee skeleton leggere (verde menta discreto)
    ctx.lineWidth = 3;
    ctx.strokeStyle = 'rgba(77, 124, 95, 0.85)';
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    SKELETON_CONNECTIONS.forEach(([i, j]) => {
      const p1 = landmarks[i];
      const p2 = landmarks[j];
      if (p1 && p2 && (p1.visibility ?? 1.0) > 0.35 && (p2.visibility ?? 1.0) > 0.35) {
        ctx.beginPath();
        ctx.moveTo(p1.x * w, p1.y * h);
        ctx.lineTo(p2.x * w, p2.y * h);
        ctx.stroke();
      }
    });

    // Punti articolari principali
    KEY_JOINTS.forEach((i) => {
      const p = landmarks[i];
      if (p && (p.visibility ?? 1.0) > 0.35) {
        ctx.beginPath();
        ctx.arc(p.x * w, p.y * h, 4.5, 0, 2 * Math.PI);
        ctx.fillStyle = '#28a745';
        ctx.fill();
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = '#ffffff';
        ctx.stroke();
      }
    });
  }, [prediction.landmarks, isExerciseFinished, connectionLost]);

  useEffect(() => {
    console.log('Esercizio selezionato:', selectedExercise, 'gateActive:', gateActive);
    if ((!selectedExercise && !assignmentId) || gateActive) {
      setServerStatus({
        text: gateActive ? 'Ruota il telefono in orizzontale' : 'Seleziona un esercizio per iniziare',
        color: '#ffc107',
      });
      return;
    }

    // Reset flag completamento e chiusura intenzionale per nuova sessione
    hasCompletedRef.current = false;
    isIntentionalCloseRef.current = false;
    setConnectionLost(false);

    // La webcam parte subito, indipendentemente dal WebSocket
    startWebcam();

    const wsUrl = getWsStreamUrl();
    console.log('[WS] URL WebSocket finale:', wsUrl);

    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onopen = () => {
      console.log('[WS] onopen: connessione stabilita');
      setServerStatus({ text: 'Rete AI Attiva', color: '#28a745' });
      setConnectionLost(false);

      if (assignmentId && sessionToken) {
        wsRef.current.send(JSON.stringify({ assignment_id: assignmentId, token: sessionToken, llm_enabled: ttsEnabled }));
      } else {
        const exerciseKey = selectedExercise?.nome
          ?.toLowerCase()
          .replace(/ /g, '_') || selectedExercise;
        wsRef.current.send(JSON.stringify({ selected_exercise: exerciseKey, llm_enabled: ttsEnabled }));
      }
    };

    wsRef.current.onmessage = (event) => {
      if (hasCompletedRef.current || isIntentionalCloseRef.current) return;
      try {
        const data = JSON.parse(event.data);
        if (targetReps && targetReps > 0 && data.reps >= targetReps) {
          hasCompletedRef.current = true;
          isIntentionalCloseRef.current = true;
          setPrediction({
            ...data,
            reps: targetReps,
            phrase: "Hai completato tutte le ripetizioni previste. Ottimo lavoro."
          });
          stopStreaming();
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.close(1000, 'Exercise finished');
          }
          return;
        }
        setPrediction(data);
      } catch (err) {
        console.error('[WS] Errore parsing messaggio:', err);
      }
    };

    wsRef.current.onclose = (event) => {
      console.log('[WS] onclose: code=', event.code, 'reason=', event.reason);
      const isNormalClose = isIntentionalCloseRef.current || hasCompletedRef.current || isExerciseFinished || event.code === 1000;
      if (!isNormalClose) {
        console.warn('[WS] Chiusura inattesa WebSocket - Connessione persa');
        stopStreaming();
        setConnectionLost(true);
        setServerStatus({ text: 'Connessione persa', color: '#dc3545' });
        setPrediction(prev => ({
          ...prev,
          phrase: 'Connessione persa. La sessione live non è più connessa al server.'
        }));
      } else {
        setServerStatus({ text: 'Disconnesso', color: '#6c757d' });
      }
    };

    wsRef.current.onerror = (err) => {
      console.error('[WS] onerror:', err);
      const isNormalClose = isIntentionalCloseRef.current || hasCompletedRef.current || isExerciseFinished;
      if (!isNormalClose) {
        stopStreaming();
        setConnectionLost(true);
        setServerStatus({ text: 'Connessione persa', color: '#dc3545' });
        setPrediction(prev => ({
          ...prev,
          phrase: 'Connessione persa. La sessione live non è più connessa al server.'
        }));
      }
    };

    return () => {
      isIntentionalCloseRef.current = true;
      stopStreaming();
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
          wsRef.current.close(1000, 'Component unmounted');
        }
      }
    };
  }, [selectedExercise, gateActive]);

  // Garantisce lo spegnimento della webcam e la chiusura del WS qualunque sia
  // la causa dell'unmount, incluso il caso in cui getUserMedia si risolve dopo l'unmount
  useEffect(() => {
    return () => {
      isIntentionalCloseRef.current = true;
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
          wsRef.current.close(1000, 'Cleanup unmount');
        }
      }
      stopStreaming(); // stopStreaming usa streamRef, non dipende dal DOM
    };
  }, []);

  useEffect(() => {
    if (!tutorialOverlayRef.current) return;
    if (isCountingActive && tutorialUrl) {
      tutorialOverlayRef.current.play().catch(() => { });
    } else {
      tutorialOverlayRef.current.pause();
      tutorialOverlayRef.current.currentTime = 0;
    }
  }, [isCountingActive, tutorialUrl]);

  useEffect(() => {
    if (isExerciseFinished) {
      hasCompletedRef.current = true;
      isIntentionalCloseRef.current = true;
      stopStreaming();
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.close(1000, 'Exercise finished');
      }
      setServerStatus({ text: 'Esercizio Completato', color: '#28a745' });
    } else {
      // Se la websocket è ancora aperta, riportiamo il server status in modalità attiva
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        setServerStatus({ text: 'Rete AI Attiva', color: '#28a745' });
      }
    }
  }, [isExerciseFinished]);

  const stopStreaming = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    // Usa streamRef: funziona anche se videoRef è già null (componente smontato)
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

  const startWebcam = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setServerStatus({ text: 'Webcam non disponibile: apri l\'app in HTTPS', color: '#dc3545' });
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', frameRate: { ideal: 15 } }
      });
      // Salva subito lo stream nel ref: se la promise si risolve dopo l'unmount
      // stopStreaming() potrà comunque fermare i track tramite streamRef
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => {
          // Adatta canvas alle dimensioni reali del video (evita distorsione su mobile)
          if (canvasRef.current) {
            canvasRef.current.width = videoRef.current.videoWidth;
            canvasRef.current.height = videoRef.current.videoHeight;
          }
          startStreaming();
        };
      } else {
        // Componente già smontato quando la promise si è risolta: stop immediato
        stopStreaming();
      }
    } catch (err) {
      console.error('Errore webcam:', err);
      setServerStatus({ text: 'Webcam non trovata', color: '#dc3545' });
    }
  };

  const startStreaming = () => {
    intervalRef.current = setInterval(() => {
      if (hasCompletedRef.current || isExerciseFinished || isIntentionalCloseRef.current || connectionLost) return;
      if (!videoRef.current || !canvasRef.current || !wsRef.current) return;
      if (wsRef.current.readyState !== WebSocket.OPEN) return;

      const video = videoRef.current;
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');

      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.5);

      if (!firstFrameSentRef.current) {
        console.log('[WS] Primo frame inviato con successo al backend');
        firstFrameSentRef.current = true;
      }

      wsRef.current.send(JSON.stringify({ image: dataUrl }));
    }, 130);
  };

  // Funzione di utilità per formattare i nomi delle cartelle in testo leggibile
  const formatExerciseName = (name) => {
    if (!name || name === 'Nessuno' || name.includes('attesa')) return name;
    return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  };

  // Mostra la confidence solo se l'esercizio rilevato coincide con quello selezionato
  const normalizeName = (name) =>
    (name || '').toLowerCase().replace(/_/g, '').replace(/\s/g, '');

  const isCorrectExercise =
    selectedExercise &&
    prediction.exercise &&
    normalizeName(prediction.exercise) === normalizeName(selectedExercise.nome);

  const displayConfidence = isCorrectExercise ? prediction.confidence : 0;

  const getConfidenceColor = (conf) => {
    if (conf > 80) return '#28a745';
    if (conf > 50) return '#ffc107';
    return '#6c757d';
  };

  const getBorderColor = (conf) => {
    if (!isCountingActive) return 'transparent';
    if (conf > 80) return '#28a745';
    if (conf >= 50) return '#ffc107';
    return '#dc3545';
  };

  return (
    <>
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        overflow: 'hidden',
      }}>

        {/* Box Webcam con overlay */}
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          style={{
            position: 'absolute', top: 0, left: 0,
            width: '100%', height: '100%',
            objectFit: 'cover',
            transform: 'scaleX(-1)',
          }}
        />
        {/* Canvas Overlay per Skeleton Leggero in Tempo Reale */}
        <canvas
          ref={skeletonCanvasRef}
          style={{
            position: 'absolute', top: 0, left: 0,
            width: '100%', height: '100%',
            objectFit: 'cover',
            transform: 'scaleX(-1)',
            pointerEvents: 'none',
            zIndex: 5,
          }}
        />
        <canvas ref={canvasRef} width="640" height="480" style={{ display: 'none' }} />

        {/* Overlay Connessione Persa in caso di chiusura inattesa */}
        {connectionLost && !isExerciseFinished && (
          <div className="connection-lost-overlay" style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            backgroundColor: 'rgba(20, 24, 22, 0.82)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 30,
            color: '#ffffff',
            textAlign: 'center',
            padding: '24px',
            backdropFilter: 'blur(6px)',
          }}>
            <div style={{ fontSize: '2.8rem', marginBottom: '10px' }}>📡⚡</div>
            <h3 style={{ fontSize: '1.3rem', fontWeight: '800', margin: '0 0 6px', color: '#ff6b6b' }}>
              Connessione persa
            </h3>
            <p style={{ fontSize: '0.95rem', margin: 0, color: '#e0e0e0', maxWidth: '320px', lineHeight: 1.4 }}>
              La sessione live non è più connessa al server.
            </p>
          </div>
        )}

        {/* Overlay Video Tutorial - solo in modalità sovrapposizione */}
        {tutorialUrl && tutorialMode === 'sovrapposizione' && (
          <video
            ref={tutorialOverlayRef}
            key={tutorialUrl}
            src={tutorialUrl}
            loop
            muted
            playsInline
            className={`tutorial-overlay-video${isCountingActive ? ' tutorial-overlay-video--active' : ''}`}
          />
        )}

        {/* Overlay Header in alto - nome esercizio e reps */}
        {selectedExercise && isCountingActive && (
          <div className="exercise-header-overlay">
            <span className="exercise-header-name">
              {selectedExercise.nome?.toUpperCase()}
            </span>
            <span className="exercise-header-reps">
              {reps} / {targetReps}
            </span>
          </div>
        )}

        {/* Confidence in basso a sinistra - solo durante l'esercizio e solo se corretto */}
        {isCountingActive && (
          <div className="confidence-badge-overlay">
            <span style={{ color: getConfidenceColor(displayConfidence) }}>
              {displayConfidence}%
            </span>
          </div>
        )}

        {/* Placeholder: nessun esercizio ancora selezionato */}
        {!selectedExercise && (
          <>
            <div className="top-status-overlay">
              <div className="positioning-message">
                Scorri in basso e seleziona un esercizio
              </div>
            </div>
            <div className="no-exercise-placeholder">
              <img src="/icons8-fotocamera-50.png" alt="" />
              <p className="no-exercise-hint">La videocamera si attiverà appena avrai selezionato l'esercizio</p>
            </div>
          </>
        )}

        {/* Messaggio di posizionamento + barra buffer - overlay assoluto in alto */}
        {!isCountingActive && selectedExercise && prediction.exercise && (
          <div className="top-status-overlay">
            <div className={`positioning-message${prediction.status === 'no_model' ? ' positioning-message--no-model' : ''}`}>
              {formatExerciseName(prediction.exercise)}
            </div>
            {prediction.status === 'buffering' && (
              <div className="buffer-progress-wrapper">
                <div
                  className="buffer-progress-bar"
                  style={{
                    width: `${Math.min(
                      ((prediction.frames_stacked || 0) / (prediction.max_frames || 43)) * 100,
                      100
                    )}%`,
                  }}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
};

export default FitnessClassifier;