import React, { useState, useEffect } from 'react';
import { supabase } from '../SupabaseClient';
import { useAuth } from '../context/AuthContext';
import './Form.css';

function ConnectDoctorPage() {
  const { user } = useAuth();
  const [doctorCode, setDoctorCode] = useState('');
  const [connectionState, setConnectionState] = useState({
    status: 'loading', // 'none', 'pending', 'active', 'loading'
    doctor: null,
    request: null
  });
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Carica lo stato attuale del collegamento
  const loadConnectionStatus = async () => {
    if (!user) return;
    try {
      setError('');
      const { data: dp, error: dpError } = await supabase
        .from('doctor_patients')
        .select('id, doctor_id, patient_id, status, created_at')
        .eq('patient_id', user.id)
        .maybeSingle();

      if (dpError && dpError.code !== 'PGRST116') throw dpError;

      if (!dp || dp.status === 'rejected') {
        setConnectionState({ status: 'none', doctor: null, request: null });
        return;
      }

      // Se esiste una riga (pending o active), recupera i dati del medico
      const { data: docProfile } = await supabase
        .from('profili')
        .select('id, nome, cognome, doctor_code')
        .eq('id', dp.doctor_id)
        .maybeSingle();

      setConnectionState({
        status: dp.status,
        doctor: docProfile,
        request: dp
      });

    } catch (err) {
      console.error('Errore nel caricamento del collegamento medico:', err);
      setError('Impossibile verificare lo stato del collegamento.');
    }
  };

  useEffect(() => {
    loadConnectionStatus();
  }, [user]);

  const handleSubmitCode = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    const cleanCode = doctorCode.trim().toUpperCase();
    if (!cleanCode) {
      setError('Inserisci un codice medico valido.');
      setSubmitting(false);
      return;
    }

    try {
      // 1. Cerca il medico tramite RPC sicura find_doctor_by_code
      const { data: doctorList, error: rpcError } = await supabase
        .rpc('find_doctor_by_code', { p_code: cleanCode });

      if (rpcError) throw rpcError;

      if (!doctorList || doctorList.length === 0) {
        setError('Codice medico non valido o inesistente.');
        setSubmitting(false);
        return;
      }

      const foundDoctor = doctorList[0];

      // 2. Impedisci auto-collegamento
      if (foundDoctor.id === user.id) {
        setError('Non puoi inserire il tuo stesso codice medico.');
        setSubmitting(false);
        return;
      }

      // 3. Inserisci la richiesta in doctor_patients
      const { error: insertError } = await supabase
        .from('doctor_patients')
        .insert({
          doctor_id: foundDoctor.id,
          patient_id: user.id,
          status: 'pending'
        });

      if (insertError) {
        if (insertError.code === '23505') { // unique_doctor_patient
          setError('Hai già inviato una richiesta a questo medico.');
        } else {
          throw insertError;
        }
        setSubmitting(false);
        return;
      }

      setDoctorCode('');
      await loadConnectionStatus();
      alert('Richiesta di collegamento inviata al medico con successo!');

    } catch (err) {
      console.error('Errore invio richiesta collegamento:', err);
      setError(err.message || 'Errore durante l\'invio della richiesta.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="form-page-container" style={{ background: 'transparent' }}>
      <div className="glass-card form-card" style={{ maxWidth: '560px', width: '100%' }}>
        <h2>🩺 Collega il tuo Medico</h2>
        <p className="form-subtitle">Associa il tuo account al medico per ricevere i piani di riabilitazione personalizzati</p>

        {connectionState.status === 'loading' ? (
          <div style={{ padding: '30px 0', color: 'var(--pv-sage-dark, #4d7c5f)', fontWeight: 600 }}>
            Verifica dello stato in corso...
          </div>
        ) : connectionState.status === 'none' ? (
          /* STATO 1: NESSUN MEDICO COLLEGATO */
          <div style={{ width: '100%', marginTop: '10px' }}>
            <div style={{
              backgroundColor: 'rgba(122, 171, 138, 0.12)',
              color: 'var(--pv-sage-deep, #274433)',
              border: '1.5px solid rgba(122, 171, 138, 0.25)',
              padding: '14px 18px',
              borderRadius: '12px',
              marginBottom: '22px',
              fontSize: '0.92rem',
              lineHeight: 1.5,
              textAlign: 'left'
            }}>
              ℹ️ <strong>Nessun medico collegato:</strong> Richiedi al tuo dottore il suo codice univoco (es. <code>DOC-A7K92Q</code>) ed inseriscilo qui sotto.
            </div>

            <form onSubmit={handleSubmitCode}>
              <div style={{ marginBottom: '16px', textAlign: 'left' }}>
                <label style={{ display: 'block', fontWeight: 700, color: 'var(--pv-sage-dark, #4d7c5f)', marginBottom: '8px', fontSize: '0.95rem' }}>
                  Codice Medico Univoco *
                </label>
                <input
                  type="text"
                  placeholder="Es. DOC-A7K92Q"
                  value={doctorCode}
                  onChange={(e) => setDoctorCode(e.target.value.toUpperCase())}
                  style={{ textTransform: 'uppercase', letterSpacing: '1.5px', fontWeight: 'bold' }}
                  required
                />
              </div>

              <button type="submit" className="form-button" disabled={submitting}>
                {submitting ? 'Verifica ed Invio in corso...' : 'Invia Richiesta di Collegamento'}
              </button>
            </form>

            {error && <p className="error-message" style={{ marginTop: '15px' }}>{error}</p>}
          </div>
        ) : connectionState.status === 'pending' ? (
          /* STATO 2: RICHIESTA IN ATTESA */
          <div style={{ width: '100%', marginTop: '10px', textAlign: 'center' }}>
            <div style={{
              backgroundColor: 'rgba(255, 193, 7, 0.12)',
              color: '#856404',
              border: '1.5px solid rgba(255, 193, 7, 0.3)',
              padding: '24px 20px',
              borderRadius: '16px',
              marginBottom: '15px'
            }}>
              <h3 style={{ marginBottom: '10px', fontSize: '1.15rem', color: '#b7791f' }}>⏳ Richiesta in Attesa di Conferma</h3>
              <p style={{ fontSize: '0.95rem', margin: '8px 0', color: '#4a5568' }}>
                Hai inviato una richiesta al medico:
              </p>
              <h4 style={{ fontSize: '1.25rem', color: 'var(--pv-sage-deep, #274433)', marginTop: '8px', fontWeight: 700 }}>
                Dr. {connectionState.doctor?.nome} {connectionState.doctor?.cognome}
              </h4>
              <p style={{ fontSize: '0.85rem', color: '#718096', marginTop: '12px' }}>
                Il tuo medico deve accedere al proprio portale ed accettare la richiesta prima che sia attiva.
              </p>
            </div>
          </div>
        ) : (
          /* STATO 3: MEDICO COLLEGATO (ACTIVE) */
          <div style={{ width: '100%', marginTop: '10px', textAlign: 'center' }}>
            <div style={{
              backgroundColor: 'rgba(122, 171, 138, 0.15)',
              color: 'var(--pv-sage-deep, #274433)',
              padding: '26px 20px',
              borderRadius: '16px',
              border: '1.5px solid rgba(122, 171, 138, 0.35)'
            }}>
              <h3 style={{ marginBottom: '10px', color: 'var(--pv-sage-dark, #4d7c5f)', fontSize: '1.2rem' }}>✅ Dottore Collegato</h3>
              <div style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--pv-sage-deep, #274433)', margin: '12px 0' }}>
                Dr. {connectionState.doctor?.nome} {connectionState.doctor?.cognome}
              </div>
              <p style={{ fontSize: '0.92rem', color: '#4a5568' }}>
                Codice Medico: <strong style={{ letterSpacing: '1px', color: 'var(--pv-sage-dark, #4d7c5f)' }}>{connectionState.doctor?.doctor_code}</strong>
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ConnectDoctorPage;
