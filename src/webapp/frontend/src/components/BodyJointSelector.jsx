import React from 'react';
import './BodyJointSelector.css';

export const ALL_JOINTS = [
  { id: 'left_shoulder', label: 'Spalla Sinistra', category: 'upper', x: 130, y: 120 },
  { id: 'right_shoulder', label: 'Spalla Destra', category: 'upper', x: 270, y: 120 },
  { id: 'left_elbow', label: 'Gomito Sinistro', category: 'upper', x: 95, y: 200 },
  { id: 'right_elbow', label: 'Gomito Destro', category: 'upper', x: 305, y: 200 },
  { id: 'left_hip', label: 'Anca Sinistra', category: 'lower', x: 155, y: 260 },
  { id: 'right_hip', label: 'Anca Destra', category: 'lower', x: 245, y: 260 },
  { id: 'left_knee', label: 'Ginocchio Sinistro', category: 'lower', x: 145, y: 370 },
  { id: 'right_knee', label: 'Ginocchio Destro', category: 'lower', x: 255, y: 370 },
];

const BodyJointSelector = ({ selectedJoints = [], onJointToggle, disabled = false }) => {
  const isSelected = (jointId) => selectedJoints.includes(jointId);

  const toggleJoint = (jointId) => {
    if (disabled) return;
    if (isSelected(jointId)) {
      onJointToggle(selectedJoints.filter(j => j !== jointId));
    } else {
      onJointToggle([...selectedJoints, jointId]);
    }
  };

  const selectAll = () => {
    if (disabled) return;
    onJointToggle(ALL_JOINTS.map(j => j.id));
  };

  const clearAll = () => {
    if (disabled) return;
    onJointToggle([]);
  };

  const selectCategory = (category) => {
    if (disabled) return;
    const catJoints = ALL_JOINTS.filter(j => j.category === category).map(j => j.id);
    const otherJoints = selectedJoints.filter(id => {
      const j = ALL_JOINTS.find(item => item.id === id);
      return j && j.category !== category;
    });
    onJointToggle([...otherJoints, ...catJoints]);
  };

  return (
    <div className={`body-joint-selector-container ${disabled ? 'disabled' : ''}`}>
      <div className="joint-selector-header">
        <span className="selector-title">Seleziona Articolazioni Cliniche</span>
        <span className="selector-subtitle">
          Clicca sulle articolazioni sul corpo umano per guidare la segmentazione post-hoc
        </span>
      </div>

      <div className="selector-presets">
        <button type="button" className="preset-btn" onClick={selectAll} disabled={disabled}>
          ✓ Seleziona Tutte (8)
        </button>
        <button type="button" className="preset-btn" onClick={() => selectCategory('upper')} disabled={disabled}>
          💪 Arti Superiori
        </button>
        <button type="button" className="preset-btn" onClick={() => selectCategory('lower')} disabled={disabled}>
          🦵 Arti Inferiori
        </button>
        <button type="button" className="preset-btn reset" onClick={clearAll} disabled={disabled}>
          ✕ Pulisci
        </button>
      </div>

      <div className="mannequin-wrapper">
        <svg viewBox="0 0 400 520" className="mannequin-svg" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <filter id="glow-red" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            <linearGradient id="body-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#2c3e50" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#1a252f" stopOpacity="0.95" />
            </linearGradient>
          </defs>

          {/* Testa */}
          <circle cx="200" cy="50" r="26" fill="url(#body-gradient)" stroke="#4a6572" strokeWidth="2.5" />
          
          {/* Collo */}
          <line x1="200" y1="76" x2="200" y2="100" stroke="#4a6572" strokeWidth="6" strokeLinecap="round" />

          {/* Torace & Spalle */}
          <path d="M 130 120 L 270 120 L 245 260 L 155 260 Z" fill="url(#body-gradient)" stroke="#4a6572" strokeWidth="2.5" />
          
          {/* Linea Spina Dorsale */}
          <line x1="200" y1="100" x2="200" y2="260" stroke="#34495e" strokeWidth="3" strokeDasharray="4 4" />

          {/* Braccia (Ossa) */}
          <line x1="130" y1="120" x2="95" y2="200" stroke="#4a6572" strokeWidth="8" strokeLinecap="round" />
          <line x1="95" y1="200" x2="65" y2="280" stroke="#4a6572" strokeWidth="6" strokeLinecap="round" />

          <line x1="270" y1="120" x2="305" y2="200" stroke="#4a6572" strokeWidth="8" strokeLinecap="round" />
          <line x1="305" y1="200" x2="335" y2="280" stroke="#4a6572" strokeWidth="6" strokeLinecap="round" />

          {/* Polsi / Mani decorative */}
          <circle cx="65" cy="280" r="7" fill="#34495e" />
          <circle cx="335" cy="280" r="7" fill="#34495e" />

          {/* Bacino */}
          <path d="M 155 260 L 245 260 L 230 290 L 170 290 Z" fill="#243342" stroke="#4a6572" strokeWidth="2" />

          {/* Gambe (Ossa) */}
          <line x1="155" y1="260" x2="145" y2="370" stroke="#4a6572" strokeWidth="9" strokeLinecap="round" />
          <line x1="145" y1="370" x2="135" y2="470" stroke="#4a6572" strokeWidth="7" strokeLinecap="round" />

          <line x1="245" y1="260" x2="255" y2="370" stroke="#4a6572" strokeWidth="9" strokeLinecap="round" />
          <line x1="255" y1="370" x2="265" y2="470" stroke="#4a6572" strokeWidth="7" strokeLinecap="round" />

          {/* Caviglie / Piedi decorativi */}
          <ellipse cx="130" cy="475" rx="12" ry="6" fill="#34495e" />
          <ellipse cx="270" cy="475" rx="12" ry="6" fill="#34495e" />

          {/* NODI ARTICOLARI CLICCABILI */}
          {ALL_JOINTS.map((joint) => {
            const active = isSelected(joint.id);
            return (
              <g
                key={joint.id}
                className={`joint-node ${active ? 'active' : ''}`}
                onClick={() => toggleJoint(joint.id)}
              >
                {/* Anello esterno pulsante se selezionato */}
                {active && (
                  <circle
                    cx={joint.x}
                    cy={joint.y}
                    r="20"
                    className="pulse-ring"
                  />
                )}

                {/* Cerchio base nodo */}
                <circle
                  cx={joint.x}
                  cy={joint.y}
                  r="14"
                  className="joint-circle-bg"
                />
                
                <circle
                  cx={joint.x}
                  cy={joint.y}
                  r="9"
                  className="joint-circle-inner"
                />

                {/* Etichetta Testo affiancata */}
                <text
                  x={joint.x > 200 ? joint.x + 22 : joint.x - 22}
                  y={joint.y + 4}
                  textAnchor={joint.x > 200 ? 'start' : 'end'}
                  className="joint-label-text"
                >
                  {joint.label.replace(' Sinistra', ' Sx').replace(' Destra', ' Dx')}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="selected-summary-badge">
        <strong>Articolazioni Selezionate ({selectedJoints.length}/8):</strong>
        {selectedJoints.length === 0 ? (
          <span className="summary-empty"> Nessuna articolazione selezionata (selezionane almeno una per DOCTOR_GUIDED)</span>
        ) : (
          <div className="joint-chips-list">
            {selectedJoints.map(id => {
              const item = ALL_JOINTS.find(j => j.id === id);
              return (
                <span key={id} className="joint-chip">
                  {item ? item.label : id}
                  <button type="button" onClick={() => toggleJoint(id)}>✕</button>
                </span>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default BodyJointSelector;
