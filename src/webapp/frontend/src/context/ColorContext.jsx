import React, { createContext, useContext, useState, useEffect } from 'react';
import { supabase } from '../SupabaseClient';

const ColorContext = createContext();

export const ColorProvider = ({ children }) => {
  const [backgroundColor, setBackgroundColor] = useState('#5B120F');

  // Mappa dei colori disponibili
  const coloriDisponibili = {
    beige: '#B5A281',
    verde: '#4B8C56',
    blu: '#2D69A0',
    nero: '#1B191A'
  };

  const defaultColor = '#5B120F';

  const resetColor = () => {
    setBackgroundColor(defaultColor);
    document.documentElement.style.setProperty('--page-bg-color', '#ffffff');
  };

  useEffect(() => {
    // Usa il colore tema predefinito PhysioVision #5B120F
    setBackgroundColor('#5B120F');
    document.documentElement.style.setProperty('--page-bg-color', '#ffffff');
  }, []);

  const updateColor = (coloreAriu) => {
    const colore = coloriDisponibili[coloreAriu] || defaultColor;
    setBackgroundColor(colore);
    document.documentElement.style.setProperty('--page-bg-color', colore);
  };

  return (
    <ColorContext.Provider value={{ backgroundColor, coloriDisponibili, resetColor, updateColor }}>
      {children}
    </ColorContext.Provider>
  );
};

export const useColor = () => {
  const context = useContext(ColorContext);
  if (!context) {
    throw new Error('useColor deve essere usato dentro ColorProvider');
  }
  return context;
};
