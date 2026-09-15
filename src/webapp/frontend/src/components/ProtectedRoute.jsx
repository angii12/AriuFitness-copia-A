import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh', color: '#5B120F' }}>
        <p style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>Verifica autenticazione in corso...</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/welcome" replace />;
  }

  return children;
};

export const DoctorRoute = ({ children }) => {
  const { user, isMedico, isPaziente, loading } = useAuth();

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh', color: '#5B120F' }}>
        <p style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>Verifica autorizzazione Medico in corso...</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/welcome" replace />;
  }

  if (isPaziente) {
    return (
      <div className="glass-card" style={{ maxWidth: '600px', margin: '80px auto', padding: '40px', textAlign: 'center' }}>
        <h2 style={{ color: '#d9534f', marginBottom: '16px' }}>🚫 Accesso Negato</h2>
        <p style={{ fontSize: '1.1rem', marginBottom: '24px', color: '#333' }}>
          Questa area è riservata esclusivamente ai <strong>Medici / Fisioterapisti</strong>.
        </p>
        <button
          onClick={() => window.location.href = '/'}
          style={{
            padding: '12px 24px',
            backgroundColor: '#5B120F',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '1rem',
            fontWeight: 'bold'
          }}
        >
          Torna alla Homepage Paziente
        </button>
      </div>
    );
  }

  if (!isMedico) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh', color: '#5B120F' }}>
        <p style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>Verifica profilo Medico in corso...</p>
      </div>
    );
  }

  return (
    <div className="pv-doctor-page-bg">
      {children}
    </div>
  );
};

/**
 * PatientRoute — Fonte autorevole: Supabase Auth → public.profili → ruolo = 'paziente'
 *
 * - non autenticato  → /welcome
 * - medico           → /medico/crea-esercizio (accesso negato con messaggio)
 * - paziente         → children
 *
 * NON usa localStorage come fonte autorevole.
 * Il ruolo è quello letto da public.profili via AuthContext (fetchProfile).
 */
export const PatientRoute = ({ children }) => {
  const { user, isPaziente, isMedico, loading } = useAuth();

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh', color: '#5B120F' }}>
        <p style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>Verifica autorizzazione in corso...</p>
      </div>
    );
  }

  // Non autenticato → login/welcome
  if (!user) {
    return <Navigate to="/welcome" replace />;
  }

  // Medico → questa rotta è solo per pazienti
  if (isMedico) {
    return (
      <div className="glass-card" style={{ maxWidth: '600px', margin: '80px auto', padding: '40px', textAlign: 'center' }}>
        <h2 style={{ color: '#d9534f', marginBottom: '16px' }}>🚫 Area Pazienti</h2>
        <p style={{ fontSize: '1.1rem', marginBottom: '24px', color: '#333' }}>
          Questa pagina è riservata ai <strong>pazienti</strong>.
          Come medico, gestisci le assegnazioni dal portale medico.
        </p>
        <button
          onClick={() => window.location.href = '/medico/pazienti'}
          style={{
            padding: '12px 24px',
            backgroundColor: '#5B120F',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '1rem',
            fontWeight: 'bold'
          }}
        >
          Vai al Portale Medico
        </button>
      </div>
    );
  }

  // Ruolo non ancora caricato o stato indefinito (non paziente, non medico)
  // Questo caso non dovrebbe accadere in produzione, ma gestiamolo con grazia
  if (!isPaziente) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh', color: '#888' }}>
        <p>Verifica profilo in corso...</p>
      </div>
    );
  }

  return (
    <div className="pv-patient-page-bg">
      {children}
    </div>
  );
};

