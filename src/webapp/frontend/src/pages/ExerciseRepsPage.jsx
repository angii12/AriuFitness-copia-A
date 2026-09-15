import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { supabase } from '../SupabaseClient';
import { API_BASE_URL } from '../config/api';
import '../index.css';
import './ExerciseRepsPage.css';

export default function ExerciseRepsPage() {
  const { exerciseId } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [exerciseData, setExerciseData] = useState(null);
  const [videos, setVideos] = useState([]);
  const [repsList, setRepsList] = useState([]);

  // SHARED PLAYER STATE
  const [selectedRep, setSelectedRep] = useState(null);
  const [currentVideoUrl, setCurrentVideoUrl] = useState('');
  const videoRef = useRef(null);
  const pendingSeekRef = useRef(null);

  // AUTH
  const getAuthHeaders = async () => {
    const { data: { session }, error: sessionError } = await supabase.auth.getSession();
    if (sessionError || !session?.access_token) {
      throw new Error('Sessione non valida o scaduta. Effettua nuovamente il login.');
    }
    return { Authorization: `Bearer ${session.access_token}` };
  };

  // FETCH EXERCISE DETAILS
  useEffect(() => {
    if (!exerciseId) return;

    const fetchDetails = async () => {
      try {
        setLoading(true);
        setError(null);
        const headers = await getAuthHeaders();
        const res = await axios.get(
          `${API_BASE_URL}/api/doctor/exercises/${exerciseId}/details`,
          { headers }
        );

        setExerciseData(res.data?.exercise || null);
        setVideos(res.data?.videos || []);
        setRepsList(res.data?.reps_summary?.list || []);
      } catch (err) {
        console.error(err);
        setError("Impossibile caricare i dati delle ripetizioni per questo esercizio.");
      } finally {
        setLoading(false);
      }
    };

    fetchDetails();
  }, [exerciseId]);

  // NAVIGATION BACK TO EXERCISE DETAIL
  const handleBackToDetail = () => {
    navigate(`/medico/esercizi/${exerciseId}`);
  };

  // RIPRODUZIONE DEL SEGMENTO SELEZIONATO
  const handleSelectRep = (rep) => {
    setSelectedRep(rep);

    // Cerca il video associato alla REP
    const matched =
      videos.find((v) => v.filename === rep.video_source) ||
      (videos.length > 0 ? videos[0] : null);

    if (!matched || !matched.url) {
      console.warn("Nessun video associato trovato per", rep.video_source);
      return;
    }

    const startSec = rep.start_sec != null ? rep.start_sec : 0;
    const videoEl = videoRef.current;

    if (currentVideoUrl !== matched.url) {
      // Cambio video source: programma il seek una volta caricati i metadati
      pendingSeekRef.current = startSec;
      setCurrentVideoUrl(matched.url);
    } else if (videoEl) {
      // Stesso video già in memoria: seek immediato e riproduzione
      try {
        videoEl.currentTime = startSec;
        const playPromise = videoEl.play();
        if (playPromise !== undefined) {
          playPromise.catch((e) => console.log("Play interrotto o impedito dal browser:", e));
        }
      } catch (e) {
        console.error("Errore seek/play video:", e);
      }
    }
  };

  // QUANDO I METADATI DEL NUOVO VIDEO SONO CARICATI
  const handleLoadedMetadata = () => {
    const videoEl = videoRef.current;
    if (!videoEl) return;

    if (pendingSeekRef.current != null) {
      const targetStart = pendingSeekRef.current;
      pendingSeekRef.current = null;
      try {
        videoEl.currentTime = targetStart;
        const playPromise = videoEl.play();
        if (playPromise !== undefined) {
          playPromise.catch((e) => console.log("Play interrotto:", e));
        }
      } catch (e) {
        console.error("Errore play on loaded metadata:", e);
      }
    }
  };

  // FERMA LA RIPRODUZIONE QUANDO CURRENT_TIME RAGGIUNGE END_SEC
  const handleTimeUpdate = () => {
    const videoEl = videoRef.current;
    if (!videoEl || !selectedRep || selectedRep.end_sec == null) return;

    if (videoEl.currentTime >= selectedRep.end_sec) {
      videoEl.pause();
      videoEl.currentTime = selectedRep.end_sec;
    }
  };

  // RIVEDI REP (RICOMINCIA DA START_SEC)
  const handleReplayRep = () => {
    const videoEl = videoRef.current;
    if (!videoEl || !selectedRep) return;

    const startSec = selectedRep.start_sec != null ? selectedRep.start_sec : 0;
    try {
      videoEl.currentTime = startSec;
      const playPromise = videoEl.play();
      if (playPromise !== undefined) {
        playPromise.catch((e) => console.log("Replay interrotto:", e));
      }
    } catch (e) {
      console.error("Errore replay:", e);
    }
  };

  // CALCOLO STATISTICHE DALLA LISTA REALE (reps_summary.list)
  const totalReps = repsList.length;
  const acceptedReps = repsList.filter(
    (rep) => rep.doctor_validation === 'accepted' || rep.accettata_medico === true
  ).length;
  const rejectedReps = repsList.filter(
    (rep) =>
      rep.doctor_validation === 'rejected' ||
      (rep.accettata_medico === false && rep.doctor_validation !== 'accepted')
  ).length;

  // LOADING STATE
  if (loading) {
    return (
      <div className="pv-doctor-page-bg pv-reps-page">
        <div className="pv-reps-nav-bar">
          <button className="pv-reps-back-btn" onClick={handleBackToDetail}>
            &larr; Torna al dettaglio esercizio
          </button>
        </div>
        <div className="pv-reps-content-container">
          <div className="glass-card" style={{ textAlign: 'center', padding: '40px', width: '100%' }}>
            <p style={{ color: '#4a5a52', fontSize: '1.1rem', margin: 0 }}>
              Caricamento ripetizioni in corso...
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ERROR STATE
  if (error) {
    return (
      <div className="pv-doctor-page-bg pv-reps-page">
        <div className="pv-reps-nav-bar">
          <button className="pv-reps-back-btn" onClick={handleBackToDetail}>
            &larr; Torna al dettaglio esercizio
          </button>
        </div>
        <div className="pv-reps-content-container">
          <div className="glass-card" style={{ textAlign: 'center', padding: '40px', width: '100%' }}>
            <h3 style={{ color: '#d32f2f', marginBottom: '12px' }}>Errore</h3>
            <p style={{ color: '#4a5a52', marginBottom: '20px' }}>{error}</p>
            <button className="pv-reps-back-btn" onClick={handleBackToDetail}>
              Torna al dettaglio
            </button>
          </div>
        </div>
      </div>
    );
  }

  const exerciseName = exerciseData?.nome || exerciseId;

  return (
    <div className="pv-doctor-page-bg pv-reps-page">

      {/* TOP NAVIGATION */}
      <div className="pv-reps-nav-bar">
        <button className="pv-reps-back-btn" onClick={handleBackToDetail}>
          &larr; Torna al dettaglio esercizio
        </button>
      </div>

      {/* CENTRAL CONTENT */}
      <div className="pv-reps-content-container">

        {/* HEADER CARD */}
        <div className="pv-reps-header-card glass-card">
          <span className="pv-reps-pre-title">REP Segmentate</span>
          <h2>{exerciseName}</h2>
        </div>

        {/* METRICS SUMMARY CARD */}
        <div className="pv-reps-summary-card">
          <div className="pv-reps-metrics-grid">
            <div className="pv-reps-metric-item">
              <span className="pv-reps-metric-num">{totalReps}</span>
              <span className="pv-reps-metric-label">REP rilevate</span>
            </div>
            <div className="pv-reps-metric-item accepted">
              <span className="pv-reps-metric-num">{acceptedReps}</span>
              <span className="pv-reps-metric-label">accettate</span>
            </div>
            <div className="pv-reps-metric-item rejected">
              <span className="pv-reps-metric-num">{rejectedReps}</span>
              <span className="pv-reps-metric-label">rifiutate</span>
            </div>
          </div>
        </div>

        {/* SHARED SINGLE VIDEO PLAYER */}
        <div className="pv-reps-player-card glass-card">
          {selectedRep ? (
            <div className="pv-reps-player-wrapper">
              <div className="pv-reps-player-header">
                <div className="pv-reps-player-info">
                  <span className="pv-reps-player-title">
                    Ripetizione {selectedRep.rep_index}
                  </span>
                  <span
                    className={`pv-rep-badge ${
                      selectedRep.doctor_validation === 'accepted' || selectedRep.accettata_medico === true
                        ? 'accepted'
                        : selectedRep.doctor_validation === 'rejected' ||
                          (selectedRep.accettata_medico === false && selectedRep.doctor_validation !== 'accepted')
                        ? 'rejected'
                        : 'pending'
                    }`}
                  >
                    {selectedRep.doctor_validation === 'accepted' || selectedRep.accettata_medico === true
                      ? 'Accettata'
                      : selectedRep.doctor_validation === 'rejected' ||
                        (selectedRep.accettata_medico === false && selectedRep.doctor_validation !== 'accepted')
                      ? 'Rifiutata'
                      : 'In attesa'}
                  </span>
                </div>
                <button
                  type="button"
                  className="pv-btn-replay-rep"
                  onClick={handleReplayRep}
                  title="Riproduci nuovamente questa ripetizione"
                >
                  &#x21bb; Rivedi REP
                </button>
              </div>

              <div className="pv-video-container">
                <video
                  ref={videoRef}
                  src={currentVideoUrl}
                  preload="metadata"
                  controls
                  playsInline
                  onLoadedMetadata={handleLoadedMetadata}
                  onCanPlay={handleLoadedMetadata}
                  onTimeUpdate={handleTimeUpdate}
                  className="pv-shared-video-element"
                />
              </div>
            </div>
          ) : (
            <div className="pv-reps-player-placeholder">
              <div className="pv-placeholder-icon-circle">
                <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
              </div>
              <p className="pv-placeholder-text">Seleziona una ripetizione per visualizzarla</p>
            </div>
          )}
        </div>

        {/* REPS CLINICAL LIST */}
        <div className="pv-reps-list-card">
          <h3 className="pv-reps-list-title">Elenco Ripetizioni Cliniche</h3>

          {repsList.length === 0 ? (
            <div className="pv-reps-empty-state">
              <p>Nessuna ripetizione segmentata trovata per questo esercizio.</p>
            </div>
          ) : (
            <div className="pv-reps-items-stack">
              {repsList.map((rep, idx) => {
                const isAccepted =
                  rep.doctor_validation === 'accepted' || rep.accettata_medico === true;
                const isRejected =
                  rep.doctor_validation === 'rejected' ||
                  (rep.accettata_medico === false && rep.doctor_validation !== 'accepted');

                let statusLabel = 'In attesa';
                let statusClass = 'pending';

                if (isAccepted) {
                  statusLabel = 'Accettata';
                  statusClass = 'accepted';
                } else if (isRejected) {
                  statusLabel = 'Rifiutata';
                  statusClass = 'rejected';
                }

                const isCurrentSelected =
                  selectedRep &&
                  selectedRep.rep_index === rep.rep_index &&
                  selectedRep.video_source === rep.video_source;

                return (
                  <div
                    key={`${rep.video_source || 'rep'}_${rep.rep_index || idx}_${idx}`}
                    className={`pv-rep-row ${isCurrentSelected ? 'pv-rep-row--selected' : ''}`}
                  >
                    <div className="pv-rep-left-group">
                      <span className="pv-rep-name">
                        Ripetizione {rep.rep_index !== undefined && rep.rep_index !== null ? rep.rep_index : idx + 1}
                      </span>
                      <span className={`pv-rep-badge ${statusClass}`}>
                        {statusLabel}
                      </span>
                    </div>

                    <button
                      type="button"
                      className={`pv-btn-view-rep ${isCurrentSelected ? 'active' : ''}`}
                      onClick={() => handleSelectRep(rep)}
                    >
                      Visualizza REP
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
