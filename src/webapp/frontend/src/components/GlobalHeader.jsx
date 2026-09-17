import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useColor } from '../context/ColorContext';
import { useAuth } from '../context/AuthContext';
import './GlobalHeader.css';

const GlobalHeader = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const { resetColor } = useColor();
  const { user, role, logout: authLogout } = useAuth();

  const isAuthenticated = !!user;
  const userRole = role || 'paziente';

  const isPublicRoute =
    location.pathname === '/' ||
    location.pathname === '/login' ||
    location.pathname === '/register' ||
    location.pathname === '/welcome' ||
    location.pathname === '/auth/callback';

  const [open, setOpen] = useState(false);
  const [hidden, setHidden] = useState(false);

  const menuRef = useRef(null);
  const scrollStates = useRef(new Map());

  const doctorNavItems = [
    {
      label: '🏠 Home',
      to: '/medico',
    },
    {
      label: '👥 I Miei Pazienti',
      to: '/medico/pazienti',
    },
    {
      label: '➕ Crea Esercizio',
      to: '/medico/crea-esercizio',
    },
    {
      label: '📋 Elenco Esercizi',
      to: '/medico/esercizi',
    },
    {
      label: '👤 Profilo',
      to: '/medico/profilo',
    },
  ];

  const patientNavItems = [
    {
      label: '🏠 Home',
      to: '/paziente',
    },
    {
      label: '📋 I miei esercizi',
      to: '/paziente/esercizi',
    },
    {
      label: '👨‍⚕️ I miei medici',
      to: '/paziente/medici',
    },
    {
      label: '👤 Profilo',
      to: '/paziente/profilo',
    },
  ];

  const navItems =
    userRole === 'medico'
      ? doctorNavItems
      : patientNavItems;

  useEffect(() => {
    const onClick = (e) => {
      if (
        menuRef.current &&
        !menuRef.current.contains(e.target)
      ) {
        setOpen(false);
      }
    };

    document.addEventListener('click', onClick);

    return () => {
      document.removeEventListener('click', onClick);
    };
  }, []);

  useEffect(() => {
    const onScroll = (e) => {
      const target =
        e.target === document
          ? document.documentElement
          : e.target;

      const currentY = target.scrollTop;

      const lastY =
        scrollStates.current.get(target) ?? 0;

      if (currentY < 10) {
        setHidden(false);
      } else if (currentY > lastY && !open) {
        setHidden(true);
      } else if (currentY < lastY) {
        setHidden(false);
      }

      scrollStates.current.set(
        target,
        currentY
      );
    };

    document.addEventListener(
      'scroll',
      onScroll,
      {
        capture: true,
        passive: true,
      }
    );

    return () => {
      document.removeEventListener(
        'scroll',
        onScroll,
        {
          capture: true,
        }
      );
    };
  }, [open]);

  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  const handleLogout = async () => {
    resetColor();

    await authLogout();

    navigate('/');
  };

  /*
    IMPORTANTE:
    sulle pagine pubbliche NON viene renderizzato
    alcun header e non deve occupare spazio.
  */
  if (isPublicRoute) {
    return null;
  }

  return (
    <header
      className={`global-header${hidden ? ' global-header--hidden' : ''
        }`}
    >
      <div
        className="brand-section"
        onClick={() =>
          navigate(
            userRole === 'medico'
              ? '/medico'
              : '/paziente'
          )
        }
        style={{ cursor: 'pointer' }}
      >
        <span className="app-title-global">
          Physio
        </span>

        <span className="app-title-global second">
          Vision
        </span>
      </div>

      <div
        className="nav-wrap"
        ref={menuRef}
      >
        <button
          className="hamburger-btn"
          onClick={() =>
            setOpen((value) => !value)
          }
          aria-label="Apri menu navigazione"
        >
          {open ? '✕' : '☰'}
        </button>

        {open && (
          <nav className="hamburger-menu">
            <div
              className="user-role-header-tag"
              style={{
                padding: '8px 14px 10px',
                fontSize: '0.72rem',
                fontWeight: 700,
                letterSpacing: '0.06em',
                color: 'var(--pv-sage-dark, #4d7c5f)',
                borderBottom: '1.5px solid rgba(122, 171, 138, 0.2)',
                marginBottom: '6px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <span>RUOLO:</span>
              <span style={{
                background: 'rgba(122, 171, 138, 0.2)',
                color: 'var(--pv-sage-deep, #274433)',
                padding: '2px 8px',
                borderRadius: '6px',
                fontSize: '0.7rem',
              }}>
                {userRole.toUpperCase()}
              </span>
            </div>

            {navItems.map(
              ({ label, to }, index) => {
                const isActive = location.pathname === to || (to !== '/medico' && to !== '/paziente' && location.pathname.startsWith(to));
                return (
                  <Link
                    key={`${to}_${index}`}
                    to={to}
                    className={`hm-item${isActive ? ' hm-item--active' : ''}`}
                    onClick={() =>
                      setOpen(false)
                    }
                  >
                    <span>{label}</span>
                  </Link>
                );
              }
            )}

            <button
              className="hm-item hm-logout"
              onClick={handleLogout}
            >
              <span>🚪 Logout</span>
            </button>
          </nav>
        )}
      </div>
    </header>
  );
};

export default GlobalHeader;