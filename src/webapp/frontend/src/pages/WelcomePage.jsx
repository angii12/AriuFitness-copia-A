import React from 'react';
import { Link } from 'react-router-dom';
import './WelcomePage.css';

const WelcomePage = () => (
  <div className="pv-landing">
    <div className="pv-landing-overlay"></div>

    <div className="pv-landing-content">
      <h1 className="pv-landing-title">
        <span className="pv-title-physio">Physio</span>
        <span className="pv-title-vision">Vision</span>
      </h1>

      <div className="pv-landing-text">
        <p className="pv-landing-desc">
          Riabilitazione assistita attraverso analisi del movimento e intelligenza artificiale.
        </p>

        <div className="pv-landing-ctas">
          <Link to="/login" className="pv-btn pv-btn-primary">
            Accedi
          </Link>

          <Link to="/register" className="pv-btn pv-btn-secondary">
            Registrati
          </Link>
        </div>
      </div>
    </div>
  </div>
);

export default WelcomePage;