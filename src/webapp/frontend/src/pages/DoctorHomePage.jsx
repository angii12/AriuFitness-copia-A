import React from 'react';
import { useNavigate } from 'react-router-dom';
import './DoctorHomePage.css';

export default function DoctorHomePage() {
  const navigate = useNavigate();

  return (
    <div className="pv-doctor-dashboard">
      <div className="pv-doctor-header">
        <h1 className="pv-doctor-title">Benvenuto</h1>
        <p className="pv-doctor-subtitle">
          Gestisci i tuoi pazienti, gli esercizi e i modelli riabilitativi.
        </p>
      </div>

      <div className="pv-doctor-grid">
        <div 
          className="pv-doctor-card pv-card-patients" 
          onClick={() => navigate('/medico/pazienti')}
        >
          <div className="pv-card-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
              <circle cx="9" cy="7" r="4"></circle>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
              <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
            </svg>
          </div>
          <h3>I miei pazienti</h3>
          <p>Monitora i progressi e assegna piani riabilitativi.</p>
        </div>

        <div 
          className="pv-doctor-card pv-card-exercise" 
          onClick={() => navigate('/medico/crea-esercizio')}
        >
          <div className="pv-card-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <line x1="12" y1="8" x2="12" y2="16"></line>
              <line x1="8" y1="12" x2="16" y2="12"></line>
            </svg>
          </div>
          <h3>Crea esercizio</h3>
          <p>Acquisisci e segmenta un nuovo esercizio.</p>
        </div>

        <div 
          className="pv-doctor-card pv-card-library" 
          onClick={() => navigate('/medico/esercizi')}
        >
          <div className="pv-card-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="8" y1="6" x2="21" y2="6"></line>
              <line x1="8" y1="12" x2="21" y2="12"></line>
              <line x1="8" y1="18" x2="21" y2="18"></line>
              <line x1="3" y1="6" x2="3.01" y2="6"></line>
              <line x1="3" y1="12" x2="3.01" y2="12"></line>
              <line x1="3" y1="18" x2="3.01" y2="18"></line>
            </svg>
          </div>
          <h3>Elenco esercizi</h3>
          <p>Libreria modelli e gestione esercizi clinici.</p>
        </div>

        <div 
          className="pv-doctor-card pv-card-profile" 
          onClick={() => navigate('/medico/profilo')}
        >
          <div className="pv-card-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
              <circle cx="12" cy="7" r="4"></circle>
            </svg>
          </div>
          <h3>Profilo</h3>
          <p>Gestisci le informazioni e le impostazioni account.</p>
        </div>
      </div>
    </div>
  );
}
