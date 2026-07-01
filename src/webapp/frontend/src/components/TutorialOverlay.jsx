import React, { useState, useEffect } from 'react';
import { useColor } from '../context/ColorContext';
import './TutorialOverlay.css';

function TutorialOverlay({ steps, storageKey }) {
  const { backgroundColor } = useColor();
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!localStorage.getItem(storageKey)) {
      setVisible(true);
    }
  }, [storageKey]);

  const dismiss = () => {
    localStorage.setItem(storageKey, 'true');
    setVisible(false);
  };

  if (!visible) return null;

  const current = steps[step];
  const isFirst = step === 0;
  const isLast = step === steps.length - 1;

  return (
    <div className="tutorial-backdrop" style={{ '--colorvar': backgroundColor }}>
      <div className="tutorial-card">
        <div className="tutorial-icon">{current.icon}</div>

        <div className="tutorial-dots">
          {steps.map((_, i) => (
            <span
              key={i}
              className={`tutorial-dot${i === step ? ' tutorial-dot--active' : ''}`}
            />
          ))}
        </div>

        <h2 className="tutorial-title">{current.title}</h2>
        <p className="tutorial-desc">{current.desc}</p>

        <div className="tutorial-actions">
          {!isFirst && (
            <button className="tutorial-btn-secondary" onClick={() => setStep(s => s - 1)}>
              ← Indietro
            </button>
          )}
          {!isLast ? (
            <button className="tutorial-btn-primary" onClick={() => setStep(s => s + 1)}>
              Avanti →
            </button>
          ) : (
            <button className="tutorial-btn-primary" onClick={dismiss}>
              Inizia!
            </button>
          )}
          <button className="tutorial-btn-skip" onClick={dismiss}>
            Salta
          </button>
        </div>
      </div>
    </div>
  );
}

export default TutorialOverlay;
