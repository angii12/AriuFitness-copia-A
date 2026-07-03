import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom'; // <-- Assicurati che Link sia qui
import './Form.css';
import './Login.css';

import { supabase } from '../SupabaseClient'; // Importa il client Supabase
function Login() {
    const [formData, setFormData] = useState({
        username: '', // L'endpoint /token si aspetta 'username'
        password: '',
    });
    const [error, setError] = useState('');
    const navigate = useNavigate();
    const [showPassword, setShowPassword] = useState(false);

    const handleChange = (e) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };
    
    const handleSubmit = async (e) => {
      e.preventDefault();
      setError('');

      // 1. Esegui il login direttamente su Supabase
      const { data, error } = await supabase.auth.signInWithPassword({
        email: formData.username,
        password: formData.password,
      });

      if (error) {
        setError(error.message);
        return;
      }
      

      // 2. Supabase gestisce già il token per te
      const session = data.session;
      localStorage.setItem('token', session.access_token);
      localStorage.setItem('user', JSON.stringify(data.user));

      // 3. Carica le opzioni utente in localStorage per uso immediato
      const { data: profilo } = await supabase
        .from('profili')
        .select('opzione_tutorial, opzione_tts, tutorial_visti')
        .eq('id', data.user.id)
        .single();
      if (profilo) {
        localStorage.setItem('tutorialMode', profilo.opzione_tutorial || 'sovrapposizione');
        localStorage.setItem('ttsEnabled', profilo.opzione_tts !== false ? 'true' : 'false');
        localStorage.setItem('tutorial_visti', JSON.stringify(profilo.tutorial_visti || []));
      }

      navigate('/');
      window.location.reload();
    };

      const togglePasswordVisibility = () => {
        setShowPassword(!showPassword);
      };

    return (
        <div className="form-page-container">
          <div className="glass-card form-card">
            <h2>Welcome!</h2> 
            
            <p className="form-subtitle">Accedi per continuare il tuo viaggio</p>
            <form onSubmit={handleSubmit}>
              <input type="email" name="username" placeholder="Email" onChange={handleChange} required />
              <div className="password-container">
                <input type={showPassword ? 'text' : 'password'} name="password" placeholder="Password" onChange={handleChange} required />
                <button 
                  type="button"
                  onClick={togglePasswordVisibility}
                  className="show-password-button"
                >
                  {showPassword ? "Nascondi" : "Mostra"}
                </button>
              </div>
              <button type="submit" className="form-button">Accedi</button>
            </form>
            {error && <p className="error-message">{error}</p>}
            <p className="switch-form-text">
              Non hai un account? <Link to="/register" className="switch-form-link">Registrati</Link>
            </p>
          </div>
        </div>
        
      );
}

export default Login;