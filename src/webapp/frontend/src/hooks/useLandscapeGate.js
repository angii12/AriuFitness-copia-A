import { useState, useEffect } from 'react';

function isTouchDevice() {
  return navigator.maxTouchPoints > 0 || window.matchMedia('(pointer: coarse)').matches;
}

function isPortraitNow() {
  if (screen.orientation?.type) {
    return screen.orientation.type.startsWith('portrait');
  }
  return window.matchMedia('(orientation: portrait)').matches;
}

// Restituisce { isBlocked, isMobileLandscape }
// isBlocked: mobile + portrait → mostra overlay "ruota il telefono"
// isMobileLandscape: mobile + landscape → attiva layout a 2/3 colonne
export function useLandscapeGate() {
  const [state, setState] = useState(() => {
    const mobile = isTouchDevice();
    const portrait = isPortraitNow();
    return { isBlocked: mobile && portrait, isMobileLandscape: mobile && !portrait };
  });

  useEffect(() => {
    if (!isTouchDevice()) return; // desktop: mai attivo

    const update = () => {
      const portrait = isPortraitNow();
      setState({ isBlocked: portrait, isMobileLandscape: !portrait });
    };

    if (screen.orientation) {
      screen.orientation.addEventListener('change', update);
      return () => screen.orientation.removeEventListener('change', update);
    }
    // Fallback per Safari iOS senza screen.orientation
    window.addEventListener('orientationchange', update);
    window.addEventListener('resize', update);
    return () => {
      window.removeEventListener('orientationchange', update);
      window.removeEventListener('resize', update);
    };
  }, []);

  return state;
}
