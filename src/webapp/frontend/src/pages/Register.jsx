import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom'; // <-- Assicurati che Link sia qui
import './Form.css';
import './Register.css';
import { supabase } from '../SupabaseClient'; // Importa il client Supabase

function Register() {
  const [step, setStep] = useState(1); // Step 1: Registrazione, Step 2-5: Questionario (1 domanda per step)
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
  
  // Funzioni di navigazione per il questionario
  const handleNextQuestion = () => {
    // Validazione della domanda corrente
    if (step === 2 && !questionarioData.colore_ariu) {
      setError('Per favore seleziona un colore.');
      return;
    }
    if (step === 3 && !questionarioData.tempo) {
      setError('Per favore seleziona un tempo.');
      return;
    }
    if (step === 4) {
      // Domanda sulle patologie: può essere saltata (facoltativa)
    }
    if (step === 5 && !questionarioData.trainer) {
      setError('Per favore seleziona un trainer.');
      return;
    }
    
    setError('');
    setStep(step + 1);
  };

  const handlePreviousQuestion = () => {
    setError('');
    setStep(step - 1);
  };

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
      // UNICO STEP: Registrazione ufficiale + invio metadati
      const { data: authData, error: authError } = await supabase.auth.signUp({
        email: formData.email,
        password: formData.password,
        options: {
          // Inseriamo i dati aggiuntivi nei metadata dell'utente
          data: {
            nome: formData.nome,
            cognome: formData.cognome,
            data_nascita: formData.data_nascita,
            genere: formData.genere,
          }
        }
      });

      if (authError) throw authError;

      // Se la registrazione ha successo, la riga nella tabella 'profili' 
      // viene creata AUTOMATICAMENTE sul database in una frazione di millisecondo.
      if (authData.user) {
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

    // Validazione campi obbligatori (solo passo 5, ultimo step)
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

      alert('Registrazione completata! Conferma l\'email ed effettua l\'accesso per entrare!.');
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
                ) : step === 2 ? (
                  <>
                    <h2>Un'esperienza personalizzata!</h2>
                    <form key="step2">
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
                        <div>
                          <p>Potrai modificare queste informazioni in qualsiasi momento.</p>
                        </div>
                        <div style={{ display: 'flex', gap: '10px', justifyContent: 'space-between' }}>
                          <button type="button" className="form-button back-forward" onClick={handlePreviousQuestion}>Indietro</button>
                          <button type="button" className="form-button back-forward" onClick={handleNextQuestion}>Avanti</button>
                        </div>
                    </form>
                    {error && <p className="error-message">{error}</p>}
                  </>
                ) : step === 3 ? (
                  <>
                    <h2>Un'esperienza personalizzata!</h2>
                    <form key="step3">
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
                        <div style={{ display: 'flex', gap: '10px', justifyContent: 'space-between' }}>
                          <button type="button" className="form-button back-forward" onClick={handlePreviousQuestion}>Indietro</button>
                          <button type="button" className="form-button back-forward" onClick={handleNextQuestion}>Avanti</button>
                        </div>
                    </form>
                    {error && <p className="error-message">{error}</p>}
                  </>
                ) : step === 4 ? (
                  <>
                    <h2>Un'esperienza personalizzata!</h2>
                    <form key="step4">
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
                        <div style={{ display: 'flex', gap: '10px', justifyContent: 'space-between'}}>
                          <button type="button" className="form-button back-forward" onClick={handlePreviousQuestion}>Indietro</button>
                          <button type="button" className="form-button back-forward" onClick={handleNextQuestion}>Avanti</button>
                        </div>
                    </form>
                    {error && <p className="error-message">{error}</p>}
                  </>
                ) : (
                  <>
                    <h2>Un'esperienza personalizzata!</h2>
                    <form key="step5" onSubmit={handleQuestionarioSubmit}>
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
                              <img src="/uomo-giovane.png" alt="Uomo Giovane" className="trainer-image" />
                              <span className="trainer-box">Marco</span>
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
                              <img src="/donna-giovane.png" alt="Donna Giovane" className="trainer-image" />
                              <span className="trainer-box">Laura</span>
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
                              <img src="/uomo-adulto.png" alt="Uomo Adulto" className="trainer-image" />
                              <span className="trainer-box">Giuseppe</span>
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
                              <img src="/donna-adulta.png" alt="Donna Adulta" className="trainer-image" />
                              <span className="trainer-box">Maria</span>
                            </label>
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: '10px', justifyContent: 'space-between' }}>
                          <button type="button" className="form-button back-forward" onClick={handlePreviousQuestion}>Indietro</button>
                          <button type="submit" className="form-button">Completa registrazione</button>
                        </div>
                    </form>
                    {error && <p className="error-message">{error}</p>}
                  </>
                )}
            </div>
        </div>
    );
}

export default Register;