import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import './ExerciseListPage.css'; // Creeremo questo file per lo stile
import { useNavigate } from 'react-router-dom';
import '../Dashboard.css'; // Per importare lo stile del bottone logout
import { supabase } from '../SupabaseClient';
import { useColor } from '../context/ColorContext';

function ExerciseListPage() {
  const [selectedExercise, setSelectedExercise] = useState(null);
  const [videoUrl, setVideoUrl] = useState('');
  const navigate = useNavigate();
  const { backgroundColor } = useColor();
  const [selectedCategory, setSelectedCategory] = useState('Tutti');
  const [addedExercises, setAddedExercises] = useState([]);
  const [exercises, setExercises] = useState([]);
  const [categories, setCategories] = useState(['Tutti']);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [selectedExerciseDetails, setSelectedExerciseDetails] = useState(null);
  const [showDescriptionModal, setShowDescriptionModal] = useState(false);

  // Carica gli esercizi dal database
  useEffect(() => {
    const loadExercises = async () => {
      try {
        setLoading(true);
        const { data, error } = await supabase
          .from('esercizi')
          .select('id, nome, zona_allenamento, video_tut_url, palla, descrizione');

        if (error) {
          throw error;
        }

        if (data) {
          setExercises(data);
          // Estrai le categorie uniche dai dati
          const uniqueCategories = [...new Set(data.map(ex => ex.zona_allenamento).filter(Boolean))];
          setCategories(['Tutti', ...uniqueCategories.sort()]);
        }
        setError(null);
      } catch (err) {
        console.error('Errore nel caricamento degli esercizi:', err);
        setError('Errore nel caricamento degli esercizi');
      } finally {
        setLoading(false);
      }
    };

    loadExercises();
  }, []);

  const persistSelectedExercises = (list) => {
    try {
      localStorage.setItem('selectedExercises', JSON.stringify(list));
    } catch (e) {
      console.warn('Impossibile salvare selectedExercises in localStorage', e);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/'); // Reindirizza alla pagina di scelta (che poi reindirizzerà al login)
  };

  const handleSelectExercise = (exercise) => {
    setSelectedExercise(exercise.nome);
    setSelectedExerciseDetails(exercise);
    if (exercise.video_tut_url) {
      setVideoUrl(exercise.video_tut_url);
    } else {
      console.warn(`URL video non trovato per l'esercizio: ${exercise.nome}`);
      setVideoUrl('');
    }
  };

  const handleAddExercise = () => {
    if (!selectedExerciseDetails) return;
    setAddedExercises((prev) => {
      // Controlla se l'esercizio è già stato aggiunto (tramite ID)
      if (prev.some((ex) => ex.id === selectedExerciseDetails.id)) return prev;
      const next = [...prev, selectedExerciseDetails];
      persistSelectedExercises(next);
      return next;
    });
  };

  const handleRemoveExercise = (exerciseId) => {
    setAddedExercises((prev) => {
      const next = prev.filter((ex) => ex.id !== exerciseId);
      persistSelectedExercises(next);
      return next;
    });
  };

  // Filtra gli esercizi in base alla categoria selezionata
  const filteredExercises = exercises.filter((exercise) => {
    if (selectedCategory === 'Tutti') return true;
    return exercise.zona_allenamento === selectedCategory;
  });

  return (
    <div className="page-container" style={{ '--colorvar': backgroundColor }}>
      <div className="glass-card page-card">
        <header className="page-header">
          <h1 style={{ color: backgroundColor }}>Galleria Esercizi</h1>
        </header>
        {loading ? (
          <div className='loading'>
            <p>Caricamento esercizi...</p>
          </div>
        ) : error ? (
          <div className='error'>
            <p>{error}</p>
          </div>
        ) : (
          <div className="content-layout">
            <div className="exercise-menu">
              <div className="filter-section">
                <label>
                  Filtra per categoria
                </label>
                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                >
                  {categories.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </select>
              </div>
              <ul className="exercise-list">
                {filteredExercises.map((exercise) => (
                  <li key={exercise.id}>
                    <button
                      className={
                        selectedExercise === exercise.nome
                          ? 'exercise-item active-exercise'
                          : 'exercise-item'
                      }
                      onClick={() => handleSelectExercise(exercise)}
                      style={{ flex: 1 }}
                    >
                      {exercise.nome}
                    </button>
                  </li>
                ))}
              </ul>

            <div className='added-exercises'>
              <h3>Lista esercizi aggiunti</h3>
              {addedExercises.length === 0 ? (
                <p> Nessun esercizio aggiunto. </p>
              ) : (
                <ul>
                  {addedExercises.map((exercise) => (
                    <li key={exercise.id}>
                      <span>{exercise.nome}</span>
                      <button
                        type="button"
                        onClick={() => handleRemoveExercise(exercise.id)}
                        aria-label={`Rimuovi ${exercise.nome}`}
                        title="Rimuovi"
                        >
                        x
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className='start-bttn'>
              <button
                type="button"
                onClick={() =>
                  navigate('/allenamento', { state: { selectedExercises: addedExercises } })
                }
                disabled={addedExercises.length === 0}
                
              >
                Inizia allenamento
              </button>
            </div>
          </div>
          
          <div className="video-player-panel">
            {/* --- CONDIZIONE CORRETTA: usa videoUrl --- */}
            {videoUrl ? (
              <>
                <div className="video-container">
                  <video key={videoUrl} controls autoPlay loop muted>
                    <source src={videoUrl} type="video/mp4" />
                    Il tuo browser non supporta i video.
                  </video>
                </div>
                <div className='exercise-details'>
                  {selectedExerciseDetails?.palla && (
                    <div className='info-ball'>
                      <p className='info-ball-string'>
                        Dimensioni palla da usare:
                      </p>
                      <p className='info-ball-data'>
                        {selectedExerciseDetails.palla + " cm"}
                      </p>
                    </div>
                  )}
                  <div className='add-exercise-section'>
                    <button
                      className='add-button'
                      type="button"
                      onClick={() => handleAddExercise()}
                      disabled={!selectedExercise || addedExercises.some((ex) => ex.id === selectedExerciseDetails?.id)}
                      style={{
                        cursor:
                          !selectedExercise || addedExercises.some((ex) => ex.id === selectedExerciseDetails?.id)
                            ? 'not-allowed'
                            : 'pointer',
                        opacity:
                          !selectedExercise || addedExercises.some((ex) => ex.id === selectedExerciseDetails?.id) ? 0.6 : 1,
                      }}
                    >
                      Aggiungi
                    </button>
                    <button
                    className='description-button'
                      type="button"
                      onClick={() => setShowDescriptionModal(true)}
                      title="Leggi la descrizione dell'esercizio"
                    >
                      ⓘ
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <div className="video-placeholder">
                <p>Seleziona un esercizio dalla lista per vedere il tutorial.</p>
              </div>
            )}
          </div>
        </div>        )}
        
        {/* Modal per la descrizione dell'esercizio */}
        {showDescriptionModal && selectedExerciseDetails && (
          <div
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: 'rgba(0, 0, 0, 0.5)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 100,
              padding: 16,
            }}
            onClick={() => setShowDescriptionModal(false)}
          >
            <div
              style={{
                background: 'white',
                borderRadius: 12,
                padding: 24,
                maxWidth: 500,
                width: '100%',
                maxHeight: '80vh',
                overflowY: 'auto',
                boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <h2 style={{ margin: 0, color: '#333' }}>
                  {selectedExerciseDetails.nome}
                </h2>
                <button
                  type="button"
                  onClick={() => setShowDescriptionModal(false)}
                  style={{
                    background: 'none',
                    border: 'none',
                    fontSize: 24,
                    cursor: 'pointer',
                    color: '#999',
                  }}
                >
                  ✕
                </button>
              </div>
              
              <div style={{ marginBottom: 16 }}>
                <h3 style={{ margin: '0 0 8px 0', color: backgroundColor, fontSize: 14 }}>
                  Descrizione
                </h3>
                <p style={{ margin: 0, color: '#555', lineHeight: 1.6 }}>
                  {selectedExerciseDetails.descrizione || 'Nessuna descrizione disponibile.'}
                </p>
              </div>
              
              {selectedExerciseDetails.palla && (
                <div style={{ marginBottom: 16, padding: 12, background: '#f5f5f5', borderRadius: 8 }}>
                  <h3 style={{ margin: '0 0 8px 0', color: backgroundColor, fontSize: 14 }}>
                    Attrezzo utilizzato
                  </h3>
                  <p style={{ margin: 0, color: '#555', fontWeight: 500 }}>
                    {selectedExerciseDetails.palla}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ExerciseListPage;