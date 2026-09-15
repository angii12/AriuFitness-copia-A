import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import './Form.css';
import './Register.css';
import { supabase } from '../SupabaseClient';
import { useAuth } from '../context/AuthContext';

function Register() {
  const [formData, setFormData] = useState({
    nome: '',
    cognome: '',
    email: '',
    password: '',
    ruolo: 'paziente'
  });

  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const navigate = useNavigate();
  const { refreshProfile } = useAuth();

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    if (!formData.nome.trim() || !formData.cognome.trim()) {
      setError('Inserisci nome e cognome.');
      setLoading(false);
      return;
    }

    if (!formData.email.trim() || !formData.password.trim()) {
      setError('Inserisci un\'email e una password valide.');
      setLoading(false);
      return;
    }

    try {
      // 1. Registrazione utente in Supabase Auth con metadati
      const { data: authData, error: authError } = await supabase.auth.signUp({
        email: formData.email.trim(),
        password: formData.password,
        options: {
          data: {
            nome: formData.nome.trim(),
            cognome: formData.cognome.trim(),
            ruolo: formData.ruolo
          }
        }
      });

      if (authError) throw authError;

      const user = authData.user;
      if (!user) {
        throw new Error('Impossibile creare l\'utente.');
      }

      // 2. Il profilo in public.profili verrà creato automaticamente dal trigger sul database
      // Dato che la conferma email è disabilitata, la sessione è già attiva.
      const profile = await refreshProfile(user);

      // 3. Redirect diretto alla pagina corretta
      if (profile?.ruolo === 'medico') {
        navigate('/medico', { replace: true });
      } else {
        navigate('/paziente', { replace: true });
      }

    } catch (err) {
      console.error('Errore registrazione:', err);
      setError(err.message || 'Errore durante la registrazione.');
    } finally {
      setLoading(false);
    }
  };

  const togglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  return (
    <div className="form-page-container">
      <div className="glass-card form-card">
        <h2>Crea il tuo account PhysioVision</h2>
        <p className="form-subtitle">Seleziona il tuo ruolo ed accedi alla piattaforma</p>

        <form onSubmit={handleSubmit}>
          <input
            type="text"
            name="nome"
            placeholder="Nome"
            value={formData.nome}
            onChange={handleChange}
            required
          />

          <input
            type="text"
            name="cognome"
            placeholder="Cognome"
            value={formData.cognome}
            onChange={handleChange}
            required
          />

          <input
            type="email"
            name="email"
            placeholder="Email"
            value={formData.email}
            onChange={handleChange}
            required
          />

          <div className="password-container">
            <input
              type={showPassword ? 'text' : 'password'}
              name="password"
              placeholder="Password"
              value={formData.password}
              onChange={handleChange}
              required
            />
            <button
              type="button"
              onClick={togglePasswordVisibility}
              className="show-password-button"
            >
              {showPassword ? 'Nascondi' : 'Mostra'}
            </button>
          </div>

          <div className="form-gender-dropdown">
            <label htmlFor="ruolo" style={{ fontWeight: 600, color: '#5B120F', fontSize: '0.9rem' }}>
              Seleziona Ruolo Utente *
            </label>
            <select
              id="ruolo"
              name="ruolo"
              value={formData.ruolo}
              onChange={handleChange}
              required
            >
              <option value="paziente">Paziente</option>
              <option value="medico">Medico / Fisioterapista</option>
            </select>
          </div>

          <button type="submit" disabled={loading} className="pv-btn pv-btn-primary" style={{width: '100%', marginTop: '10px'}}>
            {loading ? 'Registrazione in corso...' : 'Registrati'}
          </button>
        </form>

        {error && <p className="error-message">{error}</p>}

        <p className="switch-form-text">
          Hai già un account?{' '}
          <Link to="/login" className="switch-form-link">
            Accedi
          </Link>
        </p>
      </div>
    </div>
  );
}

export default Register;