import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useColor } from '../context/ColorContext';
import './GlobalHeader.css';

const GlobalHeader = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { backgroundColor } = useColor();
  const isAuthenticated = localStorage.getItem('token') !== null;
  const hideHeader = location.pathname === '/login' || location.pathname === '/register' || location.pathname === '/welcome';
  const showAuthButtons = location.pathname !== '/login' && location.pathname !== '/register';

  const [user, setUser] = useState(null);
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);

  const DefaultAvatarSVG = (
    <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" className='avatar-image'>
      <circle cx="50" cy="50" r="50" fill="#ddd"/>
      <circle cx="50" cy="32" r="14" fill="#999"/>
      <ellipse cx="50" cy="70" rx="22" ry="18" fill="#999"/>
    </svg>
  );

  useEffect(() => {
    const cached = localStorage.getItem('user');
    if (cached) setUser(JSON.parse(cached));
  }, []);

  useEffect(() => {
    const onClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('click', onClick);
    return () => document.removeEventListener('click', onClick);
  }, []);

  

  const initials = (u) => {
    const name = (u?.nome || u?.first_name || u?.name || '').trim();
    const surname = (u?.cognome || u?.last_name || '').trim();
    const n = name?.[0] || '';
    const s = surname?.[0] || (n ? '' : (u?.email?.[0] || 'U'));
    return (n + s).toUpperCase();
  };
  
  const logout = () => {
    localStorage.clear();
    navigate('/welcome');
  };

  if (hideHeader) {
    return null;
  }

  return (
    <header className="global-header">
      <div className="brand-section">
        <span className="app-title-global" style={{ color: `color-mix(in srgb, ${backgroundColor}, #000000 35%)` }}>AriuFitness</span>
      </div>

      {isAuthenticated && (
        <div className="header-buttons">
          <Link to="/" className="back-button" style={{ backgroundColor:`color-mix(in srgb, ${backgroundColor}, #000000 35%)` }}>Home</Link>

          {localStorage.getItem('token') ? (
            <div className="profile-wrap" ref={menuRef}>
              <button
                aria-label="Apri menu profilo"
                className="avatar-btn"
                onClick={() => setOpen(v => !v)}
              >
                {user?.avatar_url ? <img src={user.avatar_url} alt="avatar" /> : DefaultAvatarSVG}
              </button>

              {open && (
                <div className="gh-menu" >
                  <div className="gh-user-row">
                    <div className="gh-avatar small">
                      {user?.avatar_url ? <img src={user.avatar_url} alt="avatar" /> : DefaultAvatarSVG}
                    </div>
                    <div className="gh-user-info" >
                      <div className="gh-name">Utente</div>
                      <div className="gh-email" style={{ color: `color-mix(in srgb, ${backgroundColor}, #000000 35%)` }}>{user?.email ?? '—'}</div>
                    </div>
                  </div>

                  <div className="gh-divider" style={{ backgroundColor: `color-mix(in srgb, ${backgroundColor}, #000000 35%)` }}/>

                  <Link to="/profilo" className="menu-btn" style={{ backgroundColor: `color-mix(in srgb, ${backgroundColor}, #000000 35%)` }} onClick={() => setOpen(false)}>
                    Profilo
                  </Link>
                  <button className="menu-btn danger" onClick={logout}>
                    Logout
                  </button>
                </div>
              )}

            </div>
          ) : null}
        </div>
      )}
    </header>
  );
};

export default GlobalHeader;