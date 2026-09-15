import React, { useState, useEffect } from 'react';
import './ExerciseListPage.css';
import { useNavigate } from 'react-router-dom';
import '../Dashboard.css';
import { supabase } from '../SupabaseClient';
import { useColor } from '../context/ColorContext';
import TutorialOverlay from '../components/TutorialOverlay';

const TUTORIAL_ESERCIZI = [
  {
    icon: '🔍',
    title: 'Sfoglia gli esercizi',
    desc: 'Usa il filtro per categoria e clicca su un esercizio per vedere il video tutorial e i dettagli.',
  },
  {
    icon: '➕',
    title: 'Aggiungi alla lista',
    desc: "Nel pop-up che si apre clicca Aggiungi per inserire l'esercizio nella tua lista. Gli esercizi aggiunti mostrano una spunta verde.",
  },
  {
    icon: '▶️',
    title: 'Inizia o salva per dopo',
    desc: 'Clicca sul pulsante "X esercizi scelti" per vedere la lista, avviare l\'allenamento o salvare il piano per dopo.',
  },
];

function ExerciseListPage() {
  const [selectedExerciseDetails, setSelectedExerciseDetails] = useState(null);
  const navigate = useNavigate();
  const { backgroundColor } = useColor();
  const [selectedCategory, setSelectedCategory] = useState('Tutti');
  const [addedExercises, setAddedExercises] = useState([]);
  const [exercises, setExercises] = useState([]);
  const [categories, setCategories] = useState(['Tutti']);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isListSaved, setIsListSaved] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Modals
  const [showExerciseModal, setShowExerciseModal] = useState(false);
  const [showListModal, setShowListModal] = useState(false);
  const [showDescriptionModal, setShowDescriptionModal] = useState(false);

  useEffect(() => { setIsListSaved(false); }, [addedExercises]);

  useEffect(() => {
    const loadExercises = async () => {
      try {
        setLoading(true);
        const { data, error } = await supabase
          .from('esercizi')
          .select('id, exercise_id, nome, descrizione, categoria, video_tutorial_url');
        if (error) throw error;
        if (data) {
          setExercises(data);
          const uniqueCategories = [...new Set(data.map(ex => ex.categoria).filter(Boolean))];
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
    try { localStorage.setItem('selectedExercises', JSON.stringify(list)); }
    catch (e) { console.warn('Impossibile salvare selectedExercises', e); }
  };

  const handleSelectExercise = (exercise) => {
    setSelectedExerciseDetails(exercise);
    setShowExerciseModal(true);
  };

  const handleAddExercise = () => {
    if (!selectedExerciseDetails) return;
    setAddedExercises(prev => {
      if (prev.some(ex => ex.id === selectedExerciseDetails.id)) return prev;
      const next = [...prev, selectedExerciseDetails];
      persistSelectedExercises(next);
      return next;
    });
    setShowExerciseModal(false);
  };

  const handleRemoveExercise = (exerciseId) => {
    setAddedExercises(prev => {
      const next = prev.filter(ex => ex.id !== exerciseId);
      persistSelectedExercises(next);
      return next;
    });
  };

  const handleSalvaPerDopo = async () => {
    if (addedExercises.length === 0 || isListSaved || isSaving) return;
    setIsSaving(true);
    try {
      const pianoId = (crypto.randomUUID?.() ) ??
        'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
          const r = Math.random() * 16 | 0;
          return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
        });
      const { data: { user } } = await supabase.auth.getUser();
      const rows = addedExercises.map(ex => ({
        piano_id: pianoId,
        utente: user.id,
        esercizio: ex.id,
      }));
      const { error } = await supabase.from('allenamenti').insert(rows);
      if (error) throw error;
      setIsListSaved(true);
    } catch (e) {
      console.warn('Impossibile salvare il piano', e);
    } finally {
      setIsSaving(false);
    }
  };

  const filteredExercises = exercises.filter(ex =>
    selectedCategory === 'Tutti' || ex.zona_allenamento === selectedCategory
  );

  const isAdded = (exercise) => addedExercises.some(ex => ex.id === exercise.id);

  return (
    <div className="page-container" style={{ '--colorvar': backgroundColor }}>
      <TutorialOverlay steps={TUTORIAL_ESERCIZI} storageKey="tutorial_visto_esercizi" />
      <div className="glass-card page-card">

        <header className="page-header">
          <h1 style={{ color: backgroundColor }}>Galleria Esercizi</h1>
          {addedExercises.length > 0 && (
            <button
              className="selected-count-btn"
              style={{ backgroundColor: `color-mix(in srgb, ${backgroundColor}, #000000 25%)` }}
              onClick={() => setShowListModal(true)}
            >
              {addedExercises.length} esercizi scelti
            </button>
          )}
        </header>

        {loading ? (
          <div className="loading"><p>Caricamento esercizi...</p></div>
        ) : error ? (
          <div className="error"><p>{error}</p></div>
        ) : (
          <div className="exercise-menu">
            <div className="filter-section">
              <label>Filtra per categoria</label>
              <select value={selectedCategory} onChange={e => setSelectedCategory(e.target.value)}>
                {categories.map(cat => <option key={cat} value={cat}>{cat}</option>)}
              </select>
            </div>

            <ul className="exercise-list">
              {filteredExercises.map(exercise => (
                <li key={exercise.id}>
                  <button
                    className={`exercise-item${isAdded(exercise) ? ' exercise-added' : ''}`}
                    onClick={() => handleSelectExercise(exercise)}
                    style={{ flex: 1 }}
                  >
                    <span>{exercise.nome}</span>
                    {isAdded(exercise) && <span className="ex-added-check">✅</span>}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* ── Modal esercizio + descrizione (overlay condiviso, impilati) ── */}
      {showExerciseModal && selectedExerciseDetails && (
        <div
          className="el-modal-overlay"
          onClick={() => { setShowExerciseModal(false); setShowDescriptionModal(false); }}
        >
          <div className="el-modal-stack" onClick={e => e.stopPropagation()}>

            {/* Descrizione — appare sopra quando aperta */}
            {showDescriptionModal && (
              <div className="el-modal-content el-modal-desc">
                <div className="el-desc-body">
                  <div className="el-modal-header">
                    <h3 style={{ color: backgroundColor }}>Descrizione</h3>
                    <button className="el-modal-close" onClick={() => setShowDescriptionModal(false)}>✕</button>
                  </div>
                  <p>{selectedExerciseDetails.descrizione || 'Nessuna descrizione disponibile.'}</p>
                </div>
              </div>
            )}

            {/* Esercizio — rimane sempre visibile */}
            <div className="el-modal-content">
              <div className="el-modal-header">
                <h2>{selectedExerciseDetails.nome}</h2>
                <button
                  className="el-modal-close"
                  onClick={() => { setShowExerciseModal(false); setShowDescriptionModal(false); }}
                >✕</button>
              </div>

              {selectedExerciseDetails.video_tut_url ? (
                <div className="el-modal-video">
                  <video key={selectedExerciseDetails.video_tut_url} controls autoPlay loop muted>
                    <source src={selectedExerciseDetails.video_tut_url} type="video/mp4" />
                  </video>
                </div>
              ) : (
                <div className="el-modal-no-video"><p>Nessun video disponibile</p></div>
              )}


              <div className="el-modal-actions">
                <button
                  className="add-button"
                  onClick={handleAddExercise}
                  disabled={isAdded(selectedExerciseDetails)}
                  style={{ opacity: isAdded(selectedExerciseDetails) ? 0.6 : 1 }}
                >
                  {isAdded(selectedExerciseDetails) ? 'Aggiunto ✓' : 'Aggiungi'}
                </button>
                <button
                  className="description-button"
                  onClick={() => setShowDescriptionModal(v => !v)}
                >
                  ⓘ
                </button>
              </div>
            </div>

          </div>
        </div>
      )}

      {/* ── Modal lista esercizi scelti ── */}
      {showListModal && (
        <div className="el-modal-overlay" onClick={() => setShowListModal(false)}>
          <div className="el-modal-content" onClick={e => e.stopPropagation()}>
            <div className="el-modal-header">
              <h2>Esercizi scelti</h2>
              <button className="el-modal-close" onClick={() => setShowListModal(false)}>✕</button>
            </div>

            {addedExercises.length === 0 ? (
              <p className="el-modal-empty">Nessun esercizio aggiunto.</p>
            ) : (
              <ul className="el-list-modal-list">
                {addedExercises.map((ex, i) => (
                  <li key={ex.id}>
                    <span className="el-list-num">{i + 1}</span>
                    <span className="el-list-name">{ex.nome}</span>
                    <button
                      className="el-list-remove"
                      onClick={() => handleRemoveExercise(ex.id)}
                      aria-label={`Rimuovi ${ex.nome}`}
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <div className="el-list-modal-actions">
              <button
                onClick={handleSalvaPerDopo}
                disabled={addedExercises.length === 0 || isListSaved || isSaving}
              >
                {isSaving ? 'Salvando...' : isListSaved ? 'Salvato ✓' : 'Salva per dopo'}
              </button>
              <button
                onClick={() => navigate('/allenamento', { state: { allenamentiSelezionati: addedExercises } })}
                disabled={addedExercises.length === 0}
              >
                Avvia allenamento
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

export default ExerciseListPage;
