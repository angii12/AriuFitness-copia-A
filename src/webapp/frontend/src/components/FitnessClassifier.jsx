import React, { useEffect, useRef, useState } from 'react';
import { usePrediction } from '../context/PredictionContext';
import './FitnessClassifier.css';

const FitnessClassifier = ({ selectedExercise, isCountingActive, isExerciseFinished, tutorialUrl, tutorialMode = 'sovrapposizione', reps, targetReps, ttsEnabled = true }) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);
  const intervalRef = useRef(null);
  const tutorialOverlayRef = useRef(null);
  const streamRef = useRef(null); // stream attivo, usato per stoppare i track senza dipendere dal DOM

  const { prediction, setPrediction } = usePrediction();

  const [serverStatus, setServerStatus] = useState({ text: 'Disconnesso', color: '#dc3545' });

  useEffect(() => {
    console.log('Esercizio selezionato:', selectedExercise);
    if (!selectedExercise) {
      setServerStatus({ text: 'Seleziona un esercizio per iniziare', color: '#ffc107' });
      return;
    }

    // La webcam parte subito, indipendentemente dal WebSocket
    startWebcam();

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = `${window.location.hostname}:8000`;
    wsRef.current = new WebSocket(`${wsProtocol}//${wsHost}/ws/stream`);

    wsRef.current.onopen = () => {
      setServerStatus({ text: 'Rete AI Attiva', color: '#28a745' });
      const exerciseKey = selectedExercise?.nome
        ?.toLowerCase()
        .replace(/ /g, '_');
      wsRef.current.send(JSON.stringify({ selected_exercise: exerciseKey, llm_enabled: ttsEnabled }));
    };

    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setPrediction(data);
    };

    wsRef.current.onclose = () => {
      setServerStatus({ text: 'Disconnesso ❌', color: '#dc3545' });
    };

    wsRef.current.onerror = () => {
      setServerStatus({ text: 'Errore Connessione Back-end ⚠️', color: '#ffc107' });
    };

    return () => {
      stopStreaming();
      if (wsRef.current) wsRef.current.close();
    };
  }, [selectedExercise]);

  // Garantisce lo spegnimento della webcam e la chiusura del WS qualunque sia
  // la causa dell'unmount, incluso il caso in cui getUserMedia si risolve dopo l'unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
      stopStreaming(); // stopStreaming usa streamRef, non dipende dal DOM
    };
  }, []);

  useEffect(() => {
    if (!tutorialOverlayRef.current) return;
    if (isCountingActive && tutorialUrl) {
      tutorialOverlayRef.current.play().catch(() => {});
    } else {
      tutorialOverlayRef.current.pause();
      tutorialOverlayRef.current.currentTime = 0;
    }
  }, [isCountingActive, tutorialUrl]);

  useEffect(() => {
    if (isExerciseFinished) {
      stopStreaming();
      setServerStatus({ text: 'Esercizio Completato', color: '#28a745' });
      
      if (typeof setPrediction === 'function') {
        setPrediction({ status: 'Inattivo', reps: 0, confidence: 0 });
      }
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
      if (!videoRef.current || !canvasRef.current || !wsRef.current) return;
      if (wsRef.current.readyState !== WebSocket.OPEN) return;

      const video = videoRef.current;
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');

      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.5);

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
          overflow: 'hidden',}}>

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
      <canvas ref={canvasRef} width="640" height="480" style={{ display: 'none' }} />

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