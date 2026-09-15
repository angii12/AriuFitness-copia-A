import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { supabase } from '../SupabaseClient';
import { useAuth } from '../context/AuthContext';
import './DoctorPatientDetailPage.css';

// ─── Helper: iniziali ─────────────────────────────────────────────────────────
function getInitials(nome, cognome) {
  const n = (nome || '').trim();
  const c = (cognome || '').trim();
  if (n && c) return `${n[0]}${c[0]}`.toUpperCase();
  if (n) return n[0].toUpperCase();
  if (c) return c[0].toUpperCase();
  return '?';
}

// ─── Helper: data e ora formattata ───────────────────────────────────────────
function formatSessionDateTime(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleString('it-IT', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

export default function DoctorPatientDetailPage() {
  const { patientId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();

  // STATI PRINCIPALI
  const [patient, setPatient] = useState(null);
  const [connection, setConnection] = useState(null);
  const [assignments, setAssignments] = useState([]);
  const [sessionsByAssignment, setSessionsByAssignment] = useState({});
  const [expandedHistory, setExpandedHistory] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');

  // STATI MODALE ASSEGNAZIONE
  const [isAssignModalOpen, setIsAssignModalOpen] = useState(false);
  const [availableExercises, setAvailableExercises] = useState([]);
  const [loadingAvailable, setLoadingAvailable] = useState(false);
  const [searchExercise, setSearchExercise] = useState('');
  const [selectedExercise, setSelectedExercise] = useState(null);
  const [targetReps, setTargetReps] = useState(5);
  const [notes, setNotes] = useState('');
  const [assignSubmitting, setAssignSubmitting] = useState(false);
  const [assignError, setAssignError] = useState('');

  // ── 1. Caricamento Dati Paziente & Assegnazioni ──────────────────────────────
  const loadData = useCallback(async () => {
    if (!user || !patientId) return;
    try {
      setLoading(true);
      setError('');

      // A. Verifica che esista la relazione active
      const { data: dp, error: dpErr } = await supabase
        .from('doctor_patients')
        .select('id, doctor_id, patient_id, status, created_at')
        .eq('doctor_id', user.id)
        .eq('patient_id', patientId)
        .eq('status', 'active')
        .maybeSingle();

      if (dpErr) throw dpErr;

      if (!dp) {
        setError('Paziente non trovato o collegamento non attivo.');
        setLoading(false);
        return;
      }
      setConnection(dp);

      // B. Recupera il profilo anagrafico del paziente
      const { data: profile, error: profErr } = await supabase
        .from('profili')
        .select('id, nome, cognome')
        .eq('id', patientId)
        .maybeSingle();

      if (profErr) throw profErr;
      setPatient(profile || { nome: 'Paziente', cognome: '' });

      // C. Recupera gli esercizi assegnati
      const { data: assList, error: assErr } = await supabase
        .from('assigned_exercises')
        .select(`
          id, target_reps, notes, assigned_at, exercise_id, model_id,
          esercizi:exercise_id ( nome, categoria, descrizione ),
          exercise_models:model_id ( version, status )
        `)
        .eq('doctor_id', user.id)
        .eq('patient_id', patientId)
        .order('assigned_at', { ascending: false });

      if (assErr) throw assErr;
      setAssignments(assList || []);

      // D. Recupera le sessioni registrate per questo paziente
      const { data: sessList, error: sessErr } = await supabase
        .from('rehab_sessions')
        .select('id, assignment_id, reps_completed, target_reps, status, completed_at, created_at')
        .eq('doctor_id', user.id)
        .eq('patient_id', patientId)
        .order('completed_at', { ascending: false });

      if (sessErr) {
        console.warn('Errore lettura sessioni:', sessErr);
      }

      const groupedSessions = {};
      (sessList || []).forEach(s => {
        if (!groupedSessions[s.assignment_id]) {
          groupedSessions[s.assignment_id] = [];
        }
        groupedSessions[s.assignment_id].push(s);
      });
      setSessionsByAssignment(groupedSessions);

    } catch (err) {
      console.error('Errore caricamento dettaglio paziente:', err);
      setError('Errore durante il caricamento dei dati del paziente.');
    } finally {
      setLoading(false);
    }
  }, [user, patientId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // ── 2. Caricamento Esercizi Prescrivibili (con modello active) ───────────────
  const loadAvailableExercises = async () => {
    try {
      setLoadingAvailable(true);
      setAssignError('');

      // Query con INNER JOIN su esercizi per garantire solo esercizi del medico con modello active
      const { data, error: modelsErr } = await supabase
        .from('exercise_models')
        .select(`
          id,
          version,
          status,
          exercise_id,
          esercizi!inner (
            id,
            exercise_id,
            nome,
            categoria,
            descrizione
          )
        `)
        .eq('status', 'active')
        .order('version', { ascending: false });

      if (modelsErr) throw modelsErr;

      // Deduplica per exercise_id mantenendo la versione più recente (la prima incontrata grazie all'order version DESC)
      const uniqueMap = new Map();
      (data || []).forEach(row => {
        const exId = row.exercise_id;
        if (!uniqueMap.has(exId) && row.esercizi) {
          uniqueMap.set(exId, {
            exercise_id: exId,
            nome: row.esercizi.nome || exId,
            categoria: row.esercizi.categoria || '',
            descrizione: row.esercizi.descrizione || '',
            latestModelId: row.id,
            latestVersion: row.version
          });
        }
      });

      setAvailableExercises(Array.from(uniqueMap.values()));
    } catch (err) {
      console.error('Errore caricamento esercizi prescrivibili:', err);
      setAssignError('Impossibile caricare la lista degli esercizi prescrivibili.');
    } finally {
      setLoadingAvailable(false);
    }
  };

  const handleOpenAssignModal = () => {
    setSelectedExercise(null);
    setTargetReps(5);
    setNotes('');
    setSearchExercise('');
    setAssignError('');
    setIsAssignModalOpen(true);
    loadAvailableExercises();
  };

  const handleCloseAssignModal = () => {
    setIsAssignModalOpen(false);
    setSelectedExercise(null);
  };

  // ── 3. Assegnazione Esercizio ────────────────────────────────────────────────
  const handleConfirmAssignment = async () => {
    if (!selectedExercise) {
      setAssignError('Seleziona un esercizio prima di confermare.');
      return;
    }
    const reps = parseInt(targetReps, 10);
    if (isNaN(reps) || reps < 1 || reps > 100) {
      setAssignError('Inserisci un numero di ripetizioni valido compreso tra 1 e 100.');
      return;
    }

    try {
      setAssignSubmitting(true);
      setAssignError('');

      const { error: insertErr } = await supabase
        .from('assigned_exercises')
        .insert({
          doctor_id: user.id,
          patient_id: patientId,
          exercise_id: selectedExercise.exercise_id,
          model_id: selectedExercise.latestModelId,
          target_reps: reps,
          notes: notes.trim() || null
        });

      if (insertErr) throw insertErr;

      // Aggiorna lista e chiudi modale
      await loadData();
      handleCloseAssignModal();

      setFeedback(`Esercizio "${selectedExercise.nome}" assegnato con successo!`);
      setTimeout(() => setFeedback(''), 4000);

    } catch (err) {
      console.error('Errore assegnazione esercizio:', err);
      setAssignError(err.message || 'Errore durante il salvataggio dell\'assegnazione.');
    } finally {
      setAssignSubmitting(false);
    }
  };

  // ── 4. Revoca Assegnazione ──────────────────────────────────────────────────
  const handleRevokeAssignment = async (assignmentId, exerciseName) => {
    const ok = window.confirm(`Sei sicuro di voler revocare l'assegnazione dell'esercizio "${exerciseName}"?`);
    if (!ok) return;

    try {
      const { error: delErr } = await supabase
        .from('assigned_exercises')
        .delete()
        .eq('id', assignmentId)
        .eq('doctor_id', user.id);

      if (delErr) throw delErr;

      // Rimuovi localmente per reattività istantanea
      setAssignments(prev => prev.filter(a => a.id !== assignmentId));
      setFeedback(`Assegnazione "${exerciseName}" revocata con successo.`);
      setTimeout(() => setFeedback(''), 3500);

    } catch (err) {
      console.error('Errore revoca:', err);
      alert('Errore durante la revoca dell\'assegnazione.');
    }
  };

  const toggleHistory = (assignmentId) => {
    setExpandedHistory(prev => ({
      ...prev,
      [assignmentId]: !prev[assignmentId]
    }));
  };

  // Filtro frontend di ricerca esercizi prescrivibili
  const filteredAvailable = availableExercises.filter(ex => {
    if (!searchExercise.trim()) return true;
    const q = searchExercise.trim().toLowerCase();
    return (
      (ex.nome || '').toLowerCase().includes(q) ||
      (ex.categoria || '').toLowerCase().includes(q) ||
      (ex.descrizione || '').toLowerCase().includes(q)
    );
  });

  // ── RENDER ──────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="pv-detail-page">
        <div className="pv-detail-loading">Caricamento scheda paziente…</div>
      </div>
    );
  }

  if (error || !connection) {
    return (
      <div className="pv-detail-page">
        <div className="pv-detail-error-card">
          <div className="pv-detail-error-icon">⚠️</div>
          <h2>Accesso non consentito</h2>
          <p>{error || 'Paziente non trovato o collegamento non attivo.'}</p>
          <button className="pv-detail-btn-back" onClick={() => navigate('/medico/pazienti')}>
            ← Torna ai pazienti
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="pv-detail-page">
      <div className="pv-detail-content">

        {/* ── Link di Ritorno ───────────────────────────────────────────────── */}
        <div className="pv-detail-nav-back">
          <button className="pv-detail-back-link" onClick={() => navigate('/medico/pazienti')}>
            ← Torna ai pazienti
          </button>
        </div>

        {/* ── Toast Feedback ────────────────────────────────────────────────── */}
        {feedback && (
          <div className="pv-detail-feedback-toast">
            ✓ {feedback}
          </div>
        )}

        {/* ── Header Scheda Paziente ────────────────────────────────────────── */}
        <div className="pv-detail-header-card">
          <div className="pv-detail-avatar">
            {getInitials(patient?.nome, patient?.cognome)}
          </div>
          <div className="pv-detail-patient-info">
            <div className="pv-detail-badge-row">
              <span className="pv-badge-status-active">Paziente collegato</span>
              {connection.created_at && (
                <span className="pv-badge-date">
                  Dal {new Date(connection.created_at).toLocaleDateString('it-IT')}
                </span>
              )}
            </div>
            <h1 className="pv-detail-name">
              {patient?.nome} {patient?.cognome}
            </h1>
            <p className="pv-detail-subtitle">
              Scheda clinica e gestione del piano riabilitativo
            </p>
          </div>

          <div className="pv-detail-header-action">
            <button className="pv-detail-btn-primary" onClick={handleOpenAssignModal}>
              + Assegna esercizio
            </button>
          </div>
        </div>

        {/* ── Sezione Esercizi Assegnati ─────────────────────────────────────── */}
        <div className="pv-detail-section-card">
          <div className="pv-detail-section-header">
            <div>
              <h2>Esercizi assegnati</h2>
              <p>Piano di riabilitazione attivo prescritto per questo paziente</p>
            </div>
            <span className="pv-detail-counter-badge">
              {assignments.length} {assignments.length === 1 ? 'esercizio' : 'esercizi'}
            </span>
          </div>

          {assignments.length === 0 ? (
            <div className="pv-detail-empty">
              <div className="pv-detail-empty-icon">📋</div>
              <h3>Nessun esercizio assegnato</h3>
              <p>Questo paziente non ha ancora esercizi nel proprio piano riabilitativo.</p>
              <button className="pv-detail-btn-primary" onClick={handleOpenAssignModal}>
                + Assegna il primo esercizio
              </button>
            </div>
          ) : (
            <div className="pv-detail-assignments-list">
              {assignments.map(ass => {
                const exName = ass.esercizi?.nome || ass.exercise_id;
                const exCat = ass.esercizi?.categoria;
                const modelVer = ass.exercise_models?.version;

                const assSessions = sessionsByAssignment[ass.id] || [];
                const totalSessions = assSessions.length;
                const latestSession = assSessions[0] || null;
                const isHistoryOpen = Boolean(expandedHistory[ass.id]);

                return (
                  <div key={ass.id} className="pv-assignment-row">
                    <div className="pv-assignment-info">
                      <div className="pv-assignment-title-row">
                        <strong className="pv-assignment-name">{exName}</strong>
                        {exCat && <span className="pv-badge-cat">{exCat}</span>}
                        {modelVer !== undefined && (
                          <span className="pv-badge-model">Modello attivo v{modelVer}</span>
                        )}
                      </div>

                      {ass.esercizi?.descrizione && (
                        <p className="pv-assignment-desc">{ass.esercizi.descrizione}</p>
                      )}

                      {ass.notes && (
                        <div className="pv-assignment-note-box">
                          <span className="pv-note-label">Note per il paziente:</span>
                          <p className="pv-note-text">{ass.notes}</p>
                        </div>
                      )}

                      <div className="pv-assignment-meta-row">
                        <span className="pv-meta-date">
                          Prescritto il {new Date(ass.assigned_at).toLocaleDateString('it-IT')}
                        </span>
                      </div>

                      {/* ── Fascia Ultima Attività ── */}
                      <div className="pv-assignment-activity-section">
                        <div className="pv-activity-bar">
                          <span className="pv-activity-label">Ultima attività</span>

                          {latestSession ? (
                            <div className="pv-activity-details">
                              <span className={`pv-activity-badge pv-activity-badge--${latestSession.status}`}>
                                {latestSession.status === 'completed' ? 'COMPLETATA' : 'INTERROTTA'}
                              </span>
                              <span className="pv-activity-dot">·</span>
                              <span className="pv-activity-reps">
                                {latestSession.reps_completed}/{latestSession.target_reps || ass.target_reps} REP
                              </span>
                              <span className="pv-activity-dot">·</span>
                              <span className="pv-activity-date">
                                {formatSessionDateTime(latestSession.completed_at || latestSession.created_at)}
                              </span>
                            </div>
                          ) : (
                            <div className="pv-activity-details">
                              <span className="pv-activity-badge pv-activity-badge--never">
                                MAI ESEGUITO
                              </span>
                            </div>
                          )}

                          <div className="pv-activity-meta-right">
                            <span className="pv-activity-counter">
                              {totalSessions === 0 
                                ? '0 sessioni' 
                                : totalSessions === 1 
                                  ? '1 sessione totale' 
                                  : `${totalSessions} sessioni totali`}
                            </span>
                            {totalSessions > 0 && (
                              <button 
                                type="button" 
                                className="pv-btn-history-toggle"
                                onClick={() => toggleHistory(ass.id)}
                              >
                                {isHistoryOpen ? 'Nascondi storico' : 'Vedi storico'}
                              </button>
                            )}
                          </div>
                        </div>

                        {/* Storico Espandibile */}
                        {isHistoryOpen && totalSessions > 0 && (
                          <div className="pv-assignment-history-drawer">
                            <div className="pv-history-list">
                              {assSessions.map((s, idx) => (
                                <div key={s.id || idx} className="pv-history-row">
                                  <span className="pv-history-date">
                                    {formatSessionDateTime(s.completed_at || s.created_at)}
                                  </span>
                                  <span className={`pv-history-badge pv-history-badge--${s.status}`}>
                                    {s.status === 'completed' ? 'COMPLETATA' : 'INTERROTTA'}
                                  </span>
                                  <span className="pv-history-reps">
                                    {s.reps_completed}/{s.target_reps || ass.target_reps} REP
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Blocco Target Reps & Azione */}
                    <div className="pv-assignment-action-col">
                      <div className="pv-reps-display">
                        <span className="pv-reps-num">{ass.target_reps}</span>
                        <span className="pv-reps-lbl">ripetizioni</span>
                      </div>

                      <button
                        className="pv-btn-revoke"
                        title="Revoca assegnazione"
                        onClick={() => handleRevokeAssignment(ass.id, exName)}
                      >
                        ✕ Revoca
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

      </div>

      {/* ── MODALE ASSEGNAZIONE ESERCIZIO ───────────────────────────────────── */}
      {isAssignModalOpen && (
        <div className="pv-modal-overlay" onClick={handleCloseAssignModal}>
          <div className="pv-modal-card" onClick={e => e.stopPropagation()}>

            <div className="pv-modal-header">
              <div>
                <h3>Assegna nuovo esercizio</h3>
                <p>Seleziona un esercizio dalla tua Libreria con modello attivo</p>
              </div>
              <button className="pv-modal-close" onClick={handleCloseAssignModal}>✕</button>
            </div>

            {assignError && (
              <div className="pv-modal-error">
                {assignError}
              </div>
            )}

            {/* SELEZIONE ESERCIZIO */}
            {!selectedExercise ? (
              <div className="pv-modal-step-selection">
                <div className="pv-modal-search-box">
                  <input
                    type="text"
                    placeholder="Cerca esercizio nella libreria..."
                    value={searchExercise}
                    onChange={e => setSearchExercise(e.target.value)}
                    autoFocus
                  />
                </div>

                {loadingAvailable ? (
                  <div className="pv-modal-loading">Caricamento esercizi prescrivibili…</div>
                ) : filteredAvailable.length === 0 ? (
                  <div className="pv-modal-empty-search">
                    {availableExercises.length === 0 ? (
                      <p>Nessun esercizio con modello attivo disponibile nella tua libreria.</p>
                    ) : (
                      <p>Nessun esercizio corrispondente a "{searchExercise}".</p>
                    )}
                  </div>
                ) : (
                  <div className="pv-modal-exercise-list">
                    {filteredAvailable.map(ex => (
                      <div key={ex.exercise_id} className="pv-modal-exercise-item">
                        <div className="pv-modal-ex-info">
                          <div className="pv-modal-ex-top">
                            <strong>{ex.nome}</strong>
                            {ex.categoria && <span className="pv-badge-cat">{ex.categoria}</span>}
                            <span className="pv-badge-model">Modello attivo v{ex.latestVersion}</span>
                          </div>
                          {ex.descrizione && (
                            <p className="pv-modal-ex-desc">{ex.descrizione}</p>
                          )}
                        </div>
                        <button
                          className="pv-modal-btn-select"
                          onClick={() => {
                            setSelectedExercise(ex);
                            setAssignError('');
                          }}
                        >
                          Seleziona →
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              /* CONFIGURAZIONE ASSEGNAZIONE */
              <div className="pv-modal-step-config">
                <div className="pv-selected-ex-card">
                  <div className="pv-selected-ex-header">
                    <div>
                      <span className="pv-selected-lbl">Esercizio selezionato</span>
                      <strong className="pv-selected-name">{selectedExercise.nome}</strong>
                      <span className="pv-badge-model">Modello attivo v{selectedExercise.latestVersion}</span>
                    </div>
                    <button
                      className="pv-btn-change-ex"
                      onClick={() => setSelectedExercise(null)}
                    >
                      Cambia
                    </button>
                  </div>
                </div>

                <div className="pv-modal-form-group">
                  <label>Ripetizioni Target *</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={targetReps}
                    onChange={e => setTargetReps(parseInt(e.target.value, 10) || 1)}
                  />
                  <span className="pv-field-hint">Numero di ripetizioni da eseguire per sessione (es. 5-10).</span>
                </div>

                <div className="pv-modal-form-group">
                  <label>Note per il paziente <span className="pv-opt-tag">(facoltativo)</span></label>
                  <textarea
                    rows={3}
                    placeholder="Es: eseguire il movimento lentamente, non inarcare la schiena..."
                    value={notes}
                    onChange={e => setNotes(e.target.value)}
                  />
                </div>

                <div className="pv-modal-actions">
                  <button
                    className="pv-modal-btn-cancel"
                    onClick={() => setSelectedExercise(null)}
                    disabled={assignSubmitting}
                  >
                    Indietro
                  </button>
                  <button
                    className="pv-modal-btn-submit"
                    onClick={handleConfirmAssignment}
                    disabled={assignSubmitting}
                  >
                    {assignSubmitting ? 'Assegnazione in corso…' : 'Assegna esercizio'}
                  </button>
                </div>
              </div>
            )}

          </div>
        </div>
      )}

    </div>
  );
}
