import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
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

  const programmi = [
    { 
      id: 1, 
      titolo: "TONIFICAZIONE", 
      immagine: "/tonificazione.png",
      allenamenti: ["Full Body Tonificazione", "Focus Addome & Glutei", "Upper Body Sculpt", "Placeholder", "Placeholder", "Placeholder", "Placeholder"]
    },
    { 
      id: 2, 
      titolo: "DIMAGRIMENTO", 
      immagine: "/dimagrimento.png",
      allenamenti: ["Cardio HIIT", "Brucia Grassi Intenso", "Circuit Training"]
    },
    { 
      id: 3, 
      titolo: "FLESSIBILITÀ TOTALE E STRETCHING", 
      immagine: "/flessibilità-totale-e-stretching.png",
      allenamenti: ["Stretching Mattutino", "Mobilità Articolare", "Yoga Flex", "Placeholder", "Placeholder", "Placeholder"]
    },
    { 
      id: 4, 
      titolo: "SALUTE DELLE ARTICOLAZIONI", 
      immagine: "/salute-delle-articolazioni.png",
      allenamenti: ["Rinforzo Ginocchia", "Posturale Schiena", "Mobilità Spalle", "Placeholder", "Placeholder", "Placeholder"]
    },
    { 
      id: 5, 
      titolo: "EQUILIBRIO E POSTURA", 
      immagine: "/equilibrio-e-postura.png",
      allenamenti: ["Core & Balance", "Stabilità Caviglie", "Riallineamento Posturale", "Placeholder", "Placeholder", "Placeholder"]
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

  return (
    <div className="home-container" style={{ backgroundColor, backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40' viewBox='0 0 40 40'%3E%3Cg fill-rule='evenodd'%3E%3Cg fill='%23CCCCCC' fill-opacity='0.1'%3E%3Cpath d='M0 38.59l2.83-2.83 1.41 1.41L1.41 40H0v-1.41zM0 1.4l2.83 2.83 1.41-1.41L1.41 0H0v1.41zM38.59 40l-2.83-2.83 1.41-1.41L40 38.59V40h-1.41zM40 1.41l-2.83 2.83-1.41-1.41L38.59 0H40v1.41zM20 18.6l2.83-2.83 1.41 1.41L21.41 20l2.83 2.83-1.41 1.41L20 21.41l-2.83 2.83-1.41-1.41L18.59 20l-2.83-2.83 1.41-1.41L20 18.59z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")` }}>
      
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
                </div>
              </div>

              {/* Il Cassetto con lista esercizi */}
              <div className="panel-drawer">
                <div className="drawer-list">
                  <ul className="workout-list">
                    {prog.allenamenti.map((allenamento, index) => (
                      <li key={index} className="workout-item">
                        {allenamento}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Bottone in fondo full-width */}
              <button 
                className={`panel-button ${isOpen ? 'active' : ''}`}
                onClick={() => toggleDrawer(prog.id)}
              >
                {isOpen ? 'Chiudi' : 'View'}
              </button>

            </div>
          );
        })}
      </div>
    </div>
  );
}

export default HomePage;