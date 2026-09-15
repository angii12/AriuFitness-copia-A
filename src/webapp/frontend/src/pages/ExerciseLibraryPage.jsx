import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { supabase } from '../SupabaseClient';
import '../index.css';
import './ExerciseLibraryPage.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function ExerciseLibraryPage() {
  const { exerciseId: urlExerciseId } = useParams();
  const navigate = useNavigate();

  // LIST STATE
  const [exercises, setExercises] = useState([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  // DETAIL STATE
  const [selectedExerciseId, setSelectedExerciseId] = useState(null);
  const [details, setDetails] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState(null);

  // VIDEO SELECTION (does NOT mutate details.videos)
  const [selectedVideoIndex, setSelectedVideoIndex] = useState(0);

  // ACTIVE EXERCISE ID (supports URL param or fallback state)
  const activeExerciseId = urlExerciseId || selectedExerciseId;

  // AUTH
  const getAuthHeaders = async () => {
    const { data: { session }, error } = await supabase.auth.getSession();
    if (error || !session?.access_token) {
      throw new Error('Sessione non valida o scaduta. Effettua nuovamente il login.');
    }
    return { Authorization: `Bearer ${session.access_token}` };
  };

  // FETCH EXERCISE LIST (only if not viewing a specific exercise detail)
  useEffect(() => {
    if (!activeExerciseId) {
      const fetchExercises = async () => {
        try {
          setLoading(true);
          setListError(null);
          const headers = await getAuthHeaders();
          const res = await axios.get(`${API_BASE_URL}/api/doctor/exercises`, { headers });
          setExercises(res.data.exercises || []);
        } catch (err) {
          console.error(err);
          setListError('Errore nel caricamento degli esercizi.');
        } finally {
          setLoading(false);
        }
      };
      fetchExercises();
    }
  }, [activeExerciseId]);

  // FETCH EXERCISE DETAILS (supports direct URL access, refresh and navigation)
  useEffect(() => {
    if (activeExerciseId) {
      const fetchDetails = async () => {
        try {
          setDetailsLoading(true);
          setDetailsError(null);
          setSelectedVideoIndex(0);
          const headers = await getAuthHeaders();
          const res = await axios.get(
            `${API_BASE_URL}/api/doctor/exercises/${activeExerciseId}/details`,
            { headers }
          );
          setDetails(res.data);
        } catch (err) {
          console.error(err);
          setDetailsError("Impossibile caricare i dettagli dell'esercizio.");
        } finally {
          setDetailsLoading(false);
        }
      };
      fetchDetails();
    } else {
      setDetails(null);
    }
  }, [activeExerciseId]);

  // OPEN DETAIL
  const handleViewDetails = (exerciseId) => {
    setSelectedExerciseId(exerciseId);
    navigate(`/medico/esercizi/${exerciseId}`);
  };

  // BACK TO LIST
  const handleBackToList = () => {
    setSelectedExerciseId(null);
    setDetails(null);
    setDetailsError(null);
    setSelectedVideoIndex(0);
    navigate('/medico/esercizi');
  };

  // DETAIL VIEW
  if (activeExerciseId) {
    if (detailsLoading) {
      return (
        <div className="exercise-library-page pv-detail-page">
          <div className="pv-detail-nav-bar">
            <button className="pv-detail-back-btn" onClick={handleBackToList}>
              &larr; Torna alla libreria
            </button>
          </div>
          <div className="loading-container" style={{ textAlign: 'center', padding: '60px 20px' }}>
            <p style={{ color: '#4a5a52', fontSize: '1.1rem' }}>Caricamento dettagli in corso...</p>
          </div>
        </div>
      );
    }

    if (detailsError) {
      return (
        <div className="exercise-library-page pv-detail-page">
          <div className="pv-detail-nav-bar">
            <button className="pv-detail-back-btn" onClick={handleBackToList}>
              &larr; Torna alla libreria
            </button>
          </div>
          <div className="doctor-page-container">
            <div className="doctor-header-card glass-card">
              <h2>Errore</h2>
            </div>
            <div className="doctor-card glass-card mt-3">
              <p>{detailsError}</p>
            </div>
          </div>
        </div>
      );
    }

    if (!details) {
      return (
        <div className="exercise-library-page pv-detail-page">
          <div className="pv-detail-nav-bar">
            <button className="pv-detail-back-btn" onClick={handleBackToList}>
              &larr; Torna alla libreria
            </button>
          </div>
          <div className="doctor-page-container">
            <div className="doctor-header-card glass-card">
              <h2>Dettagli non disponibili</h2>
            </div>
          </div>
        </div>
      );
    }

    const ex = details?.exercise || {};
    const profile = details?.profile || null;
    const videos = details?.videos || [];
    const model = details?.model || null;

    // Protezione robusta su reps_summary e sulla sua lista interna
    const repsSummary = details?.reps_summary || { total: 0, accepted: 0, rejected: 0 };
    const repsList = details?.reps_summary?.list || [];
    const currentVideo = videos.length > 0 ? videos[selectedVideoIndex] : null;

    return (
      <div className="exercise-library-page pv-detail-page">

        {/* TOP NAV BAR - ALLINEATO IN ALTO A SINISTRA SOTTO L'HEADER */}
        <div className="pv-detail-nav-bar">
          <button className="pv-detail-back-btn" onClick={handleBackToList}>
            &larr; Torna alla libreria
          </button>
        </div>

        {/* CONTAINER CENTRALE ORIGINALE DELLE CARD */}
        <div className="doctor-page-container">

          {/* HEADER CARD ORIGINALE */}
          <div className="doctor-header-card glass-card">
            <h2>{ex.nome || selectedExerciseId}</h2>
          </div>

        {/* DATI BASE */}
        <div className="doctor-card glass-card mt-3">
          <h3>Dati Base</h3>
          <div className="detail-grid">
            <div className="detail-row">
              <span className="detail-label">ID</span>
              <span className="detail-value">{ex.exercise_id}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Descrizione</span>
              <span className="detail-value">{ex.descrizione || '\u2014'}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Creato il</span>
              <span className="detail-value">
                {ex.created_at ? new Date(ex.created_at).toLocaleString('it-IT') : '\u2014'}
              </span>
            </div>
          </div>
        </div>

        {/* CONFIGURAZIONE */}
        <div className="doctor-card glass-card mt-3">
          <h3>Configurazione (Profilo)</h3>
          {profile ? (
            <div className="detail-grid">
              <div className="detail-row">
                <span className="detail-label">Modalit&agrave; segnale</span>
                <span className="detail-value">{profile.signal_selection_mode || '\u2014'}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Articolazioni selezionate</span>
                <span className="detail-value">
                  {profile.doctor_selected_joints?.length
                    ? profile.doctor_selected_joints.join(', ')
                    : 'Nessuna'}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Rep mode</span>
                <span className="detail-value">{profile.rep_mode || '\u2014'}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Reps attese</span>
                <span className="detail-value">{profile.expected_reps ?? 'Auto'}</span>
              </div>
            </div>
          ) : (
            <p className="text-muted">Nessun profilo configurato.</p>
          )}
        </div>

        {/* VIDEO ORIGINALE */}
        <div className="doctor-card glass-card mt-3">
          <h3>Video Originale{videos.length > 0 ? ` (${videos.length})` : ''}</h3>
          {videos.length > 0 ? (
            <>
              {videos.length > 1 && (
                <select
                  className="form-select mb-3"
                  value={selectedVideoIndex}
                  onChange={(e) => setSelectedVideoIndex(parseInt(e.target.value, 10))}
                  style={{ maxWidth: '420px', marginBottom: '12px' }}
                >
                  {videos.map((v, idx) => (
                    <option key={v.filename} value={idx}>
                      {v.filename}
                    </option>
                  ))}
                </select>
              )}
              <video
                key={currentVideo?.url}
                src={currentVideo?.url}
                controls
                preload="none"
                style={{ width: '100%', maxHeight: '480px', borderRadius: '8px', backgroundColor: '#000' }}
              />
              <p className="text-muted mt-2" style={{ fontSize: '0.85em' }}>{currentVideo?.filename}</p>
            </>
          ) : (
            <p className="text-muted">Nessun video disponibile per questo esercizio.</p>
          )}
        </div>

        {/* REP ACTION & SUMMARY */}
        <div className="pv-reps-toggle-section">
          <button
            className="pv-btn-reps-toggle"
            onClick={() => navigate(`/medico/esercizi/${ex.exercise_id || activeExerciseId}/reps`)}
          >
            Visualizza REP segmentate
          </button>
          <p className="pv-reps-summary-text">
            {repsSummary.total} totali &middot; {repsSummary.accepted} accettate &middot; {repsSummary.rejected} rifiutate
          </p>
        </div>

        {/* MODELLO */}
        {model && (
          <div className="doctor-card glass-card pv-model-card">
            <h3>Modello Addestrato</h3>
            <div className="detail-grid">
              <div className="detail-row">
                <span className="detail-label">Status</span>
                <span className={`detail-value status-badge ${model.status}`}>{model.status}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Versione</span>
                <span className="detail-value">v{model.version}</span>
              </div>
              {model.metrics?.loss != null && (
                <div className="detail-row">
                  <span className="detail-label">Loss</span>
                  <span className="detail-value">{model.metrics.loss.toFixed(4)}</span>
                </div>
              )}
              {model.metrics?.val_loss != null && (
                <div className="detail-row">
                  <span className="detail-label">Val Loss</span>
                  <span className="detail-value">{model.metrics.val_loss.toFixed(4)}</span>
                </div>
              )}
              {model.metrics?.val_accuracy != null && (
                <div className="detail-row">
                  <span className="detail-label">Val Accuracy</span>
                  <span className="detail-value">
                    {(model.metrics.val_accuracy * 100).toFixed(1)}%
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        </div>
      </div>
    );
  }

  // GLOBAL LOADING / ERROR (list)
  if (loading) {
    return (
      <div className="loading-container">
        <h2>Caricamento libreria...</h2>
      </div>
    );
  }

  if (listError) {
    return (
      <div className="error-container">
        <h2>{listError}</h2>
      </div>
    );
  }

  // FILTER EXERCISES (frontend only)
  const filteredExercises = exercises.filter((ex) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase().trim();
    const nameMatch = (ex.nome || '').toLowerCase().includes(term);
    const idMatch = (ex.exercise_id || '').toLowerCase().includes(term);
    return nameMatch || idMatch;
  });

  // GRID VIEW
  return (
    <div className="exercise-library-page doctor-page-container" style={{ maxWidth: '1200px', margin: '0 auto', width: '100%', padding: '40px 24px', boxSizing: 'border-box' }}>

      <div className="pv-doctor-header" style={{ textAlign: 'center', marginBottom: '32px' }}>
        <h1 className="pv-doctor-title" style={{ fontFamily: "'Playfair Display', serif", fontSize: 'clamp(2.5rem, 5vw, 3.5rem)', color: '#4d7c5f', margin: '0 0 12px 0', fontWeight: '700' }}>
          Libreria Esercizi
        </h1>
        <p className="pv-doctor-subtitle" style={{ fontSize: '1.15rem', color: '#4a5a52', margin: '0 auto', maxWidth: '600px' }}>
          Visualizza e gestisci gli esercizi clinici che hai creato.
        </p>
      </div>

      {/* SEARCH BAR */}
      <div className="pv-search-container">
        <div className="pv-search-input-wrapper">
          <svg className="pv-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input
            type="text"
            className="pv-search-input"
            placeholder="Cerca esercizio..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          {searchTerm && (
            <button
              type="button"
              className="pv-search-clear-btn"
              onClick={() => setSearchTerm('')}
              aria-label="Cancella ricerca"
            >
              &times;
            </button>
          )}
        </div>
      </div>

      {exercises.length === 0 ? (
        <div className="doctor-card glass-card empty-state mt-3" style={{ textAlign: 'center', padding: '40px' }}>
          <p>Non hai ancora creato nessun esercizio.</p>
        </div>
      ) : filteredExercises.length === 0 ? (
        <div className="pv-search-empty-state">
          <p>Nessun esercizio trovato.</p>
        </div>
      ) : (
        <div className="pv-exercises-grid">
          {filteredExercises.map((ex) => (
            <div key={ex.id} className="pv-exercise-card glass-card">

              <div className="pv-ex-header text-center">
                <h3 className="pv-ex-title">{ex.nome}</h3>
                <p className="pv-ex-id">ID: {ex.exercise_id}</p>
              </div>

              <div className="pv-ex-stats-mini-grid">
                <div className="pv-stat-item">
                  <span className="pv-stat-label">Video</span>
                  <strong className="pv-stat-value">{ex.video_count}</strong>
                </div>
                <div className="pv-stat-item">
                  <span className="pv-stat-label">REP Totali</span>
                  <strong className="pv-stat-value">{ex.reps_total}</strong>
                </div>
                <div className="pv-stat-item success">
                  <span className="pv-stat-label">Accettate</span>
                  <strong className="pv-stat-value">{ex.reps_accepted}</strong>
                </div>
                <div className="pv-stat-item danger">
                  <span className="pv-stat-label">Rifiutate</span>
                  <strong className="pv-stat-value">{ex.reps_rejected}</strong>
                </div>
              </div>

              <div className="pv-ex-model-status">
                <span className="pv-model-label">Modello:</span>
                {ex.model_status === 'active' ? (
                  <span className="pv-model-badge active">Attivo (v{ex.model_version})</span>
                ) : (
                  <span className="pv-model-badge warning">Non addestrato</span>
                )}
              </div>

              <div className="pv-ex-footer">
                <button
                  className="pv-btn-details"
                  onClick={() => handleViewDetails(ex.exercise_id)}
                >
                  Apri Dettagli
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
