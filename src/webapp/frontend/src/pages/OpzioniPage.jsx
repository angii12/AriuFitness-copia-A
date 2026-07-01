import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useColor } from '../context/ColorContext';
import { supabase } from '../SupabaseClient';
import './OpzioniPage.css';

const MODALITA = [
  {
    id: 'sovrapposizione',
    titolo: 'SOVRAPPOSIZIONE',
    descrizione:
      'Il tutorial viene mostrato in overlay semi-trasparente sulla webcam. Puoi seguire i movimenti reali mentre vedi la guida animata sopra di te.',
  },
  {
    id: 'diviso',
    titolo: 'SCHERMO DIVISO',
    descrizione:
      'Webcam e tutorial sono mostrati separatamente: la webcam in alto e il video tutorial qui sotto.',
  },
  {
    id: 'solo-tutorial',
    titolo: 'SOLO TUTORIAL',
    descrizione:
      'Viene mostrato solo il video tutorial. La telecamera rimane accesa in background per il riconoscimento IA, ma non è visibile.',
  },
];

function OpzioniPage() {
  const { backgroundColor } = useColor();
  const navigate = useNavigate();
  const [modalitaSelezionata, setModalitaSelezionata] = useState(
    () => localStorage.getItem('tutorialMode') || 'sovrapposizione'
  );
  const [ttsAbilitato, setTtsAbilitato] = useState(
    () => localStorage.getItem('ttsEnabled') !== 'false'
  );

  useEffect(() => {
    const syncFromDb = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      const { data: profilo } = await supabase
        .from('profili')
        .select('opzione_tutorial, opzione_tts')
        .eq('id', user.id)
        .single();
      if (profilo) {
        const mode = profilo.opzione_tutorial || 'sovrapposizione';
        const tts = profilo.opzione_tts !== false;
        setModalitaSelezionata(mode);
        setTtsAbilitato(tts);
        localStorage.setItem('tutorialMode', mode);
        localStorage.setItem('ttsEnabled', tts ? 'true' : 'false');
      }
    };
    syncFromDb();
  }, []);

  const handleSalva = async () => {
    localStorage.setItem('tutorialMode', modalitaSelezionata);
    localStorage.setItem('ttsEnabled', ttsAbilitato ? 'true' : 'false');
    const { data: { user } } = await supabase.auth.getUser();
    if (user) {
      await supabase
        .from('profili')
        .update({ opzione_tutorial: modalitaSelezionata, opzione_tts: ttsAbilitato })
        .eq('id', user.id);
    }
    navigate('/');
  };

  return (
    <div
      className="opzioni-container"
      style={{ '--colorvar': backgroundColor, backgroundColor }}
    >
      <div className="opzioni-wrapper">
        <h1 className="opzioni-heading">OPZIONI</h1>

        <section className="opzioni-section">
          <h2 className="opzioni-section-title">Visualizzazione Tutorial</h2>
          <p className="opzioni-section-desc">
            Scegli come vuoi vedere il video tutorial durante l'allenamento.
            Prima di ogni esercizio, la telecamera si attiverà sempre per la
            calibrazione, indipendentemente dalla modalità scelta.
          </p>

          <div className="opzioni-modalita-lista">
            {MODALITA.map((m) => (
              <div
                key={m.id}
                className={`opzioni-modalita-card ${
                  modalitaSelezionata === m.id
                    ? 'opzioni-modalita-card--attiva'
                    : ''
                }`}
                onClick={() => setModalitaSelezionata(m.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) =>
                  e.key === 'Enter' && setModalitaSelezionata(m.id)
                }
                aria-pressed={modalitaSelezionata === m.id}
              >
                <div className="opzioni-modalita-testo">
                  <h3>{m.titolo}</h3>
                  <p>{m.descrizione}</p>
                </div>
                <div
                  className={`opzioni-modalita-radio ${
                    modalitaSelezionata === m.id
                      ? 'opzioni-modalita-radio--selezionato'
                      : ''
                  }`}
                  aria-hidden="true"
                />
              </div>
            ))}
          </div>
        </section>

        <section className="opzioni-section">
          <h2 className="opzioni-section-title">Feedback Vocale</h2>
          <p className="opzioni-section-desc">
            Attiva o disattiva la sintesi vocale e il coach AI. Disattivando questa opzione
            vengono silenziati tutti i messaggi parlati e le chiamate al modello AI vengono
            sospese per migliorare le prestazioni.
          </p>
          <div
            className={`opzioni-modalita-card${ttsAbilitato ? ' opzioni-modalita-card--attiva' : ''}`}
            onClick={() => setTtsAbilitato((v) => !v)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && setTtsAbilitato((v) => !v)}
            aria-pressed={ttsAbilitato}
          >
            <div className="opzioni-modalita-testo">
              <h3>COMMENTI VOCALI E COACH AI</h3>
              <p>
                {ttsAbilitato
                  ? "Il sistema parla durante l'allenamento: descrive gli esercizi, fornisce correzioni posturali e incitamenti."
                  : 'Tutti i messaggi vocali sono silenziati. Il riconoscimento AI rimane attivo ma non genera feedback parlato.'}
              </p>
            </div>
            <div className={`opzioni-toggle-switch${ttsAbilitato ? ' opzioni-toggle-switch--on' : ''}`}>
              <div className="opzioni-toggle-thumb" />
            </div>
          </div>
        </section>

        <button className="opzioni-salva-btn" onClick={handleSalva}>
          Salva e Torna alla Home
        </button>
      </div>
    </div>
  );
}

export default OpzioniPage;
