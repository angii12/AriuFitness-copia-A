import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom'; // <-- Assicurati che Link sia qui
import './Form.css';

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
          <svg className="waves" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 320" preserveAspectRatio="none"><path fill="#93100b" fillOpacity="0.3" d="M0,288L17.1,261.3C34.3,235,69,181,103,165.3C137.1,149,171,171,206,160C240,149,274,107,309,117.3C342.9,128,377,192,411,229.3C445.7,267,480,277,514,277.3C548.6,277,583,267,617,250.7C651.4,235,686,213,720,202.7C754.3,192,789,192,823,170.7C857.1,149,891,107,926,117.3C960,128,994,192,1029,197.3C1062.9,203,1097,149,1131,149.3C1165.7,149,1200,203,1234,229.3C1268.6,256,1303,256,1337,234.7C1371.4,213,1406,171,1423,149.3L1440,128L1440,320L1422.9,320C1405.7,320,1371,320,1337,320C1302.9,320,1269,320,1234,320C1200,320,1166,320,1131,320C1097.1,320,1063,320,1029,320C994.3,320,960,320,926,320C891.4,320,857,320,823,320C788.6,320,754,320,720,320C685.7,320,651,320,617,320C582.9,320,549,320,514,320C480,320,446,320,411,320C377.1,320,343,320,309,320C274.3,320,240,320,206,320C171.4,320,137,320,103,320C68.6,320,34,320,17,320L0,320Z"></path></svg>
          <svg className="waves" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 320" preserveAspectRatio="none"><path fill="#93100b" fillOpacity="0.1" d="M0,0L17.1,32C34.3,64,69,128,103,154.7C137.1,181,171,171,206,160C240,149,274,139,309,160C342.9,181,377,235,411,256C445.7,277,480,267,514,218.7C548.6,171,583,85,617,64C651.4,43,686,85,720,138.7C754.3,192,789,256,823,261.3C857.1,267,891,213,926,176C960,139,994,117,1029,101.3C1062.9,85,1097,75,1131,101.3C1165.7,128,1200,192,1234,218.7C1268.6,245,1303,235,1337,208C1371.4,181,1406,139,1423,117.3L1440,96L1440,320L1422.9,320C1405.7,320,1371,320,1337,320C1302.9,320,1269,320,1234,320C1200,320,1166,320,1131,320C1097.1,320,1063,320,1029,320C994.3,320,960,320,926,320C891.4,320,857,320,823,320C788.6,320,754,320,720,320C685.7,320,651,320,617,320C582.9,320,549,320,514,320C480,320,446,320,411,320C377.1,320,343,320,309,320C274.3,320,240,320,206,320C171.4,320,137,320,103,320C68.6,320,34,320,17,320L0,320Z"></path></svg>
        </div>
        
      );
}

export default Login;