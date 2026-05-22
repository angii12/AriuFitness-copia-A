import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useColor } from '../context/ColorContext';
import './HomePage.css';
import { supabase } from '../SupabaseClient';

function HomePage() {
  const { backgroundColor } = useColor();
  // Array con i dati dei 5 panel richiesti
  const programmi = [
    { id: 1, titolo: "TONIFICAZIONE", immagine: "/tonificazione.png" },
    { id: 2, titolo: "DIMAGRIMENTO", immagine: "/dimagrimento.png" },
    { id: 3, titolo: "FLESSIBILITÀ TOTALE E STRETCHING", immagine: "/flessibilità-totale-e-stretching.png" },
    { id: 4, titolo: "SALUTE DELLE ARTICOLAZIONI", immagine: "/salute-delle-articolazioni.png" },
    { id: 5, titolo: "EQUILIBRIO E POSTURA", immagine: "/equilibrio-e-postura.png" }
  ];

  return (
    <div className="home-container" style={{ backgroundColor, backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40' viewBox='0 0 40 40'%3E%3Cg fill-rule='evenodd'%3E%3Cg fill='%23CCCCCC' fill-opacity='0.1'%3E%3Cpath d='M0 38.59l2.83-2.83 1.41 1.41L1.41 40H0v-1.41zM0 1.4l2.83 2.83 1.41-1.41L1.41 0H0v1.41zM38.59 40l-2.83-2.83 1.41-1.41L40 38.59V40h-1.41zM40 1.41l-2.83 2.83-1.41-1.41L38.59 0H40v1.41zM20 18.6l2.83-2.83 1.41 1.41L21.41 20l2.83 2.83-1.41 1.41L20 21.41l-2.83 2.83-1.41-1.41L18.59 20l-2.83-2.83 1.41-1.41L20 18.59z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")` }}>
      

      <div className="panels-grid">
        {programmi.map((prog) => (
          <div 
            key={prog.id} 
            className="glass-panel"
            style={{'--bg-image': `url(${prog.immagine})`}}
          >
            <div className="panel-content">
              <span className="panel-tag">WORKOUT</span>
              <h2 className="panel-title">{prog.titolo}</h2>
            </div>
            
            {/* Pulsante segnaposto come richiesto */}
            <Link to="#" className="panel-button">
              View
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}

export default HomePage;