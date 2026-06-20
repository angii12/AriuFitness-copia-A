import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { Pose, POSE_CONNECTIONS } from "@mediapipe/pose";
import { drawConnectors, drawLandmarks } from "@mediapipe/drawing_utils";
import { Camera } from "@mediapipe/camera_utils";
import { supabase } from '../SupabaseClient';
import { useColor } from '../context/ColorContext';

import '../Dashboard.css';
import './ClassificationPage.css';
import FitnessClassifier from '../components/FitnessClassifier';

const DEFAULT_TARGET_REPS = 10;

function ClassificationPage() {
  // --- STATI E REF ---
  const [reps, setReps] = useState(0);
  const [phrase, setPhrase] = useState('Seleziona un esercizio e attiva la webcam per iniziare.');
  const [selectedExercise, setSelectedExercise] = useState(null);
  const [selectedExercises, setSelectedExercises] = useState([]);
  const [isWebcamActive, setIsWebcamActive] = useState(false);
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

  //configurare MediaPipe una volta che il componente è montato
  /*useEffect(() => {
    if (!isWebcamActive || !videoRef.current) return;

    const pose = new Pose({
      locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`,
    });

    pose.setOptions({
      modelComplexity: 1, // 0: Lite, 1: Full, 2: Heavy (1 è il miglior compromesso)
      smoothLandmarks: true,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5,
    });

    pose.onResults((results) => {
      if (!canvasRef.current || !videoRef.current) return;

      const canvasCtx = canvasRef.current.getContext("2d");
      const { width, height } = canvasRef.current;

      // Pulisce il canvas prima di ogni disegno
      canvasCtx.save();
      canvasCtx.clearRect(0, 0, width, height);

      // Disegna lo "stickman" (punti e connessioni)
      if (results.poseLandmarks) {
        drawConnectors(canvasCtx, results.poseLandmarks, POSE_CONNECTIONS, {
          color: "#00FF00",
          lineWidth: 4,
        });
        drawLandmarks(canvasCtx, results.poseLandmarks, {
          color: "#FF0000",
          lineWidth: 2,
          radius: 3,
        });
      }
      canvasCtx.restore();
    });

    // Collega MediaPipe al feed video esistente
    if (videoRef.current) {
      cameraRef.current = new Camera(videoRef.current, {
        onFrame: async () => {
          await pose.send({ image: videoRef.current });
        },
        width: 640,
        height: 480,
      });
      cameraRef.current.start();
    }

    return () => {
      if (cameraRef.current) cameraRef.current.stop();
      pose.close();
    };
  }, [isWebcamActive]); // Si riattiva quando accendi la webcam*/

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
      setPhrase("Seleziona il prossimo esercizio per continuare.");
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
    setPhrase('Hai Finito!');
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
    stopWebcam();
    navigate('/');
  };

  /*funzione per salvare i dati degli esercizi completati in database*/
  const saveWorkoutToDatabase = async (workoutFeedback, exercisesToSave = completedExercises) => {
    try {
      setIsSaving(true);
      
      // Ottieni l'utente da localStorage
      const userJson = localStorage.getItem('user');
      if (!userJson) {
        console.error('Errore: utente non trovato in localStorage');
        return false;
      }
      
      const user = JSON.parse(userJson);
      const userId = user.id;
      
      console.log(`Salvataggio workout per utente: ${userId}`);
      console.log(`Numero di esercizi completati: ${exercisesToSave.length}`);
      
      // Salva ogni esercizio nel database
      for (const exercise of exercisesToSave) {
        const { error } = await supabase
          .from('allenamenti')
          .insert([
            {
              utente: userId,
              esercizio: exercise.exercise_id,
              completato: exercise.completed,
              feedback: exercise.feedback,
            }
          ]);
        
        if (error) {
          console.error('Errore nel salvataggio dell\'esercizio:', error);
          return false;
        }
        
        console.log(`Esercizio ${exercise.exercise_name} salvato con successo`);
      }
      
      console.log('Workout salvato completamente');
      return true;
    } catch (err) {
      console.error('Errore durante il salvataggio del workout:', err);
      return false;
    } finally {
      setIsSaving(false);
    }
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
    
    // Controlla se c'è un esercizio in corso non tracciato
    /*let exercisesToSave = [...completedExercises];
    if (selectedExercise && currentExerciseIndex < selectedExercises.length) {
      // Verifica se questo esercizio è già stato tracciato
      const alreadyTracked = completedExercises.some(ex => ex.exercise_id === selectedExercise.id);
      
      if (!alreadyTracked) {
        // Se l'esercizio è stato iniziato
        if (currentExerciseStarted) {
          const lastExerciseData = {
            exercise_id: selectedExercise.id,
            exercise_name: selectedExercise.nome,
            completed: reps >= currentTargetReps,
            reps: reps,
            feedback: finalFeedback, // Default feedback se non è stato fornito
            timestamp: exerciseStartTime 
              ? new Date(exerciseStartTime).toISOString() 
              : new Date().toISOString(),
          };
          exercisesToSave = [...exercisesToSave, lastExerciseData];
          console.log('Ultimo esercizio aggiunto al salvataggio:', lastExerciseData);
        } else {
          // Se l'esercizio NON è stato iniziato, traccialo come saltato
          const skippedExerciseData = {
            exercise_id: selectedExercise.id,
            exercise_name: selectedExercise.nome,
            completed: false,
            reps: 0,
            feedback: null,
            timestamp: new Date().toISOString(),
          };
          exercisesToSave = [...exercisesToSave, skippedExerciseData];
          console.log('Esercizio saltato aggiunto al salvataggio:', skippedExerciseData);
        }
      }
    }
    
    // Salva il workout nel database
    const saved = await saveWorkoutToDatabase(finalFeedback, exercisesToSave);
    
    if (saved) {
      console.log('Workout salvato con successo!');
    } else {
      console.warn('Errore nel salvataggio del workout, ma comunque reindirizzando...');
    }
    */
    // Spegni la webcam e altre pulizie se necessario
    stopWebcam();
    
    // Reindirizza l'utente alla pagina principale
    navigate('/');
  };

  // --- FUNZIONI DI CONTROLLO WEBCAM ---
  const startWebcam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      setStream(stream);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      } else {
        console.error("ERRORE: videoRef.current è nullo! Impossibile mostrare il video.");
      }
      setIsWebcamActive(true);
    } catch (err) {
      console.error("Errore nell'accesso alla webcam:", err);
      setPhrase("Accesso alla webcam negato. Controlla i permessi del browser.");
    }
  };  

  const stopWebcam = () => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
    }
    setIsWebcamActive(false);
    setStream(null);
  };

  const handleWebcamToggle = () => {
    if (isWebcamActive) {
      stopWebcam();
    } else {
      startWebcam();
    }
  };

  useEffect(() => {
    // Se la webcam viene spenta durante l'esercizio, fermiamo tutorial e mettiamo in pausa la sessione.
    if (isWebcamActive) {
      setWebcamWarningMessage("");
      return;
    }

    const wasInExercise = isStartLocked || countdown !== null || isCountingActive;
    if (!wasInExercise) return;

    pauseTutorialVideo();
    resetExerciseRuntimeState();
    const msg = 'Attenzione! Non riusciamo a rilevare la videocamera!';
    setWebcamWarningMessage(msg);
    setPhrase(msg);
  }, [isWebcamActive]);
  

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
      setPhrase('Hai Finito!');
      return;
    }

    setCurrentExerciseIndex(nextIndex);
    const nextExercise = selectedExercises[nextIndex];
    handleExerciseSelect(nextExercise);
    setPhrase('Pronto per il prossimo esercizio. Premi Inizia quando vuoi partire.');
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

  

  const handleManualAddReps = (delta) => {
    setReps((prev) => prev + delta);
  };

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
    if (!selectedExercise || !isWebcamActive) {
      return;
    }
    setCurrentExerciseStarted(true);
    setIsStartLocked(true);
    setCountdown(5);
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
            <FitnessClassifier />
          </div>

          {/* Contenitore pulsanti (parte piccola) */}
          <div className="video-controls">

            {/*Pulsante Inizia */}
            {!isStartLocked && countdown === null && !isCountingActive ? (
              <button
                type="button"
                onClick={handleStartExercise}
                disabled={!isWebcamActive || !selectedExercise}
                className="webcam-toggle-button"
                style={{
                  opacity: !isWebcamActive || !selectedExercise ? 0.6 : 1,
                  cursor: !isWebcamActive || !selectedExercise ? 'not-allowed' : 'pointer',
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

        {/* Pannello Ripetizioni */}
        <div id="reps-panel" className="info-card glass-card">
          <div>
            <h3>Strumento da usare:</h3> <span>palla 25/35/45 cm</span>
            <h3>Descrizione:</h3><p>descrizione dell'esercizio</p>
          </div>
          <div className='reps-buttons' >
            <button
              type="button"
              onClick={() => handleManualAddReps(1)}
              disabled={!selectedExercise || countdown !== null || !isCountingActive}
              className="reset-button"
              style={{ cursor: !selectedExercise || !isCountingActive ? 'not-allowed' : 'pointer', opacity: !selectedExercise || !isCountingActive ? 0.6 : 1 }}
            >
              +1
            </button>
            <button
              type="button"
              onClick={() => handleManualAddReps(5)}
              disabled={!selectedExercise || countdown !== null || !isCountingActive}
              className="reset-button"
              style={{ cursor: !selectedExercise || !isCountingActive ? 'not-allowed' : 'pointer', opacity: !selectedExercise || !isCountingActive ? 0.6 : 1 }}
            >
              +5
            </button>
          </div>
        </div>
        
        {/* Pannello Feedback */}
        <div id="feedback-panel" className="info-card glass-card trainer-feedback">
          <h3>FEEDBACK DEL COACH</h3>
          <p>{phrase}</p>
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