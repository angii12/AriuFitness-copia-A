import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './WelcomePage.css';
import { supabase } from '../SupabaseClient';

const WelcomePage = () => {
  const navigate = useNavigate();
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      setIsAuthenticated(!!user);
    };
    checkAuth();
  }, []);

  const handleAccedi = () => {
    navigate('/login');
  };

  const handleIniziaPercorso = () => {
    if (isAuthenticated) {
      navigate('/home');
    } else {
      navigate('/login');
    }
  };

  return (
    <div className="ariu-landing">
      {/* Bottone Accedi */}
      <header className="ariu-header">
        <button className="btn-accedi" onClick={handleAccedi}>
          ACCEDI 
          <svg className="icon-user" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
          </svg>
        </button>
      </header>

      {/* Contenitore Testi e Pulsanti principali */}
      <main className="ariu-content">
        <div className="ariu-brand">
          <h1 className="brand-logo">
            <span className="brand-dark">ARIU</span>
            <span className="brand-muted">FITNESS</span>
          </h1>
        </div>

        <h2 className="ariu-title">
          ALLENATI A CASA.<br />
          RITROVA IL TUO EQUILIBRIO.
        </h2>

        <p className="ariu-description">
          Allenamenti efficaci, semplici e guidati con le fitball per il tuo benessere quotidiano.
        </p>

        <div className="ariu-cta-group">
          <button className="btn-primary" onClick={handleIniziaPercorso}>
            INIZIA IL TUO PERCORSO <span className="arrow">→</span>
          </button>
          <button className="btn-secondary">
            SCOPRI DI PIÙ
          </button>
        </div>
      </main>

      {/* Sezione Immagine + Onda (Sotto su mobile, a destra su desktop) */}
      <div className="ariu-image-wrapper">
        <div className="ariu-wave-container">
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="wave-svg">
            {/* Questa curva si adatta sia in verticale che in orizzontale grazie al CSS */}
            <path d="M0,0 L62,0 C55,25 35,45 38,100 L0,100 Z" fill="#ffffff" />
          </svg>
        </div>
        <div className="ariu-background-image"></div>
      </div>
    </div>
  );
};

export default WelcomePage;