import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../SupabaseClient';
import { useAuth } from '../context/AuthContext';
import './DoctorPatientsPage.css';

// ─── Helper: initiali del paziente ────────────────────────────────────────────
function getInitials(nome, cognome) {
  const n = (nome || '').trim();
  const c = (cognome || '').trim();
  if (n && c) return `${n[0]}${c[0]}`.toUpperCase();
  if (n) return n[0].toUpperCase();
  if (c) return c[0].toUpperCase();
  return '?';
}

// ─── Pagina principale ────────────────────────────────────────────────────────
function DoctorPatientsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [doctorCode, setDoctorCode] = useState(null);
  const [pendingRequests, setPendingRequests] = useState([]);
  const [activePatients, setActivePatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoadingId, setActionLoadingId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  const loadData = useCallback(async () => {
    if (!user) return;
    try {
      setLoading(true);
      setError('');

      // 1. doctor_code
      const { data: docData } = await supabase
        .from('profili')
        .select('doctor_code')
        .eq('id', user.id)
        .single();
      setDoctorCode(docData?.doctor_code || '');

      // 2. doctor_patients per il medico
      const { data: dpList, error: dpError } = await supabase
        .from('doctor_patients')
        .select('id, patient_id, status, created_at')
        .eq('doctor_id', user.id)
        .order('created_at', { ascending: false });
      if (dpError) throw dpError;

      if (!dpList || dpList.length === 0) {
        setPendingRequests([]);
        setActivePatients([]);
        setLoading(false);
        return;
      }

      // 3. Profili dei pazienti
      const patientIds = dpList.map(dp => dp.patient_id);
      const { data: profiliPazienti, error: profError } = await supabase
        .from('profili')
        .select('id, nome, cognome')
        .in('id', patientIds);
      if (profError) throw profError;

      const profiliMap = {};
      (profiliPazienti || []).forEach(p => { profiliMap[p.id] = p; });

      const pending = [];
      const active = [];

      dpList.forEach(item => {
        const pInfo = profiliMap[item.patient_id] || { nome: 'Paziente', cognome: 'Sconosciuto' };
        const fullItem = {
          ...item,
          patientName: `${pInfo.nome} ${pInfo.cognome}`.trim(),
          nome: pInfo.nome || '',
          cognome: pInfo.cognome || '',
        };
        if (item.status === 'pending') pending.push(fullItem);
        else if (item.status === 'active') active.push(fullItem);
      });

      setPendingRequests(pending);
      setActivePatients(active);
    } catch (err) {
      console.error('Errore caricamento pazienti medico:', err);
      setError('Impossibile caricare i dati dei pazienti.');
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleUpdateStatus = async (requestId, newStatus) => {
    try {
      setActionLoadingId(requestId);
      const { error } = await supabase
        .from('doctor_patients')
        .update({ status: newStatus })
        .eq('id', requestId)
        .eq('doctor_id', user.id);
      if (error) throw error;
      await loadData();
      alert(`Richiesta ${newStatus === 'active' ? 'Accettata ✓' : 'Rifiutata'} con successo!`);
    } catch (err) {
      console.error('Errore aggiornamento stato:', err);
      alert('Errore durante l\'aggiornamento della richiesta.');
    } finally {
      setActionLoadingId(null);
    }
  };

  const copyToClipboard = () => {
    if (doctorCode && doctorCode !== '') {
      navigator.clipboard.writeText(doctorCode);
      alert('Codice medico copiato negli appunti!');
    }
  };

  // Filtro frontend case-insensitive su nome, cognome, nome+cognome
  const filteredPatients = activePatients.filter(pat => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.trim().toLowerCase();
    const nome = (pat.nome || '').toLowerCase();
    const cognome = (pat.cognome || '').toLowerCase();
    const full = `${nome} ${cognome}`;
    return nome.includes(q) || cognome.includes(q) || full.includes(q);
  });

  return (
    <div className="pv-patients-page">
      <div className="pv-patients-content">

        {/* ═══ HEADER — direttamente sullo sfondo ═══ */}
        <div className="pv-patients-header">
          <h1>I miei pazienti</h1>
          <p>Gestisci i collegamenti e i pazienti associati al tuo profilo.</p>
        </div>

        {/* ═══ CARD CODICE MEDICO — compatta, centrata ═══ */}
        <div className="pv-patients-code-card">
          <div className="pv-code-info">
            <span className="pv-code-label">Codice Medico</span>
            <span className="pv-code-value">
              {doctorCode === null
                ? 'Caricamento codice...'
                : doctorCode !== ''
                ? doctorCode
                : 'Codice non disponibile'}
            </span>
            <span className="pv-code-hint">Usa questo codice per collegare un paziente al tuo profilo.</span>
          </div>
          <button 
            className="pv-patients-btn-copy" 
            onClick={copyToClipboard}
            disabled={!doctorCode}
            style={!doctorCode ? { opacity: 0.6, cursor: 'not-allowed' } : undefined}
          >
            📋 Copia codice
          </button>
        </div>

        {loading ? (
          <div className="pv-patients-loading">Caricamento dati pazienti…</div>
        ) : error ? (
          <div className="pv-patients-error">{error}</div>
        ) : (
          <>
            {/* ═══ SEZIONE RICHIESTE DI COLLEGAMENTO — card separata ═══ */}
            <div className="pv-patients-section-card">
              <h3 className="pv-patients-section-title">
                Richieste di collegamento
                <span className="pv-count-badge">{pendingRequests.length}</span>
              </h3>

              {pendingRequests.length === 0 ? (
                <div className="pv-patients-empty">
                  <span className="pv-patients-empty-icon">✓</span>
                  Nessuna richiesta in attesa.
                </div>
              ) : (
                <div className="pv-pending-list">
                  {pendingRequests.map(req => (
                    <div key={req.id} className="pv-pending-request">
                      <div className="pv-pending-info-row">
                        <div className="pv-pending-avatar">
                          {getInitials(req.nome, req.cognome)}
                        </div>
                        <div>
                          <div className="pv-pending-name">{req.patientName}</div>
                          {req.created_at && (
                            <div className="pv-pending-date">
                              Richiesta inviata il {new Date(req.created_at).toLocaleDateString('it-IT')}
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="pv-pending-actions">
                        <button
                          className="pv-patients-btn-accept"
                          disabled={actionLoadingId === req.id}
                          onClick={() => handleUpdateStatus(req.id, 'active')}
                        >
                          ✓ Accetta
                        </button>
                        <button
                          className="pv-patients-btn-reject"
                          disabled={actionLoadingId === req.id}
                          onClick={() => handleUpdateStatus(req.id, 'rejected')}
                        >
                          ✕ Rifiuta
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* ═══ BARRA DI RICERCA — sempre visibile, centrata ═══ */}
            <div className="pv-patients-search-wrapper">
              <svg className="pv-patients-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                className="pv-patients-search"
                placeholder="Cerca paziente..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
              />
            </div>

            {/* ═══ SEZIONE PAZIENTI COLLEGATI — card separata ═══ */}
            <div className="pv-patients-section-card">
              <h3 className="pv-patients-section-title">
                Pazienti collegati
                <span className="pv-count-badge">{activePatients.length}</span>
              </h3>

              {activePatients.length === 0 ? (
                <div className="pv-patients-empty">
                  <span className="pv-patients-empty-icon">👥</span>
                  Nessun paziente collegato.
                </div>
              ) : filteredPatients.length === 0 ? (
                <div className="pv-patients-empty">
                  <span className="pv-patients-empty-icon">🔍</span>
                  Nessun paziente trovato.
                </div>
              ) : (
                <div className="pv-patient-list">
                  {filteredPatients.map(pat => (
                    <div
                      key={pat.id}
                      className="pv-patient-row"
                      onClick={() => navigate(`/medico/pazienti/${pat.patient_id}`)}
                      style={{ cursor: 'pointer' }}
                      title="Apri scheda paziente"
                    >
                      <div className="pv-patient-avatar">
                        {getInitials(pat.nome, pat.cognome)}
                      </div>
                      <div className="pv-patient-info">
                        <div className="pv-patient-name">{pat.patientName}</div>
                        {pat.created_at && (
                          <div className="pv-patient-date">
                            Collegato dal {new Date(pat.created_at).toLocaleDateString('it-IT')}
                          </div>
                        )}
                      </div>
                      <span className="pv-patient-badge">Scheda Paziente →</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default DoctorPatientsPage;
