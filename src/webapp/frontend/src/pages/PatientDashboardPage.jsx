import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../SupabaseClient';
import { useAuth } from '../context/AuthContext';
import './PatientDashboardPage.css';

// ─── Helper: iniziali ─────────────────────────────────────────────────────────
function getInitials(nome, cognome) {
  const n = (nome || '').trim();
  const c = (cognome || '').trim();
  if (n && c) return `${n[0]}${c[0]}`.toUpperCase();
  if (n) return n[0].toUpperCase();
  if (c) return c[0].toUpperCase();
  return '?';
}

/**
 * PatientDashboardPage
 * ─────────────────────────────────────────────────────────────────────────────
 * Pagina "I miei esercizi":
 * Mostra gli esercizi assegnati al paziente raggruppati per Medico/Fisioterapista.
 */
export default function PatientDashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [doctorGroups, setDoctorGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadData = useCallback(async () => {
    if (!user) return;
    try {
      setLoading(true);
      setError('');

      // 1. Carica gli esercizi assegnati al paziente
      const { data: assignments, error: aeErr } = await supabase
        .from('assigned_exercises')
        .select(`
          id, doctor_id, target_reps, notes, assigned_at, exercise_id, model_id,
          esercizi:exercise_id ( nome, descrizione, categoria )
        `)
        .eq('patient_id', user.id)
        .order('assigned_at', { ascending: false });

      if (aeErr) throw aeErr;

      // 1b. Carica lo storico sessioni riabilitative completate per questo paziente
      const { data: sessions, error: sessErr } = await supabase
        .from('rehab_sessions')
        .select('id, assignment_id, status, completed_at, reps_completed, target_reps')
        .eq('patient_id', user.id)
        .eq('status', 'completed')
        .order('completed_at', { ascending: false });

      if (sessErr) {
        console.warn('Errore lettura rehab_sessions:', sessErr);
      }

      // Mappa della sessione più recente per ciascun assignment_id
      const latestSessionByAssignment = {};
      (sessions || []).forEach(sess => {
        if (sess.assignment_id && !latestSessionByAssignment[sess.assignment_id]) {
          latestSessionByAssignment[sess.assignment_id] = sess;
        }
      });

      // 2. Carica i collegamenti attivi per il paziente (per avere anche medici attivi)
      const { data: dpList, error: dpErr } = await supabase
        .from('doctor_patients')
        .select('id, doctor_id, status, created_at')
        .eq('patient_id', user.id)
        .eq('status', 'active');

      if (dpErr) throw dpErr;

      // Raccogli tutti i doctor_id unici
      const doctorIdSet = new Set();
      (assignments || []).forEach(a => {
        if (a.doctor_id) doctorIdSet.add(a.doctor_id);
      });
      (dpList || []).forEach(dp => {
        if (dp.doctor_id) doctorIdSet.add(dp.doctor_id);
      });

      const doctorIds = Array.from(doctorIdSet);

      if (doctorIds.length === 0) {
        setDoctorGroups([]);
        setLoading(false);
        return;
      }

      // 3. Recupera i profili dei medici
      const { data: profili, error: profErr } = await supabase
        .from('profili')
        .select('id, nome, cognome')
        .in('id', doctorIds);

      if (profErr) {
        console.warn('Errore lettura profili medici:', profErr);
      }

      const profiliMap = {};
      (profili || []).forEach(p => {
        profiliMap[p.id] = p;
      });

      // 4. Raggruppa gli esercizi per doctor_id
      const groupedMap = new Map();

      // Inizializza i gruppi per ogni medico
      doctorIds.forEach(docId => {
        const p = profiliMap[docId];
        const nome = p?.nome || 'Medico';
        const cognome = p?.cognome || 'collegato';
        const fullName = p ? `${nome} ${cognome}`.trim() : 'Medico collegato';

        groupedMap.set(docId, {
          doctorId: docId,
          doctorName: fullName,
          doctorInitials: getInitials(p?.nome, p?.cognome),
          doctorRole: 'Medico / Fisioterapista',
          exercises: []
        });
      });

      // Distribuisci gli esercizi nel rispettivo medico arricchendoli con lo stato completamento
      (assignments || []).forEach(a => {
        const latestSession = latestSessionByAssignment[a.id];
        const isCompleted = Boolean(latestSession && latestSession.status === 'completed');
        const completedAt = latestSession?.completed_at || null;

        const enhancedAssignment = {
          ...a,
          isCompleted,
          completedAt,
          latestSession
        };

        if (groupedMap.has(a.doctor_id)) {
          groupedMap.get(a.doctor_id).exercises.push(enhancedAssignment);
        }
      });

      // Filtra i gruppi che hanno esercizi (o mantieni solo quelli con assegnazioni o attivi)
      const groups = Array.from(groupedMap.values()).filter(g => g.exercises.length > 0);

      setDoctorGroups(groups);

    } catch (err) {
      console.error('Errore caricamento esercizi paziente:', err);
      setError('Impossibile caricare i tuoi dati. Riprova.');
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Gestione avvio sessione con assignmentId sia in URL query che in location.state
  const handleStartSession = (assignmentId, exerciseName) => {
    navigate(`/patient-session?assignmentId=${assignmentId}`, {
      state: { assignment_id: assignmentId, exercise_name: exerciseName }
    });
  };

  return (
    <div className="pv-patient-dash-page">
      <div className="pv-patient-dash-content">

        {/* ── Header Pagina ──────────────────────────────────────────── */}
        <div className="pv-patient-dash-header">
          <h1>I miei esercizi</h1>
          <p>Visualizza gli esercizi assegnati dai tuoi medici e avvia le sessioni riabilitative.</p>
        </div>

        {loading ? (
          <div className="pv-patient-dash-loading">Caricamento piano riabilitativo…</div>
        ) : error ? (
          <div className="pv-patient-dash-error">{error}</div>
        ) : doctorGroups.length === 0 ? (
          /* ── Empty State ─────────────────────────────────────────────── */
          <div className="pv-patient-dash-empty-card">
            <div className="pv-patient-dash-empty-icon">📋</div>
            <h3>Nessun esercizio assegnato</h3>
            <p>
              Non hai ancora esercizi nel tuo piano riabilitativo.
              Se non hai ancora collegato il tuo medico, collegalo con il suo codice per ricevere il piano personalizzato.
            </p>
            <a href="/paziente/collega-medico" className="pv-btn-connect-doctor">
              🩺 Collega il tuo Medico
            </a>
          </div>
        ) : (
          /* ── Card per ogni Medico ───────────────────────────────────── */
          <div>
            {doctorGroups.map(group => (
              <div key={group.doctorId} className="pv-doctor-group-card">

                {/* Header Medico */}
                <div className="pv-doctor-group-header">
                  <div className="pv-doctor-avatar">
                    {group.doctorInitials}
                  </div>
                  <div className="pv-doctor-info-text">
                    <h3 className="pv-doctor-name">{group.doctorName}</h3>
                    <span className="pv-doctor-role-tag">{group.doctorRole}</span>
                  </div>
                  <span className="pv-doctor-count-badge">
                    {group.exercises.length} {group.exercises.length === 1 ? 'esercizio' : 'esercizi'}
                  </span>
                </div>

                {/* Sezioni Esercizi del Medico: 1. Da fare | 2. Completati */}
                {(() => {
                  const todoExercises = group.exercises.filter(ex => !ex.isCompleted);
                  const completedExercises = group.exercises.filter(ex => ex.isCompleted);

                  const renderExerciseItem = (a, idx) => {
                    const exNome = a.esercizi?.nome || 'Esercizio';
                    const exDesc = a.esercizi?.descrizione;

                    return (
                      <div key={a.id} className="pv-patient-exercise-item">
                        {/* Informazioni Esercizio */}
                        <div className="pv-pex-info">
                          <div className="pv-pex-title-row">
                            <span className="pv-pex-num">{idx + 1}</span>
                            <strong className="pv-pex-name">{exNome}</strong>

                            {a.isCompleted ? (
                              <span className="pv-pex-status-badge pv-pex-status-badge--completed">
                                ✓ COMPLETATO
                              </span>
                            ) : (
                              <span className="pv-pex-status-badge pv-pex-status-badge--todo">
                                ⏳ DA FARE
                              </span>
                            )}
                          </div>

                          {exDesc && (
                            <p className="pv-pex-desc">{exDesc}</p>
                          )}

                          {a.notes && (
                            <div className="pv-pex-notes">
                              <span className="pv-pex-notes-lbl">Note del medico:</span>
                              <p className="pv-pex-notes-text">{a.notes}</p>
                            </div>
                          )}

                          <div className="pv-pex-meta-row">
                            {a.assigned_at && (
                              <span>Prescritto il {new Date(a.assigned_at).toLocaleDateString('it-IT')}</span>
                            )}
                            {a.isCompleted && a.completedAt && (
                              <span className="pv-pex-completed-date">
                                • Completato il {new Date(a.completedAt).toLocaleDateString('it-IT')}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Blocco Target Reps & Pulsante Avvia Sessione */}
                        <div className="pv-pex-action-col">
                          <div className="pv-pex-reps-box">
                            <span className="pv-pex-reps-num">{a.target_reps}</span>
                            <span className="pv-pex-reps-lbl">ripetizioni</span>
                          </div>

                          <button
                            className="pv-btn-start-session"
                            onClick={() => handleStartSession(a.id, exNome)}
                            title={a.isCompleted ? "Ripeti sessione riabilitativa" : "Avvia sessione riabilitativa"}
                          >
                            ▶ Avvia sessione
                          </button>
                        </div>
                      </div>
                    );
                  };

                  return (
                    <div>
                      {/* SEZIONE 1: Da fare */}
                      <div className="pv-exercises-section">
                        <div className="pv-exercises-section-header">
                          <h4 className="pv-exercises-section-title">
                            <span>⏳ Da fare</span>
                            <span className="pv-exercises-section-badge">{todoExercises.length}</span>
                          </h4>
                        </div>

                        {todoExercises.length > 0 ? (
                          <div className="pv-doctor-exercises-list">
                            {todoExercises.map((a, idx) => renderExerciseItem(a, idx))}
                          </div>
                        ) : (
                          <div className="pv-exercises-section-empty">
                            Hai completato tutti gli esercizi assegnati.
                          </div>
                        )}
                      </div>

                      {/* SEZIONE 2: Completati */}
                      <div className="pv-exercises-section">
                        <div className="pv-exercises-section-header">
                          <h4 className="pv-exercises-section-title">
                            <span>✓ Completati</span>
                            <span className="pv-exercises-section-badge">{completedExercises.length}</span>
                          </h4>
                        </div>

                        {completedExercises.length > 0 ? (
                          <div className="pv-doctor-exercises-list">
                            {completedExercises.map((a, idx) => renderExerciseItem(a, idx))}
                          </div>
                        ) : (
                          <div className="pv-exercises-section-empty">
                            Non hai ancora completato esercizi.
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })()}

              </div>
            ))}
          </div>
        )}

      </div>
    </div>
  );
}
