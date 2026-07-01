import React, { useMemo, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../SupabaseClient';
import { useColor } from '../context/ColorContext';
import './Form.css';
import './Profilo.css';

function getInitials(user) {
  const name = (user?.nome || user?.first_name || user?.name || '').trim();
  const surname = (user?.cognome || user?.last_name || '').trim();
  if (name || surname) return `${name?.[0] || ''}${surname?.[0] || ''}`.toUpperCase();
  const email = user?.email || '';
  const first = email.split('@')[0] || 'U';
  return first.slice(0, 2).toUpperCase();
}

function safeDate(it) {
  // accetta "YYYY-MM-DD" e lo rende "DD/MM/YYYY"; altrimenti lascia com'è
  if (typeof it !== 'string') return it;
  const m = it.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return it;
  return `${m[3]}/${m[2]}/${m[1]}`;
}

function toIsoDate(value) {
  if (typeof value !== 'string') return '';
  const v = value.trim();
  if (!v) return '';
  if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return v;
  const m = v.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (!m) return '';
  return `${m[3]}-${m[2]}-${m[1]}`;
}

function formatIsoDate(d) {
  const yyyy = String(d.getFullYear()).padStart(4, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

function adultIsoMaxDate() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setFullYear(d.getFullYear() - 18);
  return formatIsoDate(d);
}

function isAdultIsoDate(iso) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return false;
  const [y, m, d] = iso.split('-').map((x) => Number(x));
  const date = new Date(y, m - 1, d);
  if (Number.isNaN(date.getTime())) return false;
  // Controllo che non "ribalti" la data (es. 2024-02-31 -> marzo)
  if (date.getFullYear() !== y || date.getMonth() !== m - 1 || date.getDate() !== d) return false;

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const adultCutoff = new Date(today);
  adultCutoff.setFullYear(adultCutoff.getFullYear() - 18);
  return date <= adultCutoff;
}

// Funzioni di formattazione per la visualizzazione
function formatGenere(value) {
  const map = { 'M': 'Maschio', 'F': 'Femmina', 'Altro': 'Altro' };
  return map[value] || value;
}

function formatColoreAriu(value) {
  const map = {
    'beige': 'Beige',
    'verde': 'Verde',
    'blu': 'Blu',
    'nero': 'Nero'
  };
  return map[value] || value;
}

function formatTempo(value) {
  if (!value) return value;
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatTrainer(value) {
  const map = {
    'm_giovane': 'Maschio Giovane',
    'f_giovane': 'Femmina Giovane',
    'm_adulto': 'Maschio Adulto',
    'f_adulta': 'Femmina Adulta'
  };
  return map[value] || value;
}

function Row({ label, value }) {
  if (!value) return null; // non mostrare la riga se il campo manca
  return (
    <div className="profile-row">
      <span className="profile-label">{label}</span>
      <span className="profile-value">{value}</span>
    </div>
  );
}

export default function Profilo() {
  const { backgroundColor, updateColor } = useColor();
  const navigate = useNavigate();
  const token = useMemo(() => localStorage.getItem('token'), []);
  const userEmail = useMemo(() => {
    const cached = localStorage.getItem('user');
    return cached ? JSON.parse(cached)?.email : null;
  }, []);

  // Stati per i dati da Supabase
  const [userProfileData, setUserProfileData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  // Stati per editing
  const [isEditing, setIsEditing] = useState(false);
  const [editNome, setEditNome] = useState('');
  const [editCognome, setEditCognome] = useState('');
  const [editDobIso, setEditDobIso] = useState('');
  const [editGenere, setEditGenere] = useState('');
  const [editColoreAriu, setEditColoreAriu] = useState('');
  const [editTrainer, setEditTrainer] = useState('');
  const [editPatologie, setEditPatologie] = useState([]);
  const [editTempPatologia, setEditTempPatologia] = useState('');
  const [editTempo, setEditTempo] = useState('');
  const [editError, setEditError] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Carica i dati del profilo da Supabase
  useEffect(() => {
    const loadProfileData = async () => {
      if (!userEmail) {
        setLoadError('Email non trovata');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const { data, error } = await supabase
          .from('profili')
          .select('email, nome, cognome, data_nascita, genere, colore_ariu, trainer, patologie, tempo')
          .eq('email', userEmail)
          .single();

        if (error) throw error;

        setUserProfileData(data);
        // Inizializza i campi di editing
        setEditNome(data?.nome || '');
        setEditCognome(data?.cognome || '');
        setEditDobIso(toIsoDate(data?.data_nascita || ''));
        setEditGenere(data?.genere || '');
        setEditColoreAriu(data?.colore_ariu || '');
        setEditTrainer(data?.trainer || '');
        setEditPatologie(data?.patologie || []);
        setEditTempo(data?.tempo || '');
        setLoadError(null);
      } catch (err) {
        console.error('Errore nel caricamento del profilo:', err);
        setLoadError('Errore nel caricamento del profilo');
        setUserProfileData(null);
      } finally {
        setLoading(false);
      }
    };

    loadProfileData();
  }, [userEmail]);

  if (!token) {
    navigate('/login');
    return null;
  }

  if (loading) {
    return (
      <div className="form-page-container profile-center">
        <div className="form-card profile-card">
          <p style={{ textAlign: 'center' }}>Caricamento profilo...</p>
        </div>
      </div>
    );
  }

  if (loadError || !userProfileData) {
    return (
      <div className="form-page-container profile-center">
        <div className="form-card profile-card">
          <p style={{ textAlign: 'center', color: '#ed3434' }}>{loadError || 'Profilo non trovato'}</p>
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <button className="form-button" onClick={() => navigate('/')} type="button">
              Torna alla Home
            </button>
          </div>
        </div>
      </div>
    );
  }

  const nome = userProfileData?.nome || '';
  const cognome = userProfileData?.cognome || '';
  const dataNascita = safeDate(userProfileData?.data_nascita || '');
  const email = userProfileData?.email || '';
  const genere = userProfileData?.genere || '';
  const coloreAriu = userProfileData?.colore_ariu || '';
  const trainer = userProfileData?.trainer || '';
  const patologie = userProfileData?.patologie || [];
  const tempo = userProfileData?.tempo || '';

  const handleDeleteAccount = async () => {
    const confirmed = window.confirm(
      'Sei sicuro di voler eliminare il tuo account? Questa azione è irreversibile e tutti i tuoi dati verranno cancellati.'
    );
    if (!confirmed) return;

    try {
      setIsDeleting(true);
      setEditError('');

      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error('Utente non trovato');

      const { error: deleteProfileError } = await supabase
        .from('profili')
        .delete()
        .eq('id', user.id);
      if (deleteProfileError) throw deleteProfileError;

      await supabase.rpc('delete_user');

      await supabase.auth.signOut();
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      localStorage.removeItem('selectedExercises');
      navigate('/welcome');
    } catch (err) {
      console.error('Errore eliminazione account:', err);
      setEditError(err?.message || 'Errore durante l\'eliminazione del profilo.');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleStartEdit = () => {
    setEditError('');
    setEditNome(userProfileData?.nome || '');
    setEditCognome(userProfileData?.cognome || '');
    setEditDobIso(toIsoDate(userProfileData?.data_nascita || ''));
    setEditGenere(userProfileData?.genere || '');
    setEditColoreAriu(userProfileData?.colore_ariu || '');
    setEditTrainer(userProfileData?.trainer || '');
    setEditPatologie(userProfileData?.patologie || []);
    setEditTempPatologia('');
    setEditTempo(userProfileData?.tempo || '');
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    setEditError('');
    setIsEditing(false);
  };

  const handleAggiungiPatologia = () => {
    if (editTempPatologia.trim()) {
      setEditPatologie([...editPatologie, editTempPatologia.trim()]);
      setEditTempPatologia('');
    }
  };

  const handleRimuoviPatologia = (index) => {
    setEditPatologie(editPatologie.filter((_, i) => i !== index));
  };

  const handleSave = async () => {
    const nomeTrim = (editNome || '').trim();
    const cognomeTrim = (editCognome || '').trim();
    const dobIso = (editDobIso || '').trim();

    if (!nomeTrim) return setEditError('Inserisci il nome.');
    if (!cognomeTrim) return setEditError('Inserisci il cognome.');
    if (!dobIso) return setEditError('Inserisci la data di nascita.');
    if (!isAdultIsoDate(dobIso)) return setEditError('Devi essere maggiorenne (almeno 18 anni).');
    if (!editGenere) return setEditError('Seleziona il genere.');
    if (!editColoreAriu) return setEditError('Seleziona il colore dell\'Ariu.');
    if (!editTrainer) return setEditError('Seleziona il trainer.');
    if (!editTempo) return setEditError('Seleziona il tempo di allenamento.');

    try {
      setIsSaving(true);
      setEditError('');

      // Aggiorna Supabase
      const { error } = await supabase
        .from('profili')
        .update({
          nome: nomeTrim,
          cognome: cognomeTrim,
          data_nascita: dobIso,
          genere: editGenere,
          colore_ariu: editColoreAriu,
          trainer: editTrainer,
          patologie: editPatologie,
          tempo: editTempo
        })
        .eq('email', email);

      if (error) throw error;

      // Aggiorna lo state locale
      setUserProfileData({
        ...userProfileData,
        nome: nomeTrim,
        cognome: cognomeTrim,
        data_nascita: dobIso,
        genere: editGenere,
        colore_ariu: editColoreAriu,
        trainer: editTrainer,
        patologie: editPatologie,
        tempo: editTempo
      });

      updateColor(editColoreAriu);
      setIsEditing(false);
    } catch (err) {
      console.error('Errore nel salvataggio:', err);
      setEditError(err?.message || 'Salvataggio fallito.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="classcard">
    <div className="form-page-container profile-center">
      <div className="form-card profile-card">
        <h2>Profilo</h2>
        <p className="form-subtitle">Dati del tuo account</p>
  
        <div className="profile-avatar">
          {userProfileData?.avatar_url
            ? <img src={userProfileData.avatar_url} alt="avatar" />
            : <span>{getInitials(userProfileData)}</span>}
        </div>
  
        {/* Riquadro interno con lo stesso stile tipografico e colore della glass card */}
        
          <div className="profile-info-grid">
            {isEditing ? (
              <div className="profile-row">
                <span className="profile-label">Nome</span>
                <span className="profile-value">
                  <input
                    className="profile-input"
                    type="text"
                    value={editNome}
                    onChange={(e) => setEditNome(e.target.value)}
                    autoComplete="given-name"
                    required
                  />
                </span>
              </div>
            ) : (
              <Row label="Nome" value={nome} />
            )}

            {isEditing ? (
              <div className="profile-row">
                <span className="profile-label">Cognome</span>
                <span className="profile-value">
                  <input
                    className="profile-input"
                    type="text"
                    value={editCognome}
                    onChange={(e) => setEditCognome(e.target.value)}
                    autoComplete="family-name"
                    required
                  />
                </span>
              </div>
            ) : (
              <Row label="Cognome" value={cognome} />
            )}

            {isEditing ? (
              <div className="profile-row">
                <span className="profile-label">Data di nascita</span>
                <span className="profile-value">
                  <input
                    className="profile-input"
                    type="date"
                    value={editDobIso}
                    onChange={(e) => setEditDobIso(e.target.value)}
                    max={adultIsoMaxDate()}
                    required
                  />
                </span>
              </div>
            ) : (
              <Row label="Data di nascita" value={dataNascita} />
            )}
            <Row label="Email" value={email} />

            {isEditing ? (
              <div className="profile-row">
                <span className="profile-label">Genere</span>
                <span className="profile-value">
                  <select
                    className="profile-input"
                    value={editGenere}
                    onChange={(e) => setEditGenere(e.target.value)}
                    required
                  >
                    <option value="" disabled hidden>Seleziona genere</option>
                    <option value="M">Maschio</option>
                    <option value="F">Femmina</option>
                    <option value="Altro">Altro</option>
                  </select>
                </span>
              </div>
            ) : (
              <Row label="Genere" value={formatGenere(genere)} />
            )}

            {isEditing ? (
              <div className="profile-row">
                <span className="profile-label">Colore dell'Ariu</span>
                <span className="profile-value">
                  <select
                    className="profile-input"
                    value={editColoreAriu}
                    onChange={(e) => setEditColoreAriu(e.target.value)}
                    required
                  >
                    <option value="" disabled hidden>Seleziona colore</option>
                    <option value="beige">Beige</option>
                    <option value="verde">Verde</option>
                    <option value="blu">Blu</option>
                    <option value="nero">Nero</option>
                  </select>
                </span>
              </div>
            ) : (
              <Row label="Colore dell'Ariu" value={formatColoreAriu(coloreAriu)} />
            )}

            {isEditing ? (
              <div className="profile-row">
                <span className="profile-label">Trainer</span>
                <span className="profile-value">
                  <select
                    className="profile-input"
                    value={editTrainer}
                    onChange={(e) => setEditTrainer(e.target.value)}
                    required
                  >
                    <option value="" disabled hidden>Seleziona trainer</option>
                    <option value="m_giovane">Giovane maschio</option>
                    <option value="f_giovane">Giovane femmina</option>
                    <option value="m_adulto">Adulto maschio</option>
                    <option value="f_adulta">Adulto femmina</option>
                  </select>
                </span>
              </div>
            ) : (
              <Row label="Trainer" value={formatTrainer(trainer)} />
            )}

            {isEditing ? (
              <div className="profile-row" style={{ gridColumn: '1 / -1', flexDirection: 'column', alignItems: 'flex-start' }}>
                <span className="profile-label">Tempo di allenamento</span>
                <span className="profile-value" style={{ width: '100%' }}>
                  <select
                    className="profile-input"
                    value={editTempo}
                    onChange={(e) => setEditTempo(e.target.value)}
                    required
                    style={{ width: '100%' }}
                  >
                    <option value="" disabled hidden>Seleziona frequenza</option>
                    <option value="occasionalmente">Occasionalmente</option>
                    <option value="1 volta a settimana">1 volta a settimana</option>
                    <option value="2-3 volte a settimana">2-3 volte a settimana</option>
                    <option value="4-5 volte a settimana">4-5 volte a settimana</option>
                    <option value="ogni giorno">Ogni giorno</option>
                  </select>
                </span>
              </div>
            ) : (
              <Row label="Tempo di allenamento" value={formatTempo(tempo)} />
            )}

            {isEditing ? (
              <div style={{ gridColumn: '1 / -1', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <span className="profile-label">Patologie</span>
                <div className="patologie-input-container">
                  <input
                    type="text"
                    value={editTempPatologia}
                    onChange={(e) => setEditTempPatologia(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleAggiungiPatologia()}
                    placeholder="Inserisci una patologia"
                  />
                  <button
                    type="button"
                    onClick={handleAggiungiPatologia}
                    className="patologie-add-button"
                  >
                    Aggiungi
                  </button>
                </div>
                {editPatologie.length > 0 && (
                  <div>
                    <p style={{ margin: '5px 0', fontWeight: '600', fontSize: 'clamp(0.9rem, 2vw, 1rem)' }}>Patologie inserite:</p>
                    {editPatologie.map((patologia, index) => (
                      <div key={index} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px', backgroundColor: '#f5e6d3', borderRadius: '8px', marginBottom: '8px', border: '1px solid #d4c4b0' }}>
                        <span style={{ color: '#2d2d2d', fontWeight: '500' }}>{patologia}</span>
                        <button
                          type="button"
                          onClick={() => handleRimuoviPatologia(index)}
                          style={{ padding: '6px 14px', backgroundColor: '#c1121f', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: 'clamp(0.8rem, 2vw, 0.9rem)', fontWeight: '600', transition: 'all 0.2s ease' }}
                          onMouseEnter={(e) => e.target.style.backgroundColor = '#a00d1a'}
                          onMouseLeave={(e) => e.target.style.backgroundColor = '#c1121f'}
                        >
                          Rimuovi
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <Row label="Patologie" value={patologie.length > 0 ? patologie.join(', ') : '-'} />
            )}
          </div>

          {isEditing && editError ? <p className="error-message">{editError}</p> : null}
  
          <div className="profile-actions">
            {isEditing ? (
              <>
                <button className="form-button form-button--secondary" onClick={handleCancelEdit} type="button" disabled={isSaving}>
                  Annulla
                </button>
                <button className="form-button" onClick={handleSave} type="button" disabled={isSaving}>
                  {isSaving ? 'Salvataggio...' : 'Salva'}
                </button>
              </>
            ) : (
              <>
                <button className="form-button form-button--secondary" onClick={handleStartEdit} type="button">
                  Modifica
                </button>
                <button className="form-button" onClick={() => navigate('/')} type="button">
                  Torna alla Home
                </button>
                <button
                  className="form-button form-button--danger"
                  onClick={handleDeleteAccount}
                  type="button"
                  disabled={isDeleting}
                >
                  {isDeleting ? 'Eliminazione...' : 'Elimina account'}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
  
}
