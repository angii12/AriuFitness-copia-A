import React, { useEffect, useRef, useState } from 'react';
import { usePrediction } from '../context/PredictionContext';
import './FitnessClassifier.css';

const FitnessClassifier = ({ selectedExercise, isCountingActive, isExerciseFinished, tutorialUrl, tutorialMode = 'sovrapposizione', reps, targetReps, ttsEnabled = true }) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);
  const intervalRef = useRef(null);
  const tutorialOverlayRef = useRef(null);

  const { prediction, setPrediction } = usePrediction();

  const [serverStatus, setServerStatus] = useState({ text: 'Disconnesso', color: '#dc3545' });

  useEffect(() => {
    console.log('Esercizio selezionato:', selectedExercise);
    if (!selectedExercise) {
      setServerStatus({ text: 'Seleziona un esercizio per iniziare', color: '#ffc107' });
      return;
    }
    wsRef.current = new WebSocket('ws://localhost:8000/ws/stream');

    wsRef.current.onopen = () => {
      setServerStatus({ text: 'Rete AI Attiva', color: '#28a745' });
      const exerciseKey = selectedExercise?.nome
        ?.toLowerCase()
        .replace(/ /g, '_');
      wsRef.current.send(JSON.stringify({ selected_exercise: exerciseKey, llm_enabled: ttsEnabled }));
      startWebcam();
    };

    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setPrediction(data);
    };

    wsRef.current.onclose = () => {
      setServerStatus({ text: 'Disconnesso ❌', color: '#dc3545' });
      stopStreaming();
    };

    wsRef.current.onerror = () => {
      setServerStatus({ text: 'Errore Connessione Back-end ⚠️', color: '#ffc107' });
      stopStreaming();
    };

    return () => {
      stopStreaming();
      if (wsRef.current) wsRef.current.close();
    };
  }, [selectedExercise]);

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

  const startWebcam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, frameRate: { ideal: 15 } }
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => startStreaming();
      }
    } catch (err) {
      console.error("Errore webcam:", err);
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
      const dataUrl = canvas.toDataURL('image/jpeg', 0.5); // Qualità bilanciata a 0.5 per alleggerire il carico di rete

      wsRef.current.send(JSON.stringify({ image: dataUrl }));
    }, 130);
  };

  const stopStreaming = () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (videoRef.current && videoRef.current.srcObject) {
      const tracks = videoRef.current.srcObject.getTracks();
      tracks.forEach(track => track.stop());
    }
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
          border: `3px solid ${getBorderColor(displayConfidence)}`,
          transition: 'border-color 0.4s ease',
          overflow: 'hidden',
          boxSizing: 'border-box',}}>

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

      {/* Messaggio di posizionamento + barra buffer - overlay assoluto in alto */}
      {!isCountingActive && prediction.exercise && (
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