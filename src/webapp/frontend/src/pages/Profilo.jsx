import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './Form.css';
import './Profilo.css';
import { supabase } from '../SupabaseClient';
import { useAuth } from '../context/AuthContext';

function Profilo() {
  const navigate = useNavigate();
  const { user, profile, role, loading: authLoading, refreshProfile } = useAuth();

  const [isEditing, setIsEditing] = useState(false);
  const [editNome, setEditNome] = useState('');
  const [editCognome, setEditCognome] = useState('');
  const [editError, setEditError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (profile) {
      setEditNome(profile.nome || '');
      setEditCognome(profile.cognome || '');
    }
  }, [profile]);

  if (authLoading) {
    return (
      <div className="pv-doctor-page-bg pv-profile-page-container">
        <div className="glass-card pv-profile-card">
          <p className="pv-profile-loading">Caricamento profilo in corso...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    navigate('/login');
    return null;
  }

  const handleEditClick = () => {
    setIsEditing(true);
    setEditError('');
  };

  const handleCancelClick = () => {
    setIsEditing(false);
    setEditError('');
    if (profile) {
      setEditNome(profile.nome || '');
      setEditCognome(profile.cognome || '');
    }
  };

  const handleSaveClick = async () => {
    const nomeTrim = editNome.trim();
    const cognomeTrim = editCognome.trim();

    if (!nomeTrim || !cognomeTrim) {
      setEditError('Nome e cognome sono obbligatori.');
      return;
    }

    try {
      setIsSaving(true);
      setEditError('');

      const { error } = await supabase
        .from('profili')
        .update({
          nome: nomeTrim,
          cognome: cognomeTrim,
          updated_at: new Date().toISOString()
        })
        .eq('id', user.id);

      if (error) throw error;

      await refreshProfile();
      setIsEditing(false);
      alert('Profilo aggiornato con successo!');

    } catch (err) {
      console.error('Errore salvataggio profilo:', err);
      setEditError(err.message || 'Errore durante l\'aggiornamento del profilo.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="pv-doctor-page-bg pv-profile-page-container">
      <div className="glass-card pv-profile-card">
        
        {/* TITOLO E SOTTOTITOLO COMPATTI */}
        <div className="pv-profile-header">
          <h2 className="pv-profile-title">Profilo PhysioVision</h2>
          <p className="pv-profile-subtitle">Informazioni del tuo account</p>
        </div>

        <div className="pv-profile-details-container">
          
          {/* BADGE RUOLO */}
          <div className="pv-profile-role-badge-row">
            <span className="pv-role-badge">
              Ruolo: {role === 'medico' ? '🩺 MEDICO / FISIOTERAPISTA' : '🏃 PAZIENTE'}
            </span>
          </div>

          {!isEditing ? (
            /* VISUALIZZAZIONE DATI ACCOUNT */
            <div className="pv-profile-view-block">
              <div className="pv-profile-info-grid">
                <div className="pv-profile-info-row">
                  <span className="pv-profile-label">Email:</span>
                  <span className="pv-profile-value">{user.email}</span>
                </div>
                <div className="pv-profile-info-row">
                  <span className="pv-profile-label">Nome:</span>
                  <span className="pv-profile-value">{profile?.nome || 'Inconosciuto'}</span>
                </div>
                <div className="pv-profile-info-row">
                  <span className="pv-profile-label">Cognome:</span>
                  <span className="pv-profile-value">{profile?.cognome || 'Inconosciuto'}</span>
                </div>
              </div>

              <div className="pv-profile-actions">
                <button
                  type="button"
                  className="pv-btn-primary pv-btn-full"
                  onClick={handleEditClick}
                >
                  Modifica Profilo
                </button>
              </div>
            </div>
          ) : (
            /* MODALITÀ MODIFICA PROFILO */
            <div className="pv-profile-edit-form">
              <div className="pv-form-group">
                <label className="pv-form-label">Nome</label>
                <input
                  type="text"
                  className="pv-form-input"
                  value={editNome}
                  onChange={(e) => setEditNome(e.target.value)}
                  placeholder="Inserisci il tuo nome"
                  required
                />
              </div>

              <div className="pv-form-group">
                <label className="pv-form-label">Cognome</label>
                <input
                  type="text"
                  className="pv-form-input"
                  value={editCognome}
                  onChange={(e) => setEditCognome(e.target.value)}
                  placeholder="Inserisci il tuo cognome"
                  required
                />
              </div>

              {editError && <p className="pv-error-message">{editError}</p>}

              <div className="pv-form-actions">
                <button
                  type="button"
                  className="pv-btn-primary"
                  onClick={handleSaveClick}
                  disabled={isSaving}
                >
                  {isSaving ? 'Salvataggio...' : 'Salva Modifiche'}
                </button>

                <button
                  type="button"
                  className="pv-btn-secondary"
                  onClick={handleCancelClick}
                  disabled={isSaving}
                >
                  Annulla
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Profilo;
