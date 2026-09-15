import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../SupabaseClient';
import { useAuth } from '../context/AuthContext';

// ─── Helper: initiali ─────────────────────────────────────────────────────────
function getInitials(nome, cognome) {
  const n = (nome || '').trim();
  const c = (cognome || '').trim();
  if (n && c) return `${n[0]}${c[0]}`.toUpperCase();
  if (n) return n[0].toUpperCase();
  if (c) return c[0].toUpperCase();
  return '?';
}

// ─── Pagina "I miei medici" ───────────────────────────────────────────────────
export default function PatientDoctorsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [doctors, setDoctors] = useState([]);   // lista arricchita con profilo medico
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadDoctors = useCallback(async () => {
    if (!user) return;
    try {
      setLoading(true);
      setError('');

      // 1. Leggi tutte le righe doctor_patients per questo paziente
      const { data: dpList, error: dpErr } = await supabase
        .from('doctor_patients')
        .select('id, doctor_id, status, created_at')
        .eq('patient_id', user.id)
        .order('created_at', { ascending: false });

      if (dpErr) throw dpErr;

      if (!dpList || dpList.length === 0) {
        setDoctors([]);
        setLoading(false);
        return;
      }

      // 2. Recupera i profili dei medici collegati
      const doctorIds = dpList.map(dp => dp.doctor_id);
      const { data: profili, error: profErr } = await supabase
        .from('profili')
        .select('id, nome, cognome, doctor_code')
        .in('id', doctorIds);

      if (profErr) throw profErr;

      const profiliMap = {};
      (profili || []).forEach(p => { profiliMap[p.id] = p; });

      // 3. Unisci i dati
      const enriched = dpList.map(dp => {
        const profilo = profiliMap[dp.doctor_id] || { nome: 'Medico', cognome: 'Sconosciuto', doctor_code: '' };
        return {
          ...dp,
          nome: profilo.nome || '',
          cognome: profilo.cognome || '',
          doctor_code: profilo.doctor_code || '',
          fullName: `${profilo.nome || ''} ${profilo.cognome || ''}`.trim(),
        };
      });

      setDoctors(enriched);
    } catch (err) {
      console.error('Errore caricamento medici:', err);
      setError('Impossibile caricare i dati dei medici. Riprova.');
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => { loadDoctors(); }, [loadDoctors]);

  // Etichetta e colori in base allo status
  const statusStyle = (status) => {
    if (status === 'active') return { label: 'Collegato', bg: '#d8ede0', color: '#4d7c5f' };
    if (status === 'pending') return { label: 'In attesa', bg: '#fff3e0', color: '#e65100' };
    if (status === 'rejected') return { label: 'Rifiutato', bg: '#fce4ec', color: '#c62828' };
    return { label: status, bg: '#f5f5f5', color: '#666' };
  };

  // ── Stili inline (pagina minima, nessun file CSS extra) ─────────────────────
  const pageStyle = {
    width: '100%',
    maxWidth: '760px',
    margin: '0 auto',
    padding: '48px 24px 72px',
    fontFamily: "'Inter', system-ui, sans-serif",
    color: '#1f2824',
  };

  const headerStyle = {
    textAlign: 'center',
    marginBottom: '36px',
  };

  const h1Style = {
    fontFamily: "'Playfair Display', serif",
    fontSize: 'clamp(1.8rem, 4vw, 2.6rem)',
    fontWeight: 700,
    color: '#4d7c5f',
    margin: '0 0 8px',
  };

  const subtitleStyle = {
    fontSize: '1.02rem',
    color: '#5f6f67',
    margin: 0,
  };

  const cardStyle = {
    background: '#ffffff',
    border: '1.5px solid rgba(122, 171, 138, 0.22)',
    borderRadius: '18px',
    padding: '20px 22px',
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    boxShadow: '0 4px 14px rgba(77, 124, 95, 0.06)',
    marginBottom: '14px',
    transition: 'box-shadow 0.2s, border-color 0.2s',
  };

  const avatarStyle = {
    width: '48px',
    height: '48px',
    borderRadius: '50%',
    background: '#d8ede0',
    color: '#4d7c5f',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: 700,
    fontSize: '0.9rem',
    flexShrink: 0,
    letterSpacing: '0.5px',
  };

  const emptyStyle = {
    textAlign: 'center',
    padding: '48px 20px',
    background: '#ffffff',
    border: '1.5px solid rgba(122, 171, 138, 0.18)',
    borderRadius: '18px',
    boxShadow: '0 4px 14px rgba(77, 124, 95, 0.06)',
  };

  return (
    <div style={pageStyle}>

      {/* Header */}
      <div style={headerStyle}>
        <h1 style={h1Style}>I miei medici</h1>
        <p style={subtitleStyle}>Medici collegati al tuo profilo PhysioVision.</p>
      </div>

      {/* Pulsante Collega un medico */}
      <div style={{ textAlign: 'center', marginBottom: '32px' }}>
        <button
          onClick={() => navigate('/paziente/collega-medico')}
          style={{
            background: '#4d7c5f',
            color: '#fff',
            border: 'none',
            borderRadius: '12px',
            padding: '11px 24px',
            fontWeight: 700,
            fontSize: '0.92rem',
            cursor: 'pointer',
            boxShadow: '0 2px 8px rgba(77, 124, 95, 0.18)',
            transition: 'background 0.2s, transform 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = '#3d6850'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = '#4d7c5f'; e.currentTarget.style.transform = 'none'; }}
        >
          + Collega un medico
        </button>
      </div>

      {/* Contenuto */}
      {loading ? (
        <div style={{ textAlign: 'center', color: '#5f6f67', padding: '40px 0', fontSize: '1rem' }}>
          Caricamento medici…
        </div>
      ) : error ? (
        <div style={{ background: '#fff0f0', color: '#b44a4a', padding: '14px 18px', borderRadius: '12px', fontSize: '0.92rem' }}>
          {error}
        </div>
      ) : doctors.length === 0 ? (
        <div style={emptyStyle}>
          <div style={{ fontSize: '2.5rem', marginBottom: '12px', opacity: 0.4 }}>🩺</div>
          <p style={{ fontWeight: 600, color: '#4d7c5f', marginBottom: '6px' }}>Nessun medico collegato</p>
          <p style={{ color: '#5f6f67', fontSize: '0.9rem', margin: 0 }}>
            Usa il pulsante qui sopra per inviare una richiesta al tuo dottore.
          </p>
        </div>
      ) : (
        <div>
          {doctors.map(doc => {
            const st = statusStyle(doc.status);
            return (
              <div key={doc.id} style={cardStyle}>
                {/* Avatar */}
                <div style={avatarStyle}>
                  {getInitials(doc.nome, doc.cognome)}
                </div>

                {/* Info */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: '1rem', color: '#1f2824' }}>
                    {doc.fullName || 'Medico Sconosciuto'}
                  </div>
                  {doc.doctor_code && (
                    <div style={{ fontSize: '0.78rem', color: '#8fa99c', fontFamily: 'monospace', marginTop: '2px' }}>
                      Codice: {doc.doctor_code}
                    </div>
                  )}
                  {doc.created_at && (
                    <div style={{ fontSize: '0.76rem', color: '#aaa', marginTop: '2px' }}>
                      Collegato dal {new Date(doc.created_at).toLocaleDateString('it-IT')}
                    </div>
                  )}
                </div>

                {/* Badge status */}
                <span style={{
                  fontSize: '0.74rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.4px',
                  padding: '4px 12px',
                  borderRadius: '10px',
                  background: st.bg,
                  color: st.color,
                  flexShrink: 0,
                }}>
                  {st.label}
                </span>
              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}
