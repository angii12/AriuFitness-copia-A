import React, { useState, useEffect, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useColor } from '../context/ColorContext';
import './HomePage.css';
import { supabase } from '../SupabaseClient';

function HomePage() {
  const { backgroundColor } = useColor();
  
  // Stato per gestire quale card è aperta
  const [activeCardId, setActiveCardId] = useState(null);

  // --- STATO PER L'ETÀ DELL'UTENTE ---
  const [eta, setEta] = useState(null);
  const [loading, setLoading] = useState(true);

  const navigate = useNavigate();

  const programmi = [
    { 
      id: 1, 
      titolo: "TONIFICAZIONE", 
      immagine: "/tonificazione.png",
      allenamenti: ["Crunch con fitball dietro la schiena", "Plank con gomiti sulla fitball", "Plank con gomiti sulla fitball", "Russian Twist",
                   "Russian Twist (con piedi a terra)", "Dead bug", "Sollevamento gambe stringendo la fitball", "Hollow hold", "Fitball overhead roll-up",
                    "Fitball elevated leg crunches", "Squat contro il muro", "Affondi con piede posteriore sulla fitball", "Sumo squat", "Estesioni braccia e gambe",
                    "Addominali laterali", "Fitball push-up", "Medicine ball squat", "Wall sit con rotazione fitball"],
      descrizione: "18 esercizi - 1 ora di allenamento"
    },
    { 
      id: 2, 
      titolo: "DIMAGRIMENTO", 
      immagine: "/dimagrimento.png",
      allenamenti: [
        "Burpee con fitball", 
        "Stability ball mountain climbers", 
        "Medicine ball knee tucks", 
        "Medicine ball sit-up", 
        "Sit-up throw", 
        "Medicine chest press", 
        "Medicine ball-burpes (con push-up sulla spalla)", 
        "Medicine ball thrusters",  
        "Affondi con palla medica", 
        "Slam ball", 
        "Wall ball sit-ups", 
        "Affondo indietro con torsione disco", 
        "Estensione tricipiti sopra la testa", 
        "Ball toe taps"
      ],
      descrizione: "15 esercizi - 50 minuti di allenamento"
    },
    { 
      id: 3, 
      titolo: "FLESSIBILITÀ TOTALE E STRETCHING", 
      immagine: "/flessibilità-totale-e-stretching.png",
      allenamenti: [
        "Pelvic tilts", 
        "Fitball laterals shisfts", 
        "Medicine ball halos", 
        "Fitball back extensions", 
        "Kneeling stability stretch", 
        "Overhead ball side bends", 
        "Side lean with leg support", 
        "Arm raises on fitball", 
        "Swiss ball child pose", 
        "Allenamento dello psoas su fitball", 
        "Stretching pettorali con fitball", 
        "Mobilità bacino fitball"
      ],
      descrizione: "12 esercizi - 40 minuti di allenamento"
    },
    { 
      id: 4, 
      titolo: "SALUTE DELLE ARTICOLAZIONI", 
      immagine: "/salute-delle-articolazioni.png",
      allenamenti: [
        "Braccia con miniball", 
        "Lateral flexion con la fitball"
      ],
      descrizione: "2 esercizi - 15 minuti di allenamento"
    },
    { 
      id: 5, 
      titolo: "EQUILIBRIO E POSTURA", 
      immagine: "/equilibrio-e-postura.png",
      allenamenti: [
        "Roll out sulla fitball", 
        "Catcow con mani sulla fitball", 
        "Superman con fitball", 
        "Harmstring curls on fitball", 
        "Fitball lat stretch", 
        "Single leg balance reach", 
        "Physioball toe tap", 
        "Esercizio equilibrio complesso", 
        "Wall squats with a ball", 
        "Stability ball plank to pike", 
        "Inclinazioni laterali su fitball-seated"
      ],
      descrizione: "11 esercizi - 45 minuti di allenamento"
    }
  ];

  // --- RECUPERO ETÀ DA SUPABASE TRAMITE DATA DI NASCITA ---
  useEffect(() => {
    async function fetchUserAge() {
      try {
        // 1. Prendi l'utente loggato nella sessione attuale
        const { data: { user }, error: userError } = await supabase.auth.getUser();
        if (userError || !user) throw userError || new Error("Utente non autenticato");

        // 2. Recupera la colonna 'data_nascita' dalla tabella 'profiles'
        const { data, error } = await supabase
          .from('profili') 
          .select('data_nascita') // Assicurati che il nome della colonna sia identico a quello sul DB
          .eq('id', user.id)
          .single();

        if (error) throw error;
        
        if (data && data.data_nascita) {
          // --- CALCOLO DELL'ETÀ REALE ---
          const oggi = new Date();
          const compleanno = new Date(data.data_nascita);
          
          // Calcolo iniziale basato solo sulla differenza degli anni
          let etaCalcolata = oggi.getFullYear() - compleanno.getFullYear();
          
          // Sottraiamo un anno se l'utente non ha ancora festeggiato il compleanno nell'anno corrente
          const mese = oggi.getMonth() - compleanno.getMonth();
          if (mese < 0 || (mese === 0 && oggi.getDate() < compleanno.getDate())) {
            etaCalcolata--;
          }

          setEta(etaCalcolata);
        }
      } catch (error) {
        console.error("Errore nel recupero o calcolo dell'età:", error.message);
        // Fallback: se c'è un errore, per sicurezza impostiamo un'età standard (es. 30 anni)
        setEta(30); 
      } finally {
        setLoading(false);
      }
    }

    fetchUserAge();
  }, []);

  // --- LOGICA DI ORDINAMENTO DINAMICO ---
  const programmiOrdinati = useMemo(() => {
    // Definiamo la sequenza degli ID in base all'età
    // Se l'età è maggiore o uguale a 50 -> [4, 5, 3, 2, 1]
    // Se l'età è inferiore a 50 (o durante il caricamento) -> [1, 2, 3, 5, 4]
    const ordineIds = eta >= 50 ? [4, 5, 3, 2, 1] : [1, 2, 3, 5, 4];

    // Ordiniamo l'array originale basandoci sulla posizione dell'ID nell'array 'ordineIds'
    return [...programmi].sort((a, b) => {
      return ordineIds.indexOf(a.id) - ordineIds.indexOf(b.id);
    });
  }, [eta]); // Ricalcola l'ordine solo quando lo stato 'eta' cambia

  const toggleDrawer = (id) => {
    setActiveCardId(prevId => prevId === id ? null : id);
  };

  // --- FUNZIONE PER SALVARE GLI ESERCIZI NEL LOCAL STORAGE ---
  const handleStartWorkout = (allenamenti, titoloProgramma) => {
    try {
      // Salviamo l'array degli esercizi trasformandolo in stringa
      localStorage.setItem('allenamentiSelezionati', JSON.stringify(allenamenti));
      
      // Opzionale: puoi salvare anche il titolo del programma se ti serve nella pagina successiva
      localStorage.setItem('programmaAttivo', titoloProgramma);
      
      console.log(`Allenamento "${titoloProgramma}" avviato e salvato nel localStorage!`);

      navigate('/allenamento');
    } catch (error) {
      console.error("Errore nel salvataggio in localStorage:", error);
    }
  };

  return (
    <div className="home-container" style={{ backgroundColor }}>
      
      <div className="panels-grid">
        {programmiOrdinati.map((prog) => {
          const isOpen = activeCardId === prog.id;

          return (
            <div 
              key={prog.id} 
              className={`glass-panel ${isOpen ? 'panel-expanded' : ''}`}
              style={{'--bg-image': `url(${prog.immagine})`}}
            >
              {/* Contenitore superiore con titolo */}
              <div className="panel-main-content">
                <div className="panel-content">
                  <span className="panel-tag">WORKOUT</span>
                  <h2 className="panel-title">{prog.titolo}</h2>
                  <span className="panel-tag">{prog.descrizione}</span>
                </div>
              </div>

              {/* Bottone in fondo full-width */}
              <div className="bttn-container">
              <button 
                  className="panel-button"
                  onClick={() => handleStartWorkout(prog.allenamenti, prog.titolo)}
                >
                  Start
                </button>
              </div>
            </div>
          );
        })}
        <div className="glass-panel" style={{'--bg-image': `url(/personalizzato.png)`}}>
          <div className="panel-main-content">
            <div className="panel-content">
              <span className="panel-tag">ESERCIZI PERSONALIZZATI</span>
              <h2 className="panel-title">CREA IL TUO ALLENAMENTO</h2>
              <span className="panel-tag">Scegli tra oltre 60 esercizi e crea il tuo programma su misura</span>
            </div>
          </div>
          <div className="bttn-container">
            <button 
              className="panel-button"
              onClick={() => navigate('/visualizza-esercizi')}
              >
              Start
              </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default HomePage;