import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './PatientHomePage.css';

export default function PatientHomePage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  // Il nome può essere nel user_metadata di Supabase Auth
  const firstName = user?.user_metadata?.nome || user?.user_metadata?.name?.split(' ')[0] || null;

  return (
    <div className="pv-patient-dashboard">
      <div className="pv-patient-header">
        <h1 className="pv-patient-title">
          {firstName ? `Benvenuto, ${firstName}` : 'Benvenuto'}
        </h1>
        <p className="pv-patient-subtitle">
          Consulta gli esercizi assegnati dai tuoi medici e avvia le tue sessioni riabilitative.
        </p>
      </div>

      <div className="pv-patient-grid">

        {/* Card 1 — I miei esercizi */}
        <div
          className="pv-patient-card pv-pcard-exercises"
          onClick={() => navigate('/paziente/esercizi')}
        >
          <div className="pv-pcard-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 11l3 3L22 4" />
              <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
            </svg>
          </div>
          <h3>I miei esercizi</h3>
          <p>Visualizza gli esercizi assegnati dai tuoi medici.</p>
        </div>

        {/* Card 2 — I miei medici */}
        <div
          className="pv-patient-card pv-pcard-doctors"
          onClick={() => navigate('/paziente/medici')}
        >
          <div className="pv-pcard-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
          </div>
          <h3>I miei medici</h3>
          <p>Visualizza i medici collegati al tuo profilo.</p>
        </div>

        {/* Card 3 — Profilo */}
        <div
          className="pv-patient-card pv-pcard-profile"
          onClick={() => navigate('/paziente/profilo')}
        >
          <div className="pv-pcard-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>
          <h3>Profilo</h3>
          <p>Visualizza e modifica le informazioni del tuo account.</p>
        </div>

      </div>
    </div>
  );
}
