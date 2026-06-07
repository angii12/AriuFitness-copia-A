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
    const fetchUserColor = async () => {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        
        if (user) {
          const { data: profile, error } = await supabase
            .from('profili')
            .select('colore_ariu')
            .eq('id', user.id)
            .single();

          if (error) {
            console.error('Errore nel fetch del colore:', error);
            return;
          }

          if (profile && profile.colore_ariu) {
            const colore = coloriDisponibili[profile.colore_ariu] || coloriDisponibili.beige;
            setBackgroundColor(colore);
            document.documentElement.style.setProperty('--page-bg-color', colore);
          }
        }
      } catch (err) {
        console.error('Errore:', err);
      }
    };

    fetchUserColor();
  }, []);

  return (
    <ColorContext.Provider value={{ backgroundColor, coloriDisponibili, resetColor }}>
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
