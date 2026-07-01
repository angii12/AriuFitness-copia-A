import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useColor } from '../context/ColorContext';
import { supabase } from '../SupabaseClient';
import './ChronologyPage.css';
import '../Dashboard.css';

function EserciziSalvatiPage() {
  const navigate = useNavigate();
  const { backgroundColor } = useColor();
  const [piani, setPiani] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const caricaPiani = async () => {
      try {
        setLoading(true);
        const { data: { user } } = await supabase.auth.getUser();
        const { data, error } = await supabase
          .from('allenamenti')
          .select('piano_id, created_at, esercizi(*)')
          .eq('utente', user.id)
          .order('created_at', { ascending: false });

        if (error) throw error;

        // Raggruppa le righe per piano_id
        const pianiMap = {};
        for (const row of data) {
          if (!pianiMap[row.piano_id]) {
            pianiMap[row.piano_id] = {
              id: row.piano_id,
              salvataIl: row.created_at,
              esercizi: [],
            };
          }
          if (row.esercizi) pianiMap[row.piano_id].esercizi.push(row.esercizi);
        }
        setPiani(Object.values(pianiMap));
        setError(null);
      } catch (e) {
        console.error('Errore caricamento piani:', e);
        setError('Impossibile caricare i piani salvati.');
      } finally {
        setLoading(false);
      }
    };

    caricaPiani();
  }, []);

  const handleAvvia = (piano) => {
    localStorage.setItem('selectedExercises', JSON.stringify(piano.esercizi));
    navigate('/allenamento');
  };

  const handleElimina = async (id) => {
    try {
      const { error } = await supabase
        .from('allenamenti')
        .delete()
        .eq('piano_id', id);
      if (error) throw error;
      setPiani(prev => prev.filter(p => p.id !== id));
    } catch (e) {
      console.error('Errore eliminazione piano:', e);
    }
  };

  const formatDate = (isoString) => {
    try {
      return new Date(isoString).toLocaleDateString('it-IT', {
        year: 'numeric', month: 'long', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="chronology-container" style={{ '--colorvar': backgroundColor }}>
      <div className="glass-card chronology-card">
        <header className="chronology-header">
          <h1 style={{ color: backgroundColor }}>I miei piani</h1>
          <button
            type="button"
            onClick={() => navigate('/visualizza-esercizi')}
            className="goback-button"
            style={{ backgroundColor }}
          >
            + Nuovo piano
          </button>
        </header>

        {loading ? (
          <div className="chronology-empty"><p>Caricamento...</p></div>
        ) : error ? (
          <div className="chronology-empty"><p>{error}</p></div>
        ) : piani.length === 0 ? (
          <div className="chronology-empty">
            <p>
              Nessun piano salvato. Vai nella galleria esercizi, scegli gli esercizi e
              clicca su "Salva per dopo".
            </p>
          </div>
        ) : (
          <div className="workouts-list">
            {piani.map((piano) => (
              <div key={piano.id} className="workout-item">
                <div className="workout-header">
                  <span className="workout-date">{formatDate(piano.salvataIl)}</span>
                  <span className="saved-exercise-count">
                    {piano.esercizi.length} esercizi
                  </span>
                </div>

                <ul className="saved-exercise-list">
                  {piano.esercizi.map((ex, i) => (
                    <li key={ex.id || i}>{ex.nome}</li>
                  ))}
                </ul>

                <div className="saved-plan-actions">
                  <button
                    type="button"
                    className="btn-elimina"
                    onClick={() => handleElimina(piano.id)}
                  >
                    Elimina
                  </button>
                  <button
                    type="button"
                    className="btn-avvia"
                    onClick={() => handleAvvia(piano)}
                  >
                    Avvia
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default EserciziSalvatiPage;
