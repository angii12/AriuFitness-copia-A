import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useColor } from '../context/ColorContext';
import './GlobalHeader.css';

const NAV_ITEMS = [
  { label: 'Homepage',      to: '/' },
  { label: 'I miei piani',  to: '/cronologia' },
  { label: 'Profilo',        to: '/profilo' },
  { label: 'Impostazioni',  to: '/opzioni' },
];

const GlobalHeader = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { resetColor } = useColor();
  const isAuthenticated = localStorage.getItem('token') !== null;
  const hideHeader =
    location.pathname === '/login' ||
    location.pathname === '/register' ||
    location.pathname === '/welcome';

  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    const onClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, []);

  // chiudi il menu ad ogni cambio di pagina
  useEffect(() => { setOpen(false); }, [location.pathname]);

  const logout = () => {
    resetColor();
    localStorage.clear();
    navigate('/welcome');
  };

  if (hideHeader) return null;

  return (
    <header className="global-header">
      <div className="brand-section">
        <span className="app-title-global">Ariu</span>
        <span className="app-title-global second">Fitness</span>
      </div>

      {isAuthenticated && (
        <div className="nav-wrap" ref={menuRef}>
          <button
            className="hamburger-btn"
            onClick={() => setOpen(v => !v)}
            aria-label="Apri menu navigazione"
          >
            {open ? '✕' : '☰'}
          </button>

          {open && (
            <nav className="hamburger-menu">
              {NAV_ITEMS.map(({ label, to }) => (
                <Link
                  key={to}
                  to={to}
                  className="hm-item"
                  onClick={() => setOpen(false)}
                >
                  <span>{label}</span>
                </Link>
              ))}

              <button className="hm-item hm-logout" onClick={logout}>
                <span>Logout</span>
              </button>
            </nav>
          )}
        </div>
      )}
    </header>
  );
};

export default GlobalHeader;
