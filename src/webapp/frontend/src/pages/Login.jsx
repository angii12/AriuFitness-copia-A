import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import './Form.css';
import './Login.css';
import { supabase } from '../SupabaseClient';
import { useAuth } from '../context/AuthContext';

function Login() {
  const [formData, setFormData] = useState({
    username: '', // email
    password: '',
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

    try {
      // 1. Login con Supabase Auth
      const { data, error: authError } = await supabase.auth.signInWithPassword({
        email: formData.username.trim(),
        password: formData.password,
      });

      if (authError) throw authError;

      const user = data.user;

      // 2. Recupera il profilo da public.profili usando user.id
      const { data: profilo } = await supabase
        .from('profili')
        .select('id, nome, cognome, ruolo, opzione_tutorial, opzione_tts, tutorial_visti')
        .eq('id', user.id)
        .maybeSingle();

      const ruolo = profilo?.ruolo || user.user_metadata?.ruolo || 'paziente';
      
      // Sincronizza lo stato in AuthContext
      await refreshProfile();

      if (profilo) {
        localStorage.setItem('tutorialMode', profilo.opzione_tutorial || 'sovrapposizione');
        localStorage.setItem('ttsEnabled', profilo.opzione_tts !== false ? 'true' : 'false');
        localStorage.setItem('tutorial_visti', JSON.stringify(profilo.tutorial_visti || []));
      }

      // 3. Redirect in base al ruolo del profilo
      if (ruolo === 'medico') {
        navigate('/medico', { replace: true });
      } else {
        navigate('/paziente', { replace: true });
      }

    } catch (err) {
      console.error('Errore Login:', err);
      setError(err.message || 'Credenziali non valide o errore durante l\'accesso.');
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
        <h2>Accedi a PhysioVision</h2>
        <p className="form-subtitle">Inserisci le tue credenziali per accedere</p>

        <form onSubmit={handleSubmit}>
          <input
            type="email"
            name="username"
            placeholder="Email"
            value={formData.username}
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

          <button type="submit" disabled={loading} className="pv-btn pv-btn-primary" style={{width: '100%', marginTop: '10px'}}>
            {loading ? 'Accesso in corso...' : 'Accedi'}
          </button>
        </form>

        {error && <p className="error-message">{error}</p>}

        <p className="switch-form-text">
          Non hai un account?{' '}
          <Link to="/register" className="switch-form-link">
            Registrati
          </Link>
        </p>
      </div>
    </div>
  );
}

export default Login;