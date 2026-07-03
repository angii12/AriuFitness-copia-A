import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { supabase } from '../SupabaseClient';
import { useColor } from '../context/ColorContext';
import { usePrediction } from '../context/PredictionContext';

import '../Dashboard.css';
import './ClassificationPage.css';
import FitnessClassifier from '../components/FitnessClassifier';
import TutorialOverlay from '../components/TutorialOverlay';
import { useLandscapeGate } from '../hooks/useLandscapeGate';

const TUTORIAL_CLASSIFICAZIONE = [
  {
    icon: '👆',
    title: 'Seleziona l\'esercizio',
    desc: 'Clicca su un esercizio nella lista per selezionarlo. La telecamera si attiverà e il sistema attenderà che tu sia in posizione.',
  },
  {
    icon: '📷',
    title: 'Mettiti davanti alla telecamera',
    desc: 'Posizionati in modo che il tuo corpo sia visibile. Quando il sistema ti riconosce, parte il countdown e poi il conteggio automatico delle ripetizioni.',
  },
  {
    icon: '✅',
    title: 'Avanza tra gli esercizi',
    desc: 'Completate le ripetizioni, clicca Prossimo Esercizio per continuare, oppure Termina Allenamento per chiudere la sessione.',
  },
];

const DEFAULT_TARGET_REPS = 5;

function ClassificationPage() {
  const { prediction, setPrediction } = usePrediction();

  const reps = prediction.reps || 0;
  const phrase = prediction.phrase || "Inquadrati per iniziare l'esercizio.";
  const predictedExercise = prediction.exercise || '';
  const confidence = prediction.confidence || 0;

  const [selectedExercise, setSelectedExercise] = useState(null);
  const [selectedExercises, setSelectedExercises] = useState([]);
  const [stream, setStream] = useState(null);
  const [selectedTutorial, setSelectedTutorial] = useState(null);
  const [currentExerciseIndex, setCurrentExerciseIndex] = useState(0);
  const [isFeedbackModalVisible, setIsFeedbackModalVisible] = useState(false);
  const [isWorkoutFeedbackModalVisible, setIsWorkoutFeedbackModalVisible] = useState(false);
  const [workoutComment, setWorkoutComment] = useState('');
  const [countdown, setCountdown] = useState(null);
  const [isCountingActive, setIsCountingActive] = useState(false);
  const [isCompletedVisible, setIsCompletedVisible] = useState(false);
  const [isStartLocked, setIsStartLocked] = useState(false);
  const [webcamWarningMessage, setWebcamWarningMessage] = useState('');
  const [isContinueAfterDifficultModalVisible, setIsContinueAfterDifficultModalVisible] = useState(false);
  const [pendingAdvanceAfterDifficult, setPendingAdvanceAfterDifficult] = useState(false);
  const [completedExercises, setCompletedExercises] = useState([]);
  const [exerciseStartTime, setExerciseStartTime] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [currentExerciseStarted, setCurrentExerciseStarted] = useState(false);
  const [isExerciseFinished, setIsExerciseFinished] = useState(false);

  // Modalità visualizzazione tutorial (letta da localStorage)
  const [tutorialMode] = useState(
    () => localStorage.getItem('tutorialMode') || 'sovrapposizione'
  );

  // Feedback vocale abilitato (letto da localStorage)
  const [ttsEnabled] = useState(() => localStorage.getItem('ttsEnabled') !== 'false');

  // Fase di calibrazione: attiva quando si seleziona un esercizio
  const [isCalibrationPhase, setIsCalibrationPhase] = useState(false);

  const videoRef = useRef(null);
  const tutorialVideoRef = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();
  const isCountingActiveRef = useRef(false);
  const canvasRef = useRef(null);
  const cameraRef = useRef(null);
  const dingAudioRef = useRef(new Audio('/ding.mp3'));
  const exerciseRefs = useRef([]);

  // Coda TTS per feedback LLM
  const llmQueueRef = useRef([]);
  const lastLlmFeedbackIdRef = useRef(0);
  const isExerciseFinishedRef = useRef(false);
  const trySpeakRef = useRef(null);

  const { backgroundColor } = useColor();
  const { isBlocked, isMobileLandscape } = useLandscapeGate();

  useEffect(() => {
    isCountingActiveRef.current = isCountingActive;
  }, [isCountingActive]);

  useEffect(() => {
    if (exerciseRefs.current[currentExerciseIndex]) {
      exerciseRefs.current[currentExerciseIndex].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [currentExerciseIndex]);

  useEffect(() => {
    if (isExerciseFinished) {
      document.getElementById('workout-list-panel')?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [isExerciseFinished]);

  useEffect(() => {
    isExerciseFinishedRef.current = isExerciseFinished;
    if (isExerciseFinished) {
      llmQueueRef.current = [];
    }
  }, [isExerciseFinished]);

  // Ferma TTS e svuota la coda LLM quando si lascia la pagina in qualsiasi modo
  useEffect(() => {
    return () => {
      window.speechSynthesis.cancel();
      llmQueueRef.current = [];
    };
  }, []);

  // trySpeak: riproduce il prossimo testo dalla coda LLM se la sintesi è libera.
  // Definita come ref per evitare problemi di closure nelle callback utterance.onend.
  trySpeakRef.current = () => {
    if (isExerciseFinishedRef.current) { llmQueueRef.current = []; return; }
    if (window.speechSynthesis.speaking || window.speechSynthesis.pending) return;
    if (llmQueueRef.current.length === 0) return;
    const text = llmQueueRef.current.shift();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'it-IT';
    utterance.rate = 1.05;
    utterance.onend = () => trySpeakRef.current?.();
    window.speechSynthesis.speak(utterance);
  };

  // Accoda il feedback LLM ricevuto dal backend e tenta di riprodurlo
  useEffect(() => {
    const id = prediction.llm_feedback_id;
    const text = prediction.llm_feedback;
    if (!text || !id || id <= lastLlmFeedbackIdRef.current) return;
    lastLlmFeedbackIdRef.current = id;
    if (!isExerciseFinishedRef.current && isCountingActive && ttsEnabled) {
      llmQueueRef.current.push(text);
      trySpeakRef.current?.();
    }
  }, [prediction.llm_feedback_id, isCountingActive, ttsEnabled]);

  const pauseTutorialVideo = () => {
    if (!tutorialVideoRef.current) return;
    try {
      tutorialVideoRef.current.pause();
    } catch (e) {}
  };

  const resetExerciseRuntimeState = () => {
    setCountdown(null);
    setIsCountingActive(false);
    setIsStartLocked(false);
    setIsCompletedVisible(false);
  };

  // Carica esercizi da navigation state o localStorage
  useEffect(() => {
    const fromNav = location?.state?.allenamentiSelezionati;
    if (Array.isArray(fromNav) && fromNav.length > 0) {
      const normalizedNav = fromNav.map((item, index) =>
        typeof item === 'string'
          ? { id: index + 1, nome: item, video_tut_url: null }
          : item
      );
      setSelectedExercises(normalizedNav);
      setCurrentExerciseIndex(0);
      setSelectedExercise(null);
      return;
    }

    try {
      const raw = localStorage.getItem('selectedExercises');
      const parsed = raw ? JSON.parse(raw) : [];
      if (Array.isArray(parsed)) {
        const normalized = parsed.map((item, index) =>
          typeof item === 'string'
            ? {
                id: index + 1,
                nome: item,
                video_tut_url: 'wall-sit-with-medicine-ball-rotation.mp4',
              }
            : item
        );
        setSelectedExercises(normalized);
        setCurrentExerciseIndex(0);
        setSelectedExercise(null);
      }
    } catch (e) {
      console.warn('allenamentiSelezionati non valido in localStorage', e);
      setSelectedExercises([]);
    }
  }, [location?.state]);

  // Controlla e riproduce/mette in pausa il video tutorial (per modalità diviso e solo-tutorial)
  useEffect(() => {
    if (!tutorialVideoRef.current) return;
    if (tutorialMode === 'sovrapposizione') return; // gestito da FitnessClassifier

    const shouldPlay =
      tutorialMode === 'diviso'
        ? !!selectedTutorial
        : isCountingActive && !!selectedTutorial; // solo-tutorial: solo durante l'esercizio

    if (shouldPlay) {
      tutorialVideoRef.current.play().catch(() => {});
    } else {
      if (tutorialVideoRef.current.readyState >= 2) {
        tutorialVideoRef.current.pause();
        tutorialVideoRef.current.currentTime = 0;
      }
    }
  }, [isCountingActive, selectedTutorial, tutorialMode]);

  // Termina automaticamente la calibrazione quando il backend rileva il corpo completo
  // oppure quando segnala che non esiste un modello per l'esercizio scelto
  useEffect(() => {
    if (!isCalibrationPhase) return;
    if (prediction.status === 'predicted' || prediction.status === 'no_model') {
      setIsCalibrationPhase(false);
    }
  }, [prediction.status, isCalibrationPhase]);

  const trackSkippedExercise = (exercise) => {
    if (exercise && exercise.id && exercise.nome) {
      const skippedExerciseData = {
        exercise_id: exercise.id,
        exercise_name: exercise.nome,
        completed: false,
        reps: 0,
        feedback: null,
        timestamp: new Date().toISOString(),
      };
      setCompletedExercises((prev) => [...prev, skippedExerciseData]);
    }
  };

  const advanceAfterExerciseFeedback = () => {
    const nextIndex = currentExerciseIndex + 1;

    if (nextIndex < selectedExercises.length) {
      if (selectedExercise && !currentExerciseStarted) {
        trackSkippedExercise(selectedExercise);
      }
      setCurrentExerciseIndex(nextIndex);
      setSelectedExercise(null);
      setIsCalibrationPhase(false);
      setCurrentExerciseStarted(false);
      resetExerciseRuntimeState();
      return;
    }

    if (selectedExercise && !currentExerciseStarted) {
      trackSkippedExercise(selectedExercise);
    }
    setCurrentExerciseIndex(selectedExercises.length);
    setSelectedExercise(null);
    setSelectedTutorial(null);
    setIsCalibrationPhase(false);
    setCurrentExerciseStarted(false);
    resetExerciseRuntimeState();
  };

  const handleFeedbackSubmit = (feedback) => {
    if (selectedExercise && currentExerciseStarted) {
      setCompletedExercises(prev => {
        if (prev.some(e => e.exercise_id === selectedExercise.id)) return prev;
        return [...prev, {
          exercise_id: selectedExercise.id,
          exercise_name: selectedExercise.nome,
          completed: reps >= currentTargetReps,
          reps,
          feedback,
          timestamp: exerciseStartTime ? new Date(exerciseStartTime).toISOString() : new Date().toISOString(),
        }];
      });
    }

    setIsFeedbackModalVisible(false);

    if (feedback === 'difficile') {
      setPendingAdvanceAfterDifficult(true);
      setIsContinueAfterDifficultModalVisible(true);
      return;
    }

    advanceAfterExerciseFeedback();
  };

  const handleContinueAfterDifficultYes = () => {
    setIsContinueAfterDifficultModalVisible(false);
    if (pendingAdvanceAfterDifficult) {
      setPendingAdvanceAfterDifficult(false);
      advanceAfterExerciseFeedback();
    }
  };

  const handleContinueAfterDifficultNo = () => {
    setIsContinueAfterDifficultModalVisible(false);
    setPendingAdvanceAfterDifficult(false);
    navigate('/');
  };

  const handleFinishWorkout = async (feedback) => {
    const finalFeedback = feedback === 'comment' ? workoutComment : feedback;
    setIsWorkoutFeedbackModalVisible(false);
    navigate('/');
  };

  // Countdown e avvio esercizio (bloccato durante calibrazione)
  useEffect(() => {
    if (!selectedExercise) return;
    if (isExerciseFinished) return;

    const playBeep = (isFinal = false) => {
      try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const ctx = new AudioContext();
        const oscillator = ctx.createOscillator();
        const gainNode = ctx.createGain();
        oscillator.connect(gainNode);
        gainNode.connect(ctx.destination);
        if (isFinal) {
          oscillator.frequency.value = 880;
          gainNode.gain.setValueAtTime(0.15, ctx.currentTime);
          oscillator.start(ctx.currentTime);
          gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
          oscillator.stop(ctx.currentTime + 0.4);
        } else {
          oscillator.frequency.value = 440;
          gainNode.gain.setValueAtTime(0.1, ctx.currentTime);
          oscillator.start(ctx.currentTime);
          gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
          oscillator.stop(ctx.currentTime + 0.15);
        }
      } catch (e) {
        console.warn("Impossibile riprodurre l'audio:", e);
      }
    };

    // Il countdown non parte finché è in corso la calibrazione
    if (
      countdown === null &&
      !isCountingActive &&
      !isCalibrationPhase &&
      prediction.status === 'predicted'
    ) {
      playBeep(false);
      setCountdown(5);
      return;
    }

    if (countdown === 0) {
      playBeep(true);
      setCountdown(null);
      setIsCountingActive(true);
      setExerciseStartTime(Date.now());
      return;
    }

    if (countdown !== null && countdown > 0) {
      const timer = setTimeout(() => {
        playBeep(true);
        setCountdown(countdown - 1);
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown, selectedExercise, prediction.status, isCountingActive, isCalibrationPhase]);

  const advanceToNextExercise = () => {
    const nextIndex = currentExerciseIndex + 1;

    setPrediction({
      status: 'Inattivo',
      exercise: '',
      confidence: 0,
      frames_stacked: 0,
      reps: 0,
      phrase: 'Inquadrati per iniziare il prossimo esercizio.',
    });

    if (nextIndex >= selectedExercises.length) {
      setCurrentExerciseIndex(selectedExercises.length);
      setSelectedExercise(null);
      setSelectedTutorial(null);
      setIsCountingActive(false);
      setCountdown(null);
      setIsStartLocked(false);
      setIsExerciseFinished(false);
      setIsCalibrationPhase(false);
      return;
    }

    if (typeof setPrediction === 'function') {
      setPrediction({ status: 'Inattivo', reps: 0, confidence: 0 });
    }

    setIsExerciseFinished(false);
    setIsCountingActive(false);
    setCountdown(null);

    setCurrentExerciseIndex(nextIndex);
    const nextExercise = selectedExercises[nextIndex];
    handleExerciseSelect(nextExercise);
  };

  const currentTargetReps = DEFAULT_TARGET_REPS;
  const remainingReps = Math.max(currentTargetReps - reps, 0);

  // Completamento esercizio al raggiungimento del target ripetizioni
  useEffect(() => {
    if (!isCountingActive) return;
    if (!selectedExercise) return;
    if (reps < currentTargetReps) return;

    // Registra il completamento subito, prima che l'auto-advance resetti i reps
    setCompletedExercises(prev => {
      if (prev.some(e => e.exercise_id === selectedExercise.id)) return prev;
      return [...prev, {
        exercise_id: selectedExercise.id,
        exercise_name: selectedExercise.nome,
        completed: true,
        reps,
        feedback: null,
        timestamp: exerciseStartTime ? new Date(exerciseStartTime).toISOString() : new Date().toISOString(),
      }];
    });

    setIsCompletedVisible(true);
    setIsCountingActive(false);
    setCountdown(null);
    setIsExerciseFinished(true);

    pauseTutorialVideo();

    if (ttsEnabled) {
      try {
        window.speechSynthesis.cancel();
        const messaggio = new SpeechSynthesisUtterance(
          'Complimenti! Puoi passare al prossimo esercizio'
        );
        messaggio.lang = 'it-IT';
        messaggio.rate = 1.0;
        window.speechSynthesis.speak(messaggio);
      } catch (error) {
        console.error('Errore durante la riproduzione del TTS:', error);
      }
    }

    const t = setTimeout(() => {
      setIsCompletedVisible(false);
      advanceToNextExercise();
    }, 1000);

    return () => clearTimeout(t);
  }, [reps, isCountingActive, selectedExercise]);

  const handleExerciseSelect = (exercise) => {
    if (exercise && exercise.id && exercise.nome) {
      setPrediction({
        status: 'Inattivo',
        exercise: '',
        confidence: 0,
        frames_stacked: 0,
        reps: 0,
        phrase: 'Inquadrati per iniziare il prossimo esercizio.',
      });
      setSelectedExercise(exercise);
      setCurrentExerciseStarted(false);
      setIsExerciseFinished(false);
      setIsCalibrationPhase(true); // avvia fase calibrazione
      if (exercise.video_tut_url) {
        setSelectedTutorial(exercise.video_tut_url);
      }
      resetExerciseRuntimeState();
      // Desktop: riporta in cima alla pagina
      if (!navigator.maxTouchPoints) {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    }
  };

  const handleSkipExercise = () => {
    if (selectedExercise && currentExerciseStarted) {
      setCompletedExercises(prev => [...prev, {
        exercise_id: selectedExercise.id,
        exercise_name: selectedExercise.nome,
        completed: false,
        reps,
        feedback: 'saltato',
        timestamp: exerciseStartTime ? new Date(exerciseStartTime).toISOString() : new Date().toISOString(),
      }]);
    }
    advanceAfterExerciseFeedback();
  };

  const handleStartExercise = () => {
    if (!selectedExercise) return;
    setCurrentExerciseStarted(true);
    setIsStartLocked(true);
    setCountdown(5);
  };

  // TTS descrizione esercizio alla selezione
  useEffect(() => {
    if (!ttsEnabled || !selectedExercise || !selectedExercise.descrizione) return;
    window.speechSynthesis.cancel();
    const nomeEsercizio = selectedExercise.nome;
    const descrizioneEsercizio = selectedExercise.descrizione;
    const testoDaLeggere = `Esercizio selezionato: ${nomeEsercizio}. Descrizione: ${descrizioneEsercizio}`;
    const utterance = new SpeechSynthesisUtterance(testoDaLeggere);
    utterance.lang = 'it-IT';
    utterance.rate = 1.0;
    window.speechSynthesis.speak(utterance);
    return () => { window.speechSynthesis.cancel(); };
  }, [selectedExercise, ttsEnabled]);

  const prevRepsRef = useRef(0);
  const playElectronicDing = () => {
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return;
      const ctx = new AudioContext();
      const oscillator = ctx.createOscillator();
      const gainNode = ctx.createGain();
      oscillator.connect(gainNode);
      gainNode.connect(ctx.destination);
      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(880, ctx.currentTime);
      gainNode.gain.setValueAtTime(0.3, ctx.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.00001, ctx.currentTime + 0.15);
      oscillator.start(ctx.currentTime);
      oscillator.stop(ctx.currentTime + 0.15);
    } catch (e) {
      console.error('Impossibile riprodurre il bip elettronico:', e);
    }
  };

  useEffect(() => {
    if (prediction && prediction.reps > prevRepsRef.current) {
      playElectronicDing();
    }
    if (prediction) {
      prevRepsRef.current = prediction.reps;
    }
  }, [prediction?.reps]);

  // Logica di visibilità pannelli in base alla modalità
  const webcamPanelHidden =
    tutorialMode === 'solo-tutorial' && !isCalibrationPhase;

  const tutorialPanelHidden =
    tutorialMode === 'sovrapposizione' ||
    !selectedTutorial ||
    (tutorialMode === 'solo-tutorial' && isCalibrationPhase);

  // Confidence filtrata per il pannello tutorial in modalità solo-tutorial
  const _normExName = (name) =>
    (name || '').toLowerCase().replace(/_/g, '').replace(/\s/g, '');
  const displayConfidence =
    selectedExercise &&
    prediction.exercise &&
    _normExName(prediction.exercise) === _normExName(selectedExercise.nome)
      ? (prediction.confidence || 0)
      : 0;

  const getConfidenceColor = (conf) => {
    if (conf > 80) return '#28a745';
    if (conf > 50) return '#ffc107';
    return '#6c757d';
  };

  const getConfidenceBorderColor = (conf) => {
    if (!isCountingActive) return 'transparent';
    if (conf > 80) return '#28a745';
    if (conf >= 50) return '#ffc107';
    return '#dc3545';
  };

  const getExerciseIcon = (item, index) => {
    if (index < currentExerciseIndex) {
      const data = completedExercises.find(e => e.exercise_id === item.id);
      return data && !data.completed ? '❌' : '✅';
    }
    if (index > currentExerciseIndex) return '🔒';
    return '🔓';
  };

  // --- JSX RENDER ---
  return (
    <div
      className={`dashboard-container${isMobileLandscape ? ' dashboard-container--landscape' : ''}`}
      style={{ '--colorvar': backgroundColor }}
    >
      <TutorialOverlay steps={TUTORIAL_CLASSIFICAZIONE} storageKey="tutorial_visto_classificazione" />

      {/* Gate landscape: blocca l'uso in portrait su mobile */}
      {isBlocked && (
        <div className="landscape-gate">
          <div className="landscape-gate-content">
            <span className="landscape-gate-icon">📱</span>
            <p className="landscape-gate-text">Ruota il telefono in orizzontale per continuare</p>
          </div>
        </div>
      )}

      {/* Area principale — struttura piatta: webcam | tutorial | lista */}
      <div
        className={`workout-area workout-area--${tutorialMode}${isMobileLandscape ? ' workout-area--landscape' : ''}`}
      >
        {/* Pannello Webcam - sempre montato per l'IA */}
        <div
          id="webcam-panel"
          className={`video-panel glass-card${webcamPanelHidden ? ' panel-hidden' : ''}`}
          style={{
            flexDirection: 'column',
            border: `5px solid ${getConfidenceBorderColor(displayConfidence)}`,
            transition: 'border-color 0.4s ease',
          }}
        >
          <div className="video-container">
            <FitnessClassifier
              selectedExercise={selectedExercise}
              isCountingActive={isCountingActive}
              isExerciseFinished={isExerciseFinished}
              tutorialUrl={selectedTutorial}
              tutorialMode={tutorialMode}
              reps={reps}
              targetReps={currentTargetReps}
              ttsEnabled={ttsEnabled}
              gateActive={isBlocked}
            />
          </div>
          {/* Salta/Prossimo overlay — solo in sovrapposizione (tutorial panel nascosto) */}
          {tutorialPanelHidden && selectedExercise && currentExerciseIndex < selectedExercises.length - 1 && (
            <button
              className={`panel-skip-btn${isExerciseFinished ? ' panel-skip-btn--next' : ''}`}
              onClick={() => isExerciseFinished ? setIsFeedbackModalVisible(true) : handleSkipExercise()}
            >
              {isExerciseFinished ? '✓' : '>>'}
            </button>
          )}
        </div>

        {/* Pannello Tutorial (diviso / solo-tutorial) */}
        <div
          id="tutorial-panel"
          className={`video-panel glass-card${tutorialPanelHidden ? ' panel-hidden' : ''}${
            tutorialMode === 'diviso' && !isMobileLandscape ? ' tutorial-panel--diviso' : ''
          }`}
          style={tutorialMode === 'solo-tutorial' ? {
            border: `5px solid ${getConfidenceBorderColor(displayConfidence)}`,
            transition: 'border-color 0.4s ease',
          } : undefined}
        >
          {/* Salta/Prossimo overlay — diviso e solo-tutorial */}
          {selectedExercise && currentExerciseIndex < selectedExercises.length - 1 && (
            <button
              className={`panel-skip-btn${isExerciseFinished ? ' panel-skip-btn--next' : ''}`}
              onClick={() => isExerciseFinished ? setIsFeedbackModalVisible(true) : handleSkipExercise()}
            >
              {isExerciseFinished ? '✓' : '›'}
            </button>
          )}
          <div className="video-container">
            {selectedTutorial ? (
              <video
                ref={tutorialVideoRef}
                key={selectedTutorial}
                loop
                muted
                playsInline
              >
                <source src={selectedTutorial} type="video/mp4" />
              </video>
            ) : (
              <div className="video-placeholder">
                <p>Seleziona un esercizio per vedere il video tutorial</p>
              </div>
            )}

            {/* Overlay in alto: nome esercizio + reps - solo in modalità solo-tutorial */}
            {tutorialMode === 'solo-tutorial' && selectedExercise && isCountingActive && (
              <div className="exercise-header-overlay">
                <span className="exercise-header-name">
                  {selectedExercise.nome?.toUpperCase()}
                </span>
                <span className="exercise-header-reps">
                  {reps} / {currentTargetReps}
                </span>
              </div>
            )}

            {/* Confidence badge in basso a sinistra - solo in modalità solo-tutorial */}
            {tutorialMode === 'solo-tutorial' && isCountingActive && (
              <div className="confidence-badge-overlay">
                <span style={{ color: getConfidenceColor(displayConfidence) }}>
                  {displayConfidence}%
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Lista esercizi */}
        <div
          id="workout-list-panel"
          className="info-card glass-card workout-list-card"
        >
        <h3>ESERCIZI SELEZIONATI</h3>
        {prediction.status === 'no_model' && selectedExercise && (
          <div className="no-model-warning">
            &#9888; Nessun modello di riconoscimento disponibile per questo esercizio al momento. Seleziona il prossimo esercizio.
          </div>
        )}
        {selectedExercises.length === 0 ? (
          <p>
            Non hai selezionato esercizi. Vai in{' '}
            <Link to="/visualizza-esercizi">Galleria Esercizi</Link> e
            aggiungili.
          </p>
        ) : null}
        <ul className="exercise-list">
          {selectedExercises.map((item, index) => (
            <button
              key={index}
              ref={el => exerciseRefs.current[index] = el}
              className={
                selectedExercise?.id === item.id
                  ? 'exercise-item active-exercise'
                  : 'exercise-item'
              }
              onClick={() => handleExerciseSelect(item)}
              disabled={
                index !== currentExerciseIndex ||
                countdown !== null ||
                isCountingActive
              }
            >
              <span className="ex-num">{index + 1}</span>
              <span className="ex-name">{item.nome}</span>
              <span className="ex-status">{getExerciseIcon(item, index)}</span>
            </button>
          ))}
        </ul>
        {isCompletedVisible && (
          <div className="completed-message">Completato!</div>
        )}
        {selectedExercises.length > 0 &&
          currentExerciseIndex >= selectedExercises.length && (
            <div className="completed-message">Hai Finito!</div>
          )}
        {selectedExercise && (
          <div className="action-buttons-container">
            <button
              className="finish-workout-button"
              onClick={() => setIsWorkoutFeedbackModalVisible(true)}
            >
              Termina Allenamento
            </button>
          </div>
        )}
        </div>
      </div>

      {/* Modal feedback esercizio */}
      {isFeedbackModalVisible && (
        <div className="modal-overlay">
          <div className="glass-card modal-content">
            <h3>Come ti sei sentito durante l'esercizio?</h3>
            <div className="feedback-faces">
              <span onClick={() => handleFeedbackSubmit('difficile')}>😞</span>
              <span onClick={() => handleFeedbackSubmit('medio')}>😐</span>
              <span onClick={() => handleFeedbackSubmit('facile')}>😊</span>
            </div>
          </div>
        </div>
      )}

      {/* Modal feedback allenamento */}
      {isWorkoutFeedbackModalVisible && (
        <div className="modal-overlay">
          <div className="glass-card modal-content">
            <h2>FINE ALLENAMENTO!</h2>
            <h3>Come è stato l'allenamento?</h3>
            <div className="feedback-faces">
              <span onClick={() => handleFinishWorkout('difficile')}>😞</span>
              <span onClick={() => handleFinishWorkout('medio')}>😐</span>
              <span onClick={() => handleFinishWorkout('facile')}>😊</span>
            </div>
          </div>
        </div>
      )}

      {/* Modal continua dopo feedback difficile */}
      {isContinueAfterDifficultModalVisible && (
        <div className="modal-overlay">
          <div className="glass-card modal-content">
            <h3>Sei sicuro di riuscire a continuare?</h3>
            <div className="continue-buttons">
              <button
                className="continue-button"
                onClick={handleContinueAfterDifficultYes}
              >
                Sì, posso continuare
              </button>
              <button
                className="finish-workout-button"
                onClick={handleContinueAfterDifficultNo}
              >
                No, voglio fermarmi
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Countdown overlay */}
      {countdown !== null && (
        <div className="countdown-overlay">
          <p className="countdown-text">Il tuo esercizio inizia tra</p>
          <div className="countdown-number">{countdown}</div>
        </div>
      )}

      {/* Overlay calibrazione - appare prima di ogni esercizio */}
      {isCalibrationPhase && selectedExercise && (
        <div className="calibration-overlay">
          <div className="calibration-content glass-card">
            <p className="calibration-icon">&#128247;</p>
            <h3 className="calibration-title">Calibrazione</h3>
            <div className="calibration-scanning">
              <span className="calibration-dot" />
              <span className="calibration-dot" />
              <span className="calibration-dot" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ClassificationPage;
