import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../SupabaseClient';
import { useAuth } from '../context/AuthContext';
import './Form.css';

const AuthCallback = () => {
  const navigate = useNavigate();
  const { refreshProfile } = useAuth();

  useEffect(() => {
    let mounted = true;

    const handleCallback = async () => {
      try {
        // Supabase-js manages the hash parsing automatically, 
        // we just need to get the resulting session.
        const { data: { session }, error } = await supabase.auth.getSession();

        if (error) {
          console.error("Errore durante il callback di auth:", error);
          if (mounted) navigate('/login', { replace: true });
          return;
        }

        if (session && session.user) {
          // Force refresh of the profile from the database
          const profile = await refreshProfile(session.user);
          
          if (mounted) {
            // Re-indirizza in base al ruolo in modo stretto
            if (profile?.ruolo === 'medico') {
              navigate('/medico/crea-esercizio', { replace: true });
            } else if (profile?.ruolo === 'paziente') {
              navigate('/piano-riabilitativo', { replace: true });
            } else {
              navigate('/login', { replace: true });
            }
          }
        } else {
          // Nessuna sessione valida trovata nel callback
          if (mounted) navigate('/login', { replace: true });
        }
      } catch (err) {
        console.error("Eccezione durante il callback:", err);
        if (mounted) navigate('/login', { replace: true });
      }
    };

    handleCallback();

    return () => {
      mounted = false;
    };
  }, [navigate, refreshProfile]);

  return (
    <div className="form-page-container">
      <div className="glass-card form-card" style={{ textAlign: 'center' }}>
        <h2>Completamento accesso...</h2>
        <p className="form-subtitle">Attendi mentre completiamo la tua autenticazione.</p>
        <div style={{ marginTop: '20px' }}>
          {/* Semplice spinner animato in linea */}
          <div style={{ 
            display: 'inline-block',
            width: '40px',
            height: '40px',
            border: '4px solid rgba(255, 255, 255, 0.3)',
            borderRadius: '50%',
            borderTopColor: '#fff',
            animation: 'spin 1s ease-in-out infinite'
          }}></div>
          <style>{`
            @keyframes spin {
              to { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      </div>
    </div>
  );
};

export default AuthCallback;
