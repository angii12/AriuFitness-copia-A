import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom'; // <-- Assicurati che Link sia qui
import './Form.css';
import './Register.css';
import { supabase } from '../SupabaseClient'; // Importa il client Supabase

function Register() {
  const [step, setStep] = useState(1); // Step 1: Registrazione, Step 2: Questionario
  const [formData, setFormData] = useState({
    nome: '',
    cognome: '',
    data_nascita: '',
    email: '',
    password: '',
    genere: '',
  });
  const [questionarioData, setQuestionarioData] = useState({
    colore_ariu: '',
    tempo: '',
    patologie: [],
    trainer: '',
  });
  const [tempPatologia, setTempPatologia] = useState('');
  const [error, setError] = useState('');
  const [userId, setUserId] = useState(null);
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleQuestionarioChange = (e) => {
    setQuestionarioData({ ...questionarioData, [e.target.name]: e.target.value });
  };

  const aggiungiPatologia = () => {
    if (tempPatologia.trim()) {
      setQuestionarioData({
        ...questionarioData,
        patologie: [...questionarioData.patologie, tempPatologia.trim()]
      });
      setTempPatologia('');
    }
  };

  const rimuoviPatologia = (index) => {
    setQuestionarioData({
      ...questionarioData,
      patologie: questionarioData.patologie.filter((_, i) => i !== index)
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // Validazione maggiorenne 
    const birthDate = new Date(formData.data_nascita);
    const today = new Date();
    let age = today.getFullYear() - birthDate.getFullYear();
    if (today < new Date(birthDate.setFullYear(today.getFullYear()))) age--;

    if (age < 18) {
      setError('Devi essere maggiorenne per registrarti.');
      return;
    }

    // --- VALIDAZIONE PASSWORD ---
    const password = formData.password;
    
    // Requisiti: 8 caratteri, 1 Maiuscola, 1 Minuscola, 1 Numero, 1 Segno Speciale
    const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/;

    if (!passwordRegex.test(password)) {
      setError(
        'La password deve contenere almeno 8 caratteri, una maiuscola, una minuscola, un numero e un carattere speciale (@$!%*?&).'
      );
      return;
    }

    try {
      // STEP 1: Registrazione ufficiale su Supabase Auth
      const { data: authData, error: authError } = await supabase.auth.signUp({
        email: formData.email,
        password: formData.password,
      });

      if (authError) throw authError;

      // STEP 2: Inserimento dati extra nella tabella 'profili'
      if (authData.user) {
        const { error: profileError } = await supabase
          .from('profili')
          .insert([
            {
              id: authData.user.id,
              email: formData.email,
              nome: formData.nome,
              cognome: formData.cognome,
              data_nascita: formData.data_nascita,
              genere: formData.genere
            },
          ]);

        if (profileError) throw profileError;
        
        // Salva l'userId per il prossimo step
        setUserId(authData.user.id);
        // Passa al questionario
        setStep(2);
      }

    } catch (err) {
      console.error('Errore:', err);
      setError(err.message || 'Errore durante la registrazione');
    }
  };

  const handleQuestionarioSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // Validazione campi obbligatori
    if (!questionarioData.colore_ariu || !questionarioData.tempo || !questionarioData.trainer) {
      setError('Per favore compila tutti i campi obbligatori.');
      return;
    }

    try {
      // Aggiornamento dati questionario nella tabella 'profili'
      const { error: updateError } = await supabase
        .from('profili')
        .update({
          colore_ariu: questionarioData.colore_ariu,
          tempo: questionarioData.tempo,
          patologie: questionarioData.patologie,
          trainer: questionarioData.trainer,
        })
        .eq('id', userId);

      if (updateError) throw updateError;

      alert('Registrazione completata! Effettua l\'accesso per entrare!.');
      navigate('/login');

    } catch (err) {
      console.error('Errore:', err);
      setError(err.message || 'Errore durante il salvataggio del profilo');
    }
  };
  
    const togglePasswordVisibility = () => {
      setShowPassword(!showPassword);
    };

    return (
        <div className="form-page-container">
            <div className="glass-card form-card">
                {step === 1 ? (
                  <>
                    <h2>Crea il tuo account</h2>
                    <form onSubmit={handleSubmit}>
                        <input type="text" name="nome" placeholder="Nome" onChange={handleChange} required />
                        
                        <input type="text" name="cognome" placeholder="Cognome" onChange={handleChange} required />
                        
                        <input type="date" name="data_nascita" placeholder="Date of Birth" onChange={handleChange} required />
                        
                        <div className="form-gender-dropdown">
                          <select 
                            id="genere" 
                            name="genere" 
                            onChange={handleChange} 
                            required 
                            defaultValue=""
                          >
                            <option value="" disabled hidden>Genere</option>
                            <option value="M">Maschio</option>
                            <option value="F">Femmina</option>
                            <option value="Altro">Altro</option>
                          </select>
                        </div>
                        
                        <input type="email" name="email" placeholder="Email" onChange={handleChange} required />
                        
                        <div className="password-container">
                        <input type={showPassword ? 'text' : 'password'} name="password" placeholder="Password" onChange={handleChange} required />
                        <button type="button" className="show-password-button" onClick={togglePasswordVisibility}>
                          {showPassword ? "Nascondi" : "Mostra"}
                        </button>
                        </div>
                        <button type="submit" className="form-button">Avanti</button>
                    </form>
                    {error && <p className="error-message">{error}</p>}
                    <p className="switch-form-text">
                    Hai già un account? <Link to="/login" className="switch-form-link">Accedi</Link>
                    </p>
                  </>
                ) : (
                  <>
                    <h2>Un'esperienza personalizzata!</h2>
                    <form onSubmit={handleQuestionarioSubmit}>
                        <div className="color-picker-label">
                          <label htmlFor="colore_ariu">Di che colore è il tuo divano Ariu?</label>
                          <div className="color-grid">
                            <label className="color-option">
                              <input type="radio" name="colore_ariu" value="beige" checked={questionarioData.colore_ariu === "beige"} onChange={handleQuestionarioChange} required className="hide-radio"/>
                              <span className="color-box box-beige">Beige</span>
                            </label>
                            <label className="color-option">
                              <input type="radio" name="colore_ariu" value="verde" checked={questionarioData.colore_ariu === "verde"} onChange={handleQuestionarioChange} required className="hide-radio"/>
                              <span className="color-box box-verde">Verde</span>
                            </label>
                            <label className="color-option">
                              <input type="radio" name="colore_ariu" value="blu" checked={questionarioData.colore_ariu === "blu"} onChange={handleQuestionarioChange} required className="hide-radio"/>
                              <span className="color-box box-blu">Blu</span>
                            </label>
                            <label className="color-option">
                              <input type="radio" name="colore_ariu" value="nero" checked={questionarioData.colore_ariu === "nero"} onChange={handleQuestionarioChange} required className="hide-radio"/>
                              <span className="color-box box-nero">Nero</span>
                            </label>
                          </div>
                        </div>

                        <div className="form-gender-dropdown">
                          <label>Quanto tempo pensi di impiegare in media per l'attività fisica?</label>
                          <div className="time-list">
                            <label className="time-list-item">
                              <input 
                                type="radio" 
                                name="tempo" 
                                value="ogni giorno" 
                                checked={questionarioData.tempo === "ogni giorno"}
                                onChange={handleQuestionarioChange} 
                                required 
                                className="hide-radio"
                              />
                              <span className="time-box">Ogni giorno</span>
                            </label>
                            <label className="time-list-item">
                              <input 
                                type="radio" 
                                name="tempo" 
                                value="4-5 volte a settimana" 
                                checked={questionarioData.tempo === "4-5 volte a settimana"}
                                onChange={handleQuestionarioChange} 
                                required 
                                className="hide-radio"
                              />
                              <span className="time-box">4-5 volte a settimana</span>
                            </label>
                            <label className="time-list-item">
                              <input 
                                type="radio" 
                                name="tempo" 
                                value="2-3 volte a settimana" 
                                checked={questionarioData.tempo === "2-3 volte a settimana"}
                                onChange={handleQuestionarioChange} 
                                required 
                                className="hide-radio"
                              />
                              <span className="time-box">2-3 volte a settimana</span>
                            </label>
                            <label className="time-list-item">
                              <input 
                                type="radio" 
                                name="tempo" 
                                value="1 volta a settimana" 
                                checked={questionarioData.tempo === "1 volta a settimana"}
                                onChange={handleQuestionarioChange} 
                                required 
                                className="hide-radio"
                              />
                              <span className="time-box">1 volta a settimana</span>
                            </label>
                            <label className="time-list-item">
                              <input 
                                type="radio" 
                                name="tempo" 
                                value="occasionalmente" 
                                checked={questionarioData.tempo === "occasionalmente"}
                                onChange={handleQuestionarioChange} 
                                required 
                                className="hide-radio"
                              />
                              <span className="time-box">Occasionalmente</span>
                            </label>
                          </div>
                        </div>

                        <div className="form-gender-dropdown">
                          <label htmlFor="patologie">Soffri di particolari patologie?</label>
                          <div className="patologie-input-container">
                            <input 
                              type="text"
                              value={tempPatologia}
                              onChange={(e) => setTempPatologia(e.target.value)}
                              onKeyPress={(e) => e.key === 'Enter' && aggiungiPatologia()}
                              placeholder="Inserisci una patologia"
                            />
                            <button 
                              type="button"
                              onClick={aggiungiPatologia}
                              className="patologie-add-button"
                            >
                              Aggiungi
                            </button>
                          </div>
                          {questionarioData.patologie.length > 0 && (
                            <div className="patologie-list">
                              <p style={{ margin: '5px 0', fontWeight: '600', fontSize: 'clamp(0.9rem, 2vw, 1rem)' }}>Patologie inserite:</p>
                              {questionarioData.patologie.map((patologia, index) => (
                                <div key={index} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px', backgroundColor: '#f5e6d3', borderRadius: '8px', marginBottom: '8px', border: '1px solid #d4c4b0' }}>
                                  <span style={{ color: '#2d2d2d', fontWeight: '500' }}>{patologia}</span>
                                  <button
                                    type="button"
                                    onClick={() => rimuoviPatologia(index)}
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

                        <div className="form-gender-dropdown">
                          <label>Quale trainer vuoi che ti assista nel tuo percorso?</label>
                          <div className="trainer-grid">
                            <label className="trainer-grid-item">
                              <input 
                                type="radio" 
                                name="trainer" 
                                value="m_giovane" 
                                checked={questionarioData.trainer === "m_giovane"}
                                onChange={handleQuestionarioChange} 
                                required 
                                className="hide-radio"
                              />
                              <span className="trainer-box">Giovane maschio</span>
                            </label>
                            <label className="trainer-grid-item">
                              <input 
                                type="radio" 
                                name="trainer" 
                                value="f_giovane" 
                                checked={questionarioData.trainer === "f_giovane"}
                                onChange={handleQuestionarioChange} 
                                required 
                                className="hide-radio"
                              />
                              <span className="trainer-box">Giovane femmina</span>
                            </label>
                            <label className="trainer-grid-item">
                              <input 
                                type="radio" 
                                name="trainer" 
                                value="m_adulto" 
                                checked={questionarioData.trainer === "m_adulto"}
                                onChange={handleQuestionarioChange} 
                                required 
                                className="hide-radio"
                              />
                              <span className="trainer-box">Adulto maschio</span>
                            </label>
                            <label className="trainer-grid-item">
                              <input 
                                type="radio" 
                                name="trainer" 
                                value="f_adulta" 
                                checked={questionarioData.trainer === "f_adulta"}
                                onChange={handleQuestionarioChange} 
                                required 
                                className="hide-radio"
                              />
                              <span className="trainer-box">Adulto femmina</span>
                            </label>
                          </div>
                        </div>
                        <div>
                          <p>Potrai modificare queste informazioni in qualsiasi momento.</p>
                        </div>

                        <button type="submit" className="form-button">Completa registrazione</button>
                    </form>
                    {error && <p className="error-message">{error}</p>}
                  </>
                )}
            </div>
            <svg className="waves" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 320" preserveAspectRatio="none"><path fill="#ffffff" fillOpacity="0.3" d="M0,288L17.1,261.3C34.3,235,69,181,103,165.3C137.1,149,171,171,206,160C240,149,274,107,309,117.3C342.9,128,377,192,411,229.3C445.7,267,480,277,514,277.3C548.6,277,583,267,617,250.7C651.4,235,686,213,720,202.7C754.3,192,789,192,823,170.7C857.1,149,891,107,926,117.3C960,128,994,192,1029,197.3C1062.9,203,1097,149,1131,149.3C1165.7,149,1200,203,1234,229.3C1268.6,256,1303,256,1337,234.7C1371.4,213,1406,171,1423,149.3L1440,128L1440,320L1422.9,320C1405.7,320,1371,320,1337,320C1302.9,320,1269,320,1234,320C1200,320,1166,320,1131,320C1097.1,320,1063,320,1029,320C994.3,320,960,320,926,320C891.4,320,857,320,823,320C788.6,320,754,320,720,320C685.7,320,651,320,617,320C582.9,320,549,320,514,320C480,320,446,320,411,320C377.1,320,343,320,309,320C274.3,320,240,320,206,320C171.4,320,137,320,103,320C68.6,320,34,320,17,320L0,320Z"></path></svg>
            <svg className="waves" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 320" preserveAspectRatio="none"><path fill="#ffffff" fillOpacity="0.1" d="M0,0L17.1,32C34.3,64,69,128,103,154.7C137.1,181,171,171,206,160C240,149,274,139,309,160C342.9,181,377,235,411,256C445.7,277,480,267,514,218.7C548.6,171,583,85,617,64C651.4,43,686,85,720,138.7C754.3,192,789,256,823,261.3C857.1,267,891,213,926,176C960,139,994,117,1029,101.3C1062.9,85,1097,75,1131,101.3C1165.7,128,1200,192,1234,218.7C1268.6,245,1303,235,1337,208C1371.4,181,1406,139,1423,117.3L1440,96L1440,320L1422.9,320C1405.7,320,1371,320,1337,320C1302.9,320,1269,320,1234,320C1200,320,1166,320,1131,320C1097.1,320,1063,320,1029,320C994.3,320,960,320,926,320C891.4,320,857,320,823,320C788.6,320,754,320,720,320C685.7,320,651,320,617,320C582.9,320,549,320,514,320C480,320,446,320,411,320C377.1,320,343,320,309,320C274.3,320,240,320,206,320C171.4,320,137,320,103,320C68.6,320,34,320,17,320L0,320Z"></path></svg>
        </div>
    );
}

export default Register;