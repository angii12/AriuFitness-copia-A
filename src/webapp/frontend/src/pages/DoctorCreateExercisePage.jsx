import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import BodyJointSelector from '../components/BodyJointSelector';
import { supabase } from '../SupabaseClient';
import './DoctorCreateExercisePage.css';

const API_BASE_URL = 'http://localhost:8000';

const RepMiniPlayer = ({ rep, exerciseId }) => {
  const videoRef = useRef(null);
  const [error, setError] = useState(false);

  // Fallback to 30 fps if not provided by the backend (as documented in implementation plan)
  const fps = rep.fps || 30.0;
  const startTime = rep.start_frame / fps;
  const endTime = rep.end_frame / fps;

  const handleTimeUpdate = () => {
    if (videoRef.current && videoRef.current.currentTime >= endTime) {
      videoRef.current.pause();
      videoRef.current.currentTime = startTime;
    }
  };

  const handlePlay = () => {
    if (videoRef.current && (videoRef.current.currentTime < startTime || videoRef.current.currentTime >= endTime)) {
      videoRef.current.currentTime = startTime;
    }
  };

  const handleReplay = () => {
    if (videoRef.current) {
      videoRef.current.currentTime = startTime;
      videoRef.current.play();
    }
  };

  if (error || !rep.video_source) {
    return <div style={{ padding: '10px', color: '#ff4d4d', fontStyle: 'italic', fontSize: '0.9rem' }}>Video non disponibile</div>;
  }

  const videoUrl = `${API_BASE_URL}/uploads/videos/${exerciseId}/${rep.video_source}`;

  return (
    <div className="rep-mini-player" style={{ marginTop: '10px', marginBottom: '10px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <video
        ref={videoRef}
        src={`${videoUrl}#t=${startTime},${endTime}`}
        onTimeUpdate={handleTimeUpdate}
        onPlay={handlePlay}
        onError={() => setError(true)}
        controls
        preload="metadata"
        style={{ width: '100%', maxHeight: '180px', backgroundColor: '#000', borderRadius: '8px' }}
      />
      <button 
        type="button" 
        onClick={handleReplay} 
        style={{ marginTop: '8px', padding: '6px 12px', fontSize: '0.85rem', cursor: 'pointer', borderRadius: '4px', border: '1px solid #ccc', backgroundColor: '#f9f9f9', display: 'flex', alignItems: 'center', gap: '5px' }}>
        <span>🔄</span> Replay REP
      </button>
    </div>
  );
};

function DoctorCreateExercisePage() {
  const [activeStep, setActiveStep] = useState(1); // 1: Info & Config, 2: Upload Video & Process, 3: REP Review, 4: Training & Result
  
  // Form esercizio
  const [exerciseId, setExerciseId] = useState('');
  const [nome, setNome] = useState('');
  const [descrizione, setDescrizione] = useState('');
  const [signalMode, setSignalMode] = useState('auto'); // 'auto' | 'doctor_guided'
  const [selectedJoints, setSelectedJoints] = useState([]);
  const [expectedReps, setExpectedReps] = useState('');

  // Video Caricamento (Multi-video)
  const [videoFiles, setVideoFiles] = useState([]);
  const [isDragActive, setIsDragActive] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processLogs, setProcessLogs] = useState([]);
  const [processingError, setProcessingError] = useState('');

  // Reps per review
  const [repsList, setRepsList] = useState([]);
  const [repReviews, setRepReviews] = useState({}); // { rep_index: boolean }

  // Training & Risultati
  const [isTraining, setIsTraining] = useState(false);
  const [trainingResult, setTrainingResult] = useState(null);
  const [trainingError, setTrainingError] = useState('');

  // Auto-genera exercise_id da nome se vuoto
  const handleNomeChange = (e) => {
    const val = e.target.value;
    setNome(val);
    if (!exerciseId || exerciseId.startsWith('ex_')) {
      const slug = 'ex_' + val.toLowerCase().trim().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
      setExerciseId(slug);
    }
  };

  const processSelectedFiles = (newFiles) => {
    const validFiles = Array.from(newFiles).filter(f => 
      f.type.startsWith('video/') || f.name.match(/\.(mp4|mov)$/i)
    );

    if (validFiles.length === 0) return;

    setVideoFiles(prev => {
      const allFiles = [...prev];
      validFiles.forEach(file => {
        const isDuplicate = allFiles.some(f => 
          f.name === file.name && f.size === file.size && f.lastModified === file.lastModified
        );
        if (!isDuplicate) {
          allFiles.push(file);
        }
      });
      return allFiles;
    });
  };

  const handleVideoSelection = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      processSelectedFiles(e.target.files);
    }
    // reset input value so the same file can be selected again if needed
    e.target.value = null;
  };

  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(true);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    // Previene il flickering quando si passa su elementi figli
    if (!e.currentTarget.contains(e.relatedTarget)) {
      setIsDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processSelectedFiles(e.dataTransfer.files);
    }
  };

  const addLog = (msg) => {
    setProcessLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
  };

  // Step 1 -> Step 2 Validation
  const handleProceedToVideo = (e) => {
    e.preventDefault();
    if (!exerciseId.trim() || !nome.trim()) {
      alert('Inserisci l\'ID e il Nome dell\'esercizio.');
      return;
    }
    if (signalMode === 'doctor_guided' && selectedJoints.length === 0) {
      alert('In modalità DOCTOR_GUIDED devi selezionare almeno un\'articolazione sul corpo umano.');
      return;
    }
    setActiveStep(2);
  };

  // Helper function to get valid auth headers from Supabase session
  const getAuthHeaders = async () => {
    const { data: { session }, error } = await supabase.auth.getSession();
    if (error || !session?.access_token) {
      throw new Error('Sessione non valida o scaduta. Effettua nuovamente il login.');
    }
    return { Authorization: `Bearer ${session.access_token}` };
  };

  // Processamento Esercizio e Video caricati
  const handleProcessExerciseAndVideos = async () => {
    if (videoFiles.length === 0) {
      alert('Seleziona almeno un video per l\'esercizio.');
      return;
    }

    setIsProcessing(true);
    setProcessingError('');
    setProcessLogs([]);

    try {
      // 1. Creazione Esercizio e Profilo sul DB
      addLog(`Creazione esercizio '${exerciseId}' e profilo su Supabase...`);
      const authHeaders = await getAuthHeaders();
      
      await axios.post(`${API_BASE_URL}/api/doctor/exercises`, {
        exercise_id: exerciseId,
        nome: nome,
        descrizione: descrizione,
        categoria: 'Riabilitazione',
        signal_selection_mode: signalMode,
        doctor_selected_joints: signalMode === 'doctor_guided' ? selectedJoints : [],
        expected_reps: expectedReps ? parseInt(expectedReps, 10) : null
      }, { headers: authHeaders });
      addLog(`[OK] Esercizio '${exerciseId}' registrato nel sistema.`);

      // 2. Upload e Segmentazione di ciascun Video
      let allProcessedReps = [];
      for (let i = 0; i < videoFiles.length; i++) {
        const file = videoFiles[i];
        addLog(`Caricamento video ${i + 1}/${videoFiles.length}: ${file.name}...`);

        const formData = new FormData();
        formData.append('file', file);

        const uploadRes = await axios.post(
          `${API_BASE_URL}/api/doctor/exercises/${exerciseId}/upload-video`,
          formData,
          { headers: authHeaders }
        );
        
        const videoPath = uploadRes.data.video_path;
        addLog(`[OK] Video salvato. Avvio segmentazione Rehab-AI MediaPipe...`);

        const segmentRes = await axios.post(
          `${API_BASE_URL}/api/doctor/exercises/${exerciseId}/segment-video`,
          {
            video_path: videoPath,
            signal_selection_mode: signalMode,
            doctor_selected_joints: signalMode === 'doctor_guided' ? selectedJoints : [],
            expected_reps: expectedReps ? parseInt(expectedReps, 10) : null
          },
          { headers: authHeaders }
        );

        const reps = segmentRes.data.result.reps || [];
        addLog(`[OK] Rilevate ${reps.length} REP nel video ${file.name}.`);
        allProcessedReps = [...allProcessedReps, ...reps];
      }

      // 3. Lettura REP salvate per la review
      const repsRes = await axios.get(`${API_BASE_URL}/api/doctor/exercises/${exerciseId}/reps`, { headers: authHeaders });
      const fetchedReps = repsRes.data.reps || [];
      setRepsList(fetchedReps);

      // Inizializza tutte le REP a true (accettate di default) con identificatore univoco per video
      const initialReviews = {};
      fetchedReps.forEach(r => {
        const key = r.id || `${r.video_source || 'video'}__${r.rep_index}`;
        initialReviews[key] = true;
      });
      setRepReviews(initialReviews);

      addLog(`[COMPLETATO] Elaborazione completata. Rilevate in totale ${fetchedReps.length} REP.`);
      setIsProcessing(false);
      setActiveStep(3);

    } catch (err) {
      console.error(err);
      const msg = err.response?.data?.detail || err.message;
      setProcessingError(`Errore durante l'elaborazione: ${msg}`);
      addLog(`[ERRORE] ${msg}`);
      setIsProcessing(false);
    }
  };

  const getRepKey = (r) => r.id || `${r.video_source || 'video'}__${r.rep_index}`;

  // Toggle accettazione singola REP
  const toggleRepAcceptance = (rep) => {
    const key = getRepKey(rep);
    setRepReviews(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  // Accetta tutte le REP
  const acceptAllReps = () => {
    const updated = {};
    repsList.forEach(r => {
      updated[getRepKey(r)] = true;
    });
    setRepReviews(updated);
  };

  // Rifiuta tutte le REP
  const rejectAllReps = () => {
    const updated = {};
    repsList.forEach(r => {
      updated[getRepKey(r)] = false;
    });
    setRepReviews(updated);
  };

  // Invio Review e Avvio Training TwoBranchLSTM
  const handleSaveReviewAndTrain = async () => {
    const acceptedCount = Object.values(repReviews).filter(Boolean).length;
    if (acceptedCount === 0) {
      alert('Devi accettare almeno 1 REP per procedere con l\'addestramento del modello.');
      return;
    }

    setIsTraining(true);
    setTrainingError('');
    setActiveStep(4);

    try {
      const authHeaders = await getAuthHeaders();

      // 1. Invia la review al backend con riferimento a id, video_source e rep_index
      const reviewPayload = {
        reviews: repsList.map(r => ({
          id: r.id,
          video_source: r.video_source,
          rep_index: r.rep_index,
          accettata: Boolean(repReviews[getRepKey(r)])
        }))
      };

      await axios.post(
        `${API_BASE_URL}/api/doctor/exercises/${exerciseId}/reps/review`, 
        reviewPayload, 
        { headers: authHeaders }
      );

      // 2. Avvia il training multi-negative
      const trainRes = await axios.post(
        `${API_BASE_URL}/api/doctor/exercises/${exerciseId}/train`, 
        {
          epochs: 25,
          batch_size: 32,
          seed: 42
        },
        { headers: authHeaders }
      );

      setTrainingResult(trainRes.data);
      setIsTraining(false);

    } catch (err) {
      console.error(err);
      const msg = err.response?.data?.detail || err.message;
      setTrainingError(`Errore durante l'addestramento: ${msg}`);
      setIsTraining(false);
    }
  };

  return (
    <div className="doctor-page-container">
      <div className="doctor-header-card glass-card">
        <h2>Creazione Nuovo Esercizio Clinico</h2>
        <p className="doctor-subtitle">
          Configura l'esercizio, definisci le articolazioni guida, carica i video dimostrativi e approva le ripetizioni segmentate.
        </p>

        {/* Stepper progressivo */}
        <div className="stepper-nav">
          <div className={`step-item ${activeStep >= 1 ? 'active' : ''}`}>1. Configurazione</div>
          <div className={`step-item ${activeStep >= 2 ? 'active' : ''}`}>2. Upload Video</div>
          <div className={`step-item ${activeStep >= 3 ? 'active' : ''}`}>3. Review REP</div>
          <div className={`step-item ${activeStep >= 4 ? 'active' : ''}`}>4. Training Modello</div>
        </div>
      </div>

      {/* STEP 1: FORM CONFIGURAZIONE */}
      {activeStep === 1 && (
        <div className="doctor-card glass-card">
          <h3>Passo 1: Dettagli Esercizio e Modalità Clinica</h3>
          <form onSubmit={handleProceedToVideo} className="doctor-form">
            
            <div className="form-group">
              <label htmlFor="nome">Nome Esercizio *</label>
              <input
                id="nome"
                type="text"
                value={nome}
                onChange={handleNomeChange}
                placeholder="Es. Piegamento Ginocchio o Sollevamento Braccia"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="exerciseId">Codice Esercizio (ID Univoco) *</label>
              <input
                id="exerciseId"
                type="text"
                value={exerciseId}
                onChange={(e) => setExerciseId(e.target.value)}
                placeholder="Es. ex_piegamento_ginocchio"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="descrizione">Descrizione & Istruzioni Cliniche</label>
              <textarea
                id="descrizione"
                value={descrizione}
                onChange={(e) => setDescrizione(e.target.value)}
                placeholder="Note sull'esecuzione corretta dell'esercizio per il paziente..."
                rows="3"
              />
            </div>

            <div className="form-group">
              <label>Modalità di Selezione Segnali / Articolazioni *</label>
              <div className="radio-group-mode">
                <label className={`radio-card ${signalMode === 'auto' ? 'selected' : ''}`}>
                  <input
                    type="radio"
                    name="signalMode"
                    value="auto"
                    checked={signalMode === 'auto'}
                    onChange={(e) => setSignalMode(e.target.value)}
                  />
                  <div>
                    <strong>AUTO (Pipeline Automatica Rehab-AI)</strong>
                    <p>Rileva in autonomia l'articolazione biomeccanicamente dominante.</p>
                  </div>
                </label>

                <label className={`radio-card ${signalMode === 'doctor_guided' ? 'selected' : ''}`}>
                  <input
                    type="radio"
                    name="signalMode"
                    value="doctor_guided"
                    checked={signalMode === 'doctor_guided'}
                    onChange={(e) => setSignalMode(e.target.value)}
                  />
                  <div>
                    <strong>DOCTOR_GUIDED (Guidata dal Medico)</strong>
                    <p>Seleziona manualmente le articolazioni specifiche su cui eseguire la validazione.</p>
                  </div>
                </label>
              </div>
            </div>

            {/* SELEZIONATORE ARTICOLAZIONI OMINO 2D */}
            {signalMode === 'doctor_guided' && (
              <div className="joint-selector-section">
                <BodyJointSelector
                  selectedJoints={selectedJoints}
                  onJointToggle={setSelectedJoints}
                />
              </div>
            )}

            <div className="form-group">
              <label htmlFor="expectedReps">Ripetizioni Attese per Video (Opzionale)</label>
              <input
                id="expectedReps"
                type="number"
                min="1"
                max="50"
                value={expectedReps}
                onChange={(e) => setExpectedReps(e.target.value)}
                placeholder="Lascia vuoto per rilevamento automatico Rest-to-Rest"
              />
            </div>

            <button type="submit" className="action-button primary">
              Continua al Caricamento Video ➔
            </button>
          </form>
        </div>
      )}

      {/* STEP 2: UPLOAD VIDEO & PROCESSAMENTO */}
      {activeStep === 2 && (
        <div className="doctor-card glass-card">
          <h3>Passo 2: Upload Video Dimostrativi (1 o più video)</h3>
          
          <div 
            className={`video-upload-box ${isDragActive ? 'drag-active' : ''}`}
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <input
              type="file"
              id="video-input"
              accept="video/*"
              multiple
              onChange={handleVideoSelection}
              disabled={isProcessing}
            />
            <label htmlFor="video-input" className="file-drop-label">
              📁 <strong>Clicca o trascina qui i video dell'esercizio</strong>
              <span>(Puoi selezionare 1 o più file video .mp4, .mov)</span>
            </label>
          </div>

          {videoFiles.length > 0 && (
            <div className="file-list-preview">
              <h4>Video Selezionati ({videoFiles.length}):</h4>
              <ul>
                {videoFiles.map((file, idx) => (
                  <li key={idx}>
                    🎥 <strong>{file.name}</strong> ({(file.size / (1024 * 1024)).toFixed(2)} MB)
                  </li>
                ))}
              </ul>
            </div>
          )}

          {processLogs.length > 0 && (
            <div className="log-output-box">
              <h4>Log Processamento Pipeline:</h4>
              <div className="log-content">
                {processLogs.map((log, idx) => (
                  <div key={idx}>{log}</div>
                ))}
              </div>
            </div>
          )}

          {processingError && <p className="error-message">{processingError}</p>}

          <div className="button-row">
            <button
              type="button"
              className="action-button secondary"
              onClick={() => setActiveStep(1)}
              disabled={isProcessing}
            >
              ⬅ Indietro
            </button>

            <button
              type="button"
              className="action-button primary"
              onClick={handleProcessExerciseAndVideos}
              disabled={isProcessing || videoFiles.length === 0}
            >
              {isProcessing ? '⏳ Processamento in corso...' : '⚡ Salva & Processa Video'}
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: REVIEW RIPETIZIONI */}
      {activeStep === 3 && (
        <div className="doctor-card glass-card">
          <h3>Passo 3: Revisione Clinica delle Ripetizioni (REP)</h3>
          <p className="step-desc">
            La pipeline Rehab-AI ha segmentato le seguenti ripetizioni. Approva le REP eseguite correttamente per l'addestramento.
          </p>

          <div className="rep-actions-bar">
            <button type="button" className="btn-small success" onClick={acceptAllReps}>
              ✓ Accetta Tutte
            </button>
            <button type="button" className="btn-small danger" onClick={rejectAllReps}>
              ✕ Rifiuta Tutte
            </button>
            <span className="summary-count">
              Accettate: <strong>{Object.values(repReviews).filter(Boolean).length}</strong> su {repsList.length}
            </span>
          </div>

          <div className="reps-grid">
            {repsList.map((rep, repIdx) => {
              const repKey = getRepKey(rep);
              const isAccepted = Boolean(repReviews[repKey]);
              const durationSec = (rep.end_frame - rep.start_frame) / 30.0; // Stima durata indicativa

              return (
                <div key={rep.id || `${repKey}_${repIdx}`} className={`rep-card ${isAccepted ? 'accepted' : 'rejected'}`}>
                  <div className="rep-card-header">
                    <span className="rep-badge">REP #{rep.rep_index}</span>
                    <span className="video-source-tag">📹 {rep.video_source || 'video'}</span>
                  </div>

                  <div className="rep-details">
                    <div>⏱ Durata: <strong>~{durationSec.toFixed(1)}s</strong> (Frame {rep.start_frame} - {rep.end_frame})</div>
                    {rep.doctor_validation && (
                      <div> Validazione: <span className={`val-badge ${rep.doctor_validation}`}>{rep.doctor_validation}</span></div>
                    )}
                  </div>

                  <RepMiniPlayer rep={rep} exerciseId={exerciseId} />

                  <div className="rep-toggle-row">
                    <button
                      type="button"
                      className={`toggle-btn ${isAccepted ? 'is-accepted' : 'is-rejected'}`}
                      onClick={() => toggleRepAcceptance(rep)}
                    >
                      {isAccepted ? '✓ Accettata per Training' : '✕ Rifiutata (Esclusa)'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="button-row">
            <button
              type="button"
              className="action-button secondary"
              onClick={() => setActiveStep(2)}
            >
              ⬅ Indietro
            </button>

            <button
              type="button"
              className="action-button success-large"
              onClick={handleSaveReviewAndTrain}
            >
              🚀 Salva Review & Addestra Modello TwoBranchLSTM
            </button>
          </div>
        </div>
      )}

      {/* STEP 4: TRAINING & RISULTATI */}
      {activeStep === 4 && (
        <div className="doctor-card glass-card">
          <h3>Passo 4: Addestramento Modello Multi-Negative</h3>

          {isTraining ? (
            <div className="training-loader-box">
              <div className="spinner"></div>
              <h4>Addestramento TwoBranchLSTM in corso...</h4>
              <p>Generazione finestre temporali, applicazione Data Augmentation ed estrazione campioni multi-negative.</p>
            </div>
          ) : trainingError ? (
            <div className="error-box">
              <h4>❌ Si è verificato un errore</h4>
              <p>{trainingError}</p>
              <button
                type="button"
                className="action-button secondary"
                onClick={() => setActiveStep(3)}
              >
                ⬅ Torna alla Review REP
              </button>
            </div>
          ) : (
            <div className="training-success-box">
              <div className="success-icon">🎉</div>
              <h3>Modello Addestrato e Registrato con Successo!</h3>
              <p>Il modello <strong>{exerciseId}</strong> è stato salvato nel Registro Modelli di Produzione ed è pronto per l'inferenza live.</p>

              {trainingResult && (
                <div className="metrics-card">
                  <h4>Metriche di Validazione (Best Epoch {trainingResult.train_result?.metrics?.epoch || 1}):</h4>
                  <div className="metrics-grid">
                    <div className="metric-pill">
                      <span>F1-Score</span>
                      <strong>{((trainingResult.train_result?.metrics?.f1 || 0) * 100).toFixed(1)}%</strong>
                    </div>
                    <div className="metric-pill">
                      <span>Accuracy</span>
                      <strong>{((trainingResult.train_result?.metrics?.accuracy || 0) * 100).toFixed(1)}%</strong>
                    </div>
                    <div className="metric-pill">
                      <span>Precision</span>
                      <strong>{((trainingResult.train_result?.metrics?.precision || 0) * 100).toFixed(1)}%</strong>
                    </div>
                    <div className="metric-pill">
                      <span>Recall</span>
                      <strong>{((trainingResult.train_result?.metrics?.recall || 0) * 100).toFixed(1)}%</strong>
                    </div>
                  </div>
                </div>
              )}

              <div className="button-row">
                <button
                  type="button"
                  className="action-button primary"
                  onClick={() => {
                    setActiveStep(1);
                    setExerciseId('');
                    setNome('');
                    setDescrizione('');
                    setVideoFiles([]);
                    setRepsList([]);
                    setTrainingResult(null);
                  }}
                >
                  ➕ Crea un Altro Esercizio
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default DoctorCreateExercisePage;
