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
  const [hidden, setHidden] = useState(false);
  const menuRef = useRef(null);
  const scrollStates = useRef(new Map());

  useEffect(() => {
    const onClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, []);

  useEffect(() => {
    const onScroll = (e) => {
      const target = e.target === document ? document.documentElement : e.target;
      const currentY = target.scrollTop;
      const lastY = scrollStates.current.get(target) ?? 0;
      if (currentY < 10) {
        setHidden(false);
      } else if (currentY > lastY && !open) {
        setHidden(true);
      } else if (currentY < lastY) {
        setHidden(false);
      }
      scrollStates.current.set(target, currentY);
    };
    document.addEventListener('scroll', onScroll, { capture: true, passive: true });
    return () => document.removeEventListener('scroll', onScroll, { capture: true });
  }, [open]);

  // chiudi il menu ad ogni cambio di pagina
  useEffect(() => { setOpen(false); }, [location.pathname]);

  const logout = () => {
    resetColor();
    localStorage.clear();
    navigate('/welcome');
  };

  if (hideHeader) return null;

  return (
    <header className={`global-header${hidden ? ' global-header--hidden' : ''}`}>
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
