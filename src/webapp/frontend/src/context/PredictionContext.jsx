import React, { createContext, useContext, useState } from 'react';

// Crea il Context
const PredictionContext = createContext();

// Crea il Provider
export const PredictionProvider = ({ children }) => {
  const [prediction, setPrediction] = useState({
    status: 'Inattivo',
    exercise: 'In attesa della webcam...',
    confidence: 0,
    frames_stacked: 0,
    reps: 0,
    phrase: 'Inquadrati per iniziare l\'esercizio.'
  });

  const value = {
    prediction,
    setPrediction
  };

  return (
    <PredictionContext.Provider value={value}>
      {children}
    </PredictionContext.Provider>
  );
};

// Hook personalizzato per usare il Context
export const usePrediction = () => {
  const context = useContext(PredictionContext);
  if (!context) {
    throw new Error('usePrediction deve essere usato all\'interno di PredictionProvider');
  }
  return context;
};
