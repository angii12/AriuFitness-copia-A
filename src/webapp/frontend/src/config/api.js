/**
 * Centralized API and WebSocket configuration for PhysioVision Frontend.
 */

// Base HTTP URL for the backend API
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Returns the WebSocket stream URL dynamically based on current host/protocol.
 * In local environment (localhost/127.0.0.1) connects directly to port 8000.
 * In production/remote uses relative host with wss:// or ws://.
 */
export const getWsStreamUrl = (path = '/ws/stream') => {
  const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  if (isLocal) {
    return `ws://${window.location.hostname}:8000${path}`;
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${path}`;
};
