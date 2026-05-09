import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../SupabaseClient';
import './ChronologyPage.css';
import '../Dashboard.css';

const ITEMS_PER_PAGE = 10;

function ChronologyPage() {
  const navigate = useNavigate();
  const userId = useMemo(() => {
    const cached = localStorage.getItem('user');
    return cached ? JSON.parse(cached)?.id : null;
  }, []);

  const [workouts, setWorkouts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);

  // Carica gli allenamenti da Supabase
  useEffect(() => {
    const loadWorkouts = async () => {
      if (!userId) {
        setError('Utente non autenticato');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const { data, error: fetchError } = await supabase
          .from('allenamenti')
          .select('*, esercizio(nome)')
          .eq('utente', userId)
          .order('created_at', { ascending: false });

        if (fetchError) {
          throw fetchError;
        }

        setWorkouts(data || []);
        console.log('Allenamenti caricati:', data);
        setError(null);
      } catch (err) {
        console.error('Errore nel caricamento degli allenamenti:', err);
        setError('Errore nel caricamento degli allenamenti. Verifica di avere completato almeno un allenamento.');
        setWorkouts([]);
      } finally {
        setLoading(false);
      }
    };

    loadWorkouts();
  }, [userId]);

  // Calcola le statistiche
  const totalWorkouts = workouts.length;
  const totalExercises = workouts.filter(w => w.completato === true).length;

  // Paginazione
  const totalPages = Math.ceil(totalWorkouts / ITEMS_PER_PAGE);
  const startIdx = (currentPage - 1) * ITEMS_PER_PAGE;
  const endIdx = startIdx + ITEMS_PER_PAGE;
  const paginatedWorkouts = workouts.slice(startIdx, endIdx);

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
      window.scrollTo(0, 0);
    }
  };

  const handlePrevPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
      window.scrollTo(0, 0);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('it-IT', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateString;
    }
  };

  const getFeedbackEmoji = (feedback) => {
    switch (feedback?.toLowerCase()) {
      case 'facile':
        return '😊';
      case 'medio':
        return '😐';
      case 'difficile':
        return '😞';
      default:
        return '-';
    }
  };

  return (
    <div className="chronology-container">
      <div className="glass-card chronology-card">
        <header className="chronology-header">
          <h1>Cronologia Allenamenti</h1>
          <button 
            type="button"
            onClick={() => navigate('/visualizza-esercizi')}
            className="goback-button"
          >
            Indietro
          </button>
        </header>

        {loading ? (
          <div className="chronology-loading">
            <p>Caricamento allenamenti...</p>
          </div>
        ) : error ? (
          <div className="chronology-error">
            <p>{error}</p>
          </div>
        ) : totalWorkouts === 0 ? (
          <div className="chronology-empty">
            <p>Nessun allenamento registrato</p>
          </div>
        ) : (
          <>
            {/* Statistiche */}
            <div className="chronology-stats">
              <div className="stat-item">
                <span className="stat-label">Allenamenti Totali</span>
                <span className="stat-value">{totalWorkouts}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Esercizi Completati</span>
                <span className="stat-value">{totalExercises}</span>
              </div>
            </div>

            {/* Lista Allenamenti */}
            <div className="workouts-list">
              {paginatedWorkouts.map((workout, index) => (
                <div key={workout.id || index} className="workout-item">
                  <div className="workout-header">
                    <span className="workout-date">{formatDate(workout.created_at)}</span>
                    <span className="workout-feedback">{getFeedbackEmoji(workout.feedback)}</span>
                  </div>
                  
                  <div className="workout-details">
                    <div className="detail-row">
                      <span className="detail-label">Nome:</span>
                      <span className="detail-value">
                        {workout.esercizio?.nome || '-'}
                      </span>
                    </div>
                    
                    <div className="detail-row">
                      <span className="detail-label">Completato:</span>
                      <span className="detail-value">
                        {workout.completato ? '✓' : 'X'}
                      </span>
                    </div>
                    
                    {workout.feedback && (
                      <div className="detail-row">
                        <span className="detail-label">Feedback:</span>
                        <span className="detail-value feedback-text">
                          {workout.feedback}
                        </span>
                      </div>
                    )}

                    {workout.note && (
                      <div className="detail-row full-width">
                        <span className="detail-label">Note:</span>
                        <p className="detail-note">{workout.note}</p>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Paginazione */}
            {totalPages > 1 && (
              <div className="chronology-pagination">
                <button
                  onClick={handlePrevPage}
                  disabled={currentPage === 1}
                  className="pagination-button"
                >
                  ← Precedente
                </button>
                
                <div className="pagination-info">
                  Pagina {currentPage} di {totalPages}
                </div>
                
                <button
                  onClick={handleNextPage}
                  disabled={currentPage === totalPages}
                  className="pagination-button"
                >
                  Successiva →
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default ChronologyPage;
