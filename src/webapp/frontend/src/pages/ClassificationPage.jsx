import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { Pose, POSE_CONNECTIONS } from "@mediapipe/pose";
import { drawConnectors, drawLandmarks } from "@mediapipe/drawing_utils";
import { Camera } from "@mediapipe/camera_utils";
import { supabase } from '../SupabaseClient';
import { useColor } from '../context/ColorContext';
import { usePrediction } from '../context/PredictionContext';

import '../Dashboard.css';
import './ClassificationPage.css';
import FitnessClassifier from '../components/FitnessClassifier';

const DEFAULT_TARGET_REPS = 10;

function ClassificationPage() {
  // --- STATI E REF ---
  // Utilizza i dati predetti dal Context condiviso con FitnessClassifier
  const { prediction } = usePrediction();
  
  // Stati per i dati ricevuti in tempo reale (estratti dal Context)
  const reps = prediction.reps || 0;
  const phrase = prediction.phrase || 'Inquadrati per iniziare l\'esercizio.';
  const predictedExercise = prediction.exercise || "";
  const confidence = prediction.confidence || 0;
  
  const [selectedExercise, setSelectedExercise] = useState(null);
  const [selectedExercises, setSelectedExercises] = useState([]);
  const [stream, setStream] = useState(null);
  const [selectedTutorial, setSelectedTutorial] = useState(null);
  const [currentExerciseIndex, setCurrentExerciseIndex] = useState(0);
  const [isFeedbackModalVisible, setIsFeedbackModalVisible] = useState(false);  
  const [isWorkoutFeedbackModalVisible, setIsWorkoutFeedbackModalVisible] = useState(false);
  const [workoutComment, setWorkoutComment] = useState("");
  const [countdown, setCountdown] = useState(null); // Gestisce il numero del countdown (5, 4, 3...)
  const [isCountingActive, setIsCountingActive] = useState(false); // true solo dopo il countdown
  const [isCompletedVisible, setIsCompletedVisible] = useState(false);
  const [isStartLocked, setIsStartLocked] = useState(false);
  const [webcamWarningMessage, setWebcamWarningMessage] = useState("");
  const [isContinueAfterDifficultModalVisible, setIsContinueAfterDifficultModalVisible] = useState(false);
  const [pendingAdvanceAfterDifficult, setPendingAdvanceAfterDifficult] = useState(false);
  
  const [completedExercises, setCompletedExercises] = useState([]);
  const [exerciseStartTime, setExerciseStartTime] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [currentExerciseStarted, setCurrentExerciseStarted] = useState(false);
  const [isExerciseFinished, setIsExerciseFinished] = useState(false);

  const videoRef = useRef(null);

  const tutorialVideoRef = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();
  const isCountingActiveRef = useRef(false);

  const canvasRef = useRef(null);
  const cameraRef = useRef(null);

  const { backgroundColor } = useColor();

  useEffect(() => {
    isCountingActiveRef.current = isCountingActive;
  }, [isCountingActive]);


  /*funzione per mettere in pausa il video tutorial*/
  const pauseTutorialVideo = () => {
    if (!tutorialVideoRef.current) return;
    try {
      tutorialVideoRef.current.pause();
    } catch (e) {
      // ignore
    }
  };

  /*reset dello stato legato all'esercizio in corso, usato quando si avanza al prossimo esercizio o quando si interrompe l'esercizio corrente*/
  const resetExerciseRuntimeState = () => {
    setCountdown(null);
    setIsCountingActive(false);
    setIsStartLocked(false);
    setIsCompletedVisible(false);
  };

  /*effetto per caricare gli esercizi selezionati dalla navigazione o da localStorage al montaggio del componente o quando cambia location.state*/
  useEffect(() => {
    const fromNav = location?.state?.allenamentiSelezionati;
    if (Array.isArray(fromNav) && fromNav.length > 0) {
      // Se sono stringhe, le trasformiamo in oggetti
      const normalizedNav = fromNav.map((item, index) => 
        typeof item === 'string' ? { id: index + 1, nome: item, video_tut_url: null } : item
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
        // Se sono stringhe, le trasformiamo in oggetti
        const normalized = parsed.map((item, index) => 
          typeof item === 'string' ? { id: index + 1, nome: item, video_tut_url: 'wall-sit-with-medicine-ball-rotation.mp4' } : item
        );
        setSelectedExercises(normalized);
        console.log('Esercizi caricati da localStorage:', normalized);
        setCurrentExerciseIndex(0);
        setSelectedExercise(null);
      }
    } catch (e) {
      console.warn('allenamentiSelezionati non valido in localStorage', e);
      setSelectedExercises([]);
    }
  }, [location?.state]);

  /*funzione per tracciare un esercizio saltato (non iniziato)*/
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
      
      setCompletedExercises(prev => [...prev, skippedExerciseData]);
      console.log('Esercizio saltato tracciato:', skippedExerciseData);
    }
  };

  /*funzione per avanzare al prossimo esercizio dopo il feedback, usata sia quando l'utente dà un feedback normale (facil/medio/difficile) sia quando conferma di voler continuare dopo aver dato un feedback difficile*/
  const advanceAfterExerciseFeedback = () => {
    const nextIndex = currentExerciseIndex + 1;

    if (nextIndex < selectedExercises.length) {
      // Se l'esercizio attuale non è stato iniziato, traccialo come saltato
      if (selectedExercise && !currentExerciseStarted) {
        trackSkippedExercise(selectedExercise);
      }
      
      setCurrentExerciseIndex(nextIndex);
      setSelectedExercise(null);
      setReps(0);
      setCurrentExerciseStarted(false);
      resetExerciseRuntimeState();
      return;
    }

    // Se era l'ultimo esercizio, consideriamo la sessione finita
    // Se non è stato iniziato, traccialo come saltato
    if (selectedExercise && !currentExerciseStarted) {
      trackSkippedExercise(selectedExercise);
    }
    
    setCurrentExerciseIndex(selectedExercises.length);
    setSelectedExercise(null);
    setSelectedTutorial(null);
    setCurrentExerciseStarted(false);
    resetExerciseRuntimeState();
  };

  /*funzione chiamata quando l'utente fornisce un feedback dopo aver completato un esercizio, 
  se il feedback è "difficile" mostra un pop-up di conferma per evitare che l'utente dia per 
  errore un feedback negativo e interrompa la sessione, se invece è "medio" o "facile" avanza 
  direttamente al prossimo esercizio*/
  const handleFeedbackSubmit = (feedback) => {
    console.log(`Feedback esercizio: ${feedback}`);
    
    // Traccia il feedback dell'esercizio completato SOLO se è stato iniziato
    if (selectedExercise && currentExerciseStarted) {
      const exerciseData = {
        exercise_id: selectedExercise.id,
        exercise_name: selectedExercise.nome,
        completed: reps >= currentTargetReps,
        reps: reps,
        feedback: feedback,
        timestamp: exerciseStartTime 
          ? new Date(exerciseStartTime).toISOString() 
          : new Date().toISOString(),
      };
      
      // Aggiungi ai completed exercises
      setCompletedExercises(prev => [...prev, exerciseData]);
      console.log('Esercizio tracciato:', exerciseData);
    }
    
    setIsFeedbackModalVisible(false);

    if (feedback === 'difficile') {
      setPendingAdvanceAfterDifficult(true);
      setIsContinueAfterDifficultModalVisible(true);
      return;
    }

    advanceAfterExerciseFeedback();
  };
  

  /*funzione chiamata quando l'utente conferma di voler continuare dopo aver dato un feedback difficile, 
  chiude il pop-up e avanza al prossimo esercizio, se invece l'utente decide di non continuare chiude il 
  pop-up, ferma la webcam e reindirizza alla home*/
  const handleContinueAfterDifficultYes = () => {
    setIsContinueAfterDifficultModalVisible(false);
    if (pendingAdvanceAfterDifficult) {
      setPendingAdvanceAfterDifficult(false);
      advanceAfterExerciseFeedback();
    }
  };

  /*funzione chiamata quando l'utente decide di non continuare dopo aver dato un feedback difficile,
  chiude il pop-up, ferma la webcam e reindirizza alla home*/
  const handleContinueAfterDifficultNo = () => {
    setIsContinueAfterDifficultModalVisible(false);
    setPendingAdvanceAfterDifficult(false);
    navigate('/');
  };


  /*funzione chiamata quando l'utente decide di terminare l'allenamento, 
  chiude il pop-up, ferma la webcam e reindirizza alla home*/
  const handleFinishWorkout = async (feedback) => {
    // Se il feedback è un commento e non una faccina, usa il testo del commento
    const finalFeedback = feedback === 'comment' ? workoutComment : feedback;
    console.log(`Feedback finale allenamento: ${finalFeedback}`);
    console.log(`Esercizi completati: ${completedExercises.length}`);
    
    // Chiudi il pop-up
    setIsWorkoutFeedbackModalVisible(false);

    
    // Reindirizza l'utente alla pagina principale
    navigate('/');
  };

  // --- FUNZIONI DI CONTROLLO WEBCAM ---
  

  useEffect(() => {
    // Se il countdown non è attivo, non fare nulla
    if (countdown === null) return;
  
    // Se il countdown arriva a 0, avvia l'esercizio
    if (countdown === 0) {
      setCountdown(null); // Nasconde il countdown
      setIsCountingActive(true); // Attiva il conteggio delle ripetizioni
      setExerciseStartTime(Date.now()); // Registra l'inizio dell'esercizio

      return;
    }
  
    // Se il countdown è > 0, imposta un timer per scalarlo di 1 dopo un secondo
    const timer = setTimeout(() => {
      setCountdown(countdown - 1);
    }, 1000);
  
    // Pulisce il timer se il componente viene smontato
    return () => clearTimeout(timer);
  }, [countdown, selectedExercise]); // Dipende anche dall'esercizio selezionato

  const advanceToNextExercise = () => {
    const nextIndex = currentExerciseIndex + 1;
    if (nextIndex >= selectedExercises.length) {
      setCurrentExerciseIndex(selectedExercises.length);
      setSelectedExercise(null);
      setSelectedTutorial(null);
      setIsCountingActive(false);
      setCountdown(null);
      setIsStartLocked(false);
      return;
    }

    setCurrentExerciseIndex(nextIndex);
    const nextExercise = selectedExercises[nextIndex];
    handleExerciseSelect(nextExercise);
  };

  const currentTargetReps = DEFAULT_TARGET_REPS;
  const remainingReps = Math.max(currentTargetReps - reps, 0);

  /*effetto che si attiva quando le ripetizioni raggiungono o superano il target, 
  mostra il messaggio di completamento e dopo 1 secondo avanza al prossimo esercizio*/
  useEffect(() => {
    if (!isCountingActive) return;
    if (!selectedExercise) return;
    if (reps < currentTargetReps) return;

    setIsCompletedVisible(true);
    setIsCountingActive(false);
    setCountdown(null);
    setIsExerciseFinished(true);

    if (tutorialVideoRef.current) {
      try {
        tutorialVideoRef.current.pause();
      } catch (e) {
        // ignore
      }
    }

    const t = setTimeout(() => {
      setIsCompletedVisible(false);
      advanceToNextExercise();
    }, 1000);

    return () => clearTimeout(t);
  }, [reps, isCountingActive, selectedExercise]);


  /*funzione chiamata quando si seleziona un esercizio dalla lista, 
  imposta l'esercizio selezionato e carica il video tutorial corrispondente se presente*/
  const handleExerciseSelect = (exercise) => {
    if (exercise && exercise.id && exercise.nome) {
      setSelectedExercise(exercise);
      setCurrentExerciseStarted(false);
      setIsExerciseFinished(false);
      // Carica il video tutorial dall'oggetto esercizio
      if (exercise.video_tut_url) {
        setSelectedTutorial(exercise.video_tut_url);
      }
      resetExerciseRuntimeState();
    }
  };

  const handleStartExercise = () => {
    if (!selectedExercise) {
      return;
    }
    setCurrentExerciseStarted(true);
    setIsStartLocked(true);
    setCountdown(5);
  };

  const getExerciseDetails = (exerciseKey) => {
    const details = {
      'sollevamento_gambe_stringendo_la_fitball': {
        tool: 'Fitball (Palla Grande)',
        description: 'Sdraiati a terra supino, stringi la fitball tra le gambe e solleva il bacino contraendo i glutei.'
      },
      'braccia_con_miniball': {
        tool: 'Miniball (Palla Piccola 25/35 cm)',
        description: 'Disteso a pancia in giù, stringi la miniball tra le mani ed estendi il busto verso l\'alto controllando il movimento.'
      },
      'medicine_ball_squat': {
        tool: 'Palla Medica (Zavorrata)',
        description: 'In piedi con i piedi alla larghezza delle spalle, tieni la palla al petto ed esegui un profondo squat mantenendo la schiena dritta.'
      },
      'roll_out_sulla_fitball': {
        tool: 'Fitball (Palla Grande)',
        description: 'In ginocchio, appoggia gli avambracci sulla fitball e rotola in avanti attivando la stabilità del core senza inarcare i lombari.'
      },
      'fitball_back_extensions': {
        tool: 'Fitball (Palla Grande)',
        description: 'Posiziona l\'addome sulla fitball con i piedi stabili a terra, fletti il busto in avanti e poi estendilo controllando i muscoli della schiena.'
      },
      'overhead_ball_side_bends': {
        tool: 'Fitball o Palla Medica leggera',
        description: 'In piedi, solleva la palla sopra la testa a braccia tese ed esegui delle flessioni laterali stabili del busto.'
      }
    };

    return details[exerciseKey] || { tool: 'Seleziona un esercizio', description: 'In attesa che l\'IA rilevi il tuo movimento...' };
  };

  // --- JSX RENDER ---

  return (
    <div className="dashboard-container" style={{ '--colorvar': backgroundColor }}>
      {/* Sezione superiore fissa */}
      <div className="main-view-grid">
        {/* Pannello Webcam */}
        <div className="video-panel glass-card" style={{ flexDirection: 'column' }}>
          {/* Contenitore della webcam (parte grande) */}
          <div className="video-container" >
            <FitnessClassifier selectedExercise={selectedExercise} />
          </div>

          {/* Contenitore pulsanti (parte piccola) */}
          <div className="video-controls">

            {/*Pulsante Inizia */}
            {!isStartLocked && countdown === null && !isCountingActive ? (
              <button
                type="button"
                onClick={handleStartExercise}
                disabled={!selectedExercise}
                className="webcam-toggle-button"
                style={{
                  opacity: !selectedExercise ? 0.6 : 1,
                  cursor: !selectedExercise ? 'not-allowed' : 'pointer',
                }}
              >
                Inizia
              </button>
            ) : null}

            {isCompletedVisible && (
              <div className="completed-message" >
                Complimenti!
              </div>
            )}
            
          </div>
          
        
        
        </div>

        {/* PANNELLO TUTORIAL CON VISIBILITÀ CONDIZIONALE */}
        <div id="tutorial-panel" className={`video-panel glass-card ${!selectedTutorial ? 'panel-hidden' : ''}`}>
          <div className="video-container">
            {selectedTutorial ? (
              <video ref={tutorialVideoRef} key={selectedTutorial} controls autoPlay loop muted>
                <source src={selectedTutorial} type="video/mp4" />
              </video>
            ) : (
              <div className="video-placeholder">
                <p>Seleziona un esercizio per vedere il video tutorial</p>
              </div>
            )}
          </div>
        </div>

        {/* Pannello Ripetizioni ed Esercizio */}
        <div id="reps-panel" className="info-card glass-card">
          <div className="exercise-details">
            <h3>Esercizio Rilevato:</h3>
            <span className="exercise-detected-name">
              {predictedExercise ? predictedExercise.replace(/_/g, ' ').toUpperCase() : "In attesa..."}
              {confidence > 0 && ` (${confidence}%)`}
            </span>
            
            <h3>Strumento da usare:</h3> 
            <span>{getExerciseDetails(predictedExercise).tool}</span>
            
            <h3>Descrizione:</h3>
            <p>{getExerciseDetails(predictedExercise).description}</p>
          </div>

          {/* Visualizzazione gigante del contatore IA */}
          <div className="reps-counter-box" style={{ textAlign: 'center', marginTop: '15px' }}>
            <h2 style={{ fontSize: '1.2rem', color: 'var(--text-secondary, #aaa)', marginBottom: '5px' }}>RIPETIZIONI</h2>
            <span className="reps-number" style={{ fontSize: '3.5rem', fontWeight: 'bold', color: '#00ffcc' }}>
              {reps}
            </span>
          </div>
        </div>
        
        {/* Pannello Feedback */}
        <div id="feedback-panel" className="info-card glass-card trainer-feedback">
          <h3>FEEDBACK DEL COACH</h3>
          <p className="coach-phrase">{phrase}</p>
        </div>
      </div>

      {/* Sezione inferiore scorrevole */}
      <div id="workout-list-panel" className="info-card glass-card workout-list-card">
        <h3>ESERCIZI SELEZIONATI</h3>
        {selectedExercises.length === 0 ? (
          <p>
            Non hai selezionato esercizi. Vai in <Link to="/visualizza-esercizi">Galleria Esercizi</Link> e aggiungili.
          </p>
        ) : null}
        <ul className="exercise-list">
          {selectedExercises.map((item, index) => (
            <button
              key={index}
              className={selectedExercise?.id === item.id ? 'exercise-item active-exercise' : 'exercise-item'}
              onClick={() => handleExerciseSelect(item)}
              disabled={index !== currentExerciseIndex || countdown !== null || isCountingActive}
            >
              {item.nome}
            </button>
          ))}
        </ul>
        {isCompletedVisible && (
          <div className="completed-message">
            Completato!
          </div>
        )}
        {selectedExercises.length > 0 && currentExerciseIndex >= selectedExercises.length && (
          <div className="completed-message">
            Hai Finito!
          </div>
        )}
        {selectedExercise && (
          <div className="action-buttons-container">
            {currentExerciseIndex < selectedExercises.length - 1 && (
              <button className="finish-exercise-button" onClick={() => {
                if (isExerciseFinished) {
                  // Si attiva solo se l'esercizio è finito ("Prossimo Esercizio")
                  setIsFeedbackModalVisible(true);
                } else {
                  // Qui gestisci cosa succede quando c'è scritto "Salta Esercizio"
                  // Ad esempio, puoi passare direttamente all'esercizio successivo senza mostrare il modale
                  advanceToNextExercise(); 
                }
              }}>
                {isExerciseFinished ? 'Prossimo Esercizio' : 'Salta Esercizio'}
              </button>
            )}
            <button className="finish-workout-button" onClick={() => setIsWorkoutFeedbackModalVisible(true)}>
              Termina Allenamento
            </button>
          </div>
        )}
      </div>
      
      

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

      {isContinueAfterDifficultModalVisible && (
        <div className="modal-overlay">
          <div className="glass-card modal-content">
            <h3>Sei sicuro di riuscire a continuare?</h3>
            <div className="continue-buttons">
              <button className="continue-button" onClick={handleContinueAfterDifficultYes}>
                Si, posso continuare
              </button>
              <button className="finish-workout-button" onClick={handleContinueAfterDifficultNo}>
                No, voglio fermarmi
              </button>
            </div>
          </div>
        </div>
      )}

      {countdown !== null && (
        <div className="countdown-overlay">
          <p className="countdown-text">Il tuo esercizio inizia tra</p>
          <div className="countdown-number">{countdown}</div>
        </div>
      )}
    </div>
  );
}

export default ClassificationPage;