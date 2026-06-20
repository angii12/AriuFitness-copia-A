import React, { useEffect, useRef, useState } from 'react';

const FitnessClassifier = () => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);
  const intervalRef = useRef(null);

  const [serverStatus, setServerStatus] = useState({ text: 'Disconnesso', color: '#dc3545' });
  const [prediction, setPrediction] = useState({
    status: 'Inattivo',
    exercise: 'In attesa della webcam...',
    confidence: 0,
    frames_stacked: 0
  });

  useEffect(() => {
    wsRef.current = new WebSocket('ws://localhost:8000/ws/stream');

    wsRef.current.onopen = () => {
      setServerStatus({ text: 'Rete AI Attiva ⚡', color: '#28a745' });
      startWebcam();
    };

    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setPrediction(data);
    };

    wsRef.current.onclose = () => {
      setServerStatus({ text: 'Disconnesso ❌', color: '#dc3545' });
      stopStreaming();
    };

    wsRef.current.onerror = () => {
      setServerStatus({ text: 'Errore Connessione Back-end ⚠️', color: '#ffc107' });
      stopStreaming();
    };

    return () => {
      stopStreaming();
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const startWebcam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, frameRate: { ideal: 15 } }
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => startStreaming();
      }
    } catch (err) {
      console.error("Errore webcam:", err);
      setServerStatus({ text: 'Webcam non trovata 📷', color: '#dc3545' });
    }
  };

  const startStreaming = () => {
    intervalRef.current = setInterval(() => {
      if (!videoRef.current || !canvasRef.current || !wsRef.current) return;
      if (wsRef.current.readyState !== WebSocket.OPEN) return;

      const video = videoRef.current;
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');

      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.5); // Qualità bilanciata a 0.5 per alleggerire il carico di rete

      wsRef.current.send(JSON.stringify({ image: dataUrl }));
    }, 130);
  };

  const stopStreaming = () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (videoRef.current && videoRef.current.srcObject) {
      const tracks = videoRef.current.srcObject.getTracks();
      tracks.forEach(track => track.stop());
    }
  };

  // Funzione di utilità per formattare i nomi delle cartelle in testo leggibile
  const formatExerciseName = (name) => {
    if (!name || name === 'Nessuno' || name.includes('attesa')) return name;
    return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  };

  // Determina il colore del box in base alla confidenza dell'algoritmo
  const getConfidenceColor = (conf) => {
    if (conf > 80) return '#28a745'; // Verde: Sicuro
    if (conf > 50) return '#ffc107'; // Giallo: Incerto
    return '#6c757d'; // Grigio: Nessun dato affidabile
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '20px', width: '100%' }}>
      
      {/* Badge dello Stato del Server */}
      <div style={{
        padding: '8px 16px',
        borderRadius: '20px',
        backgroundColor: serverStatus.color,
        color: '#fff',
        fontWeight: 'bold',
        fontSize: '14px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
      }}>
        {serverStatus.text}
      </div>

      <div style={{ 
        display: 'flex', 
        flexWrap: 'wrap', 
        justifyContent: 'center', 
        gap: '30px', 
        width: '100%', 
        maxWidth: '1100px' 
      }}>
        
        {/* Box Webcam */}
        <div style={{ position: 'relative', borderRadius: '12px', overflow: 'hidden', boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}>
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            style={{ width: '100%', maxWidth: '640px', height: 'auto', display: 'block', transform: 'scaleX(-1)' }} // Effetto specchio per l'utente
          />
          <canvas ref={canvasRef} width="640" height="480" style={{ display: 'none' }} />
        </div>

        {/* Pannello Dati e Predizioni */}
        <div style={{
          flex: '1',
          minWidth: '320px',
          maxWidth: '400px',
          backgroundColor: '#fff',
          borderRadius: '12px',
          padding: '24px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between'
        }}>
          <div>
            <h4 style={{ margin: '0 0 16px 0', color: '#495057', textTransform: 'uppercase', fontSize: '12px', letterSpacing: '1px' }}>
              Analisi Movimento AI
            </h4>
            
            <div style={{ marginBottom: '24px' }}>
              <span style={{ fontSize: '14px', color: '#6c757d' }}>Esercizio Corrente</span>
              <h2 style={{ margin: '4px 0 0 0', color: '#212529', fontSize: '26px', fontWeight: '700' }}>
                {formatExerciseName(prediction.exercise)}
              </h2>
            </div>

            {/* Visualizzazione Avanzamento Buffer o Confidenza */}
            {prediction.status === 'buffering' ? (
              <div>
                <span style={{ fontSize: '14px', color: '#6c757d' }}>Inizializzazione Finestra Temporale...</span>
                <div style={{ width: '100%', backgroundColor: '#e9ecef', borderRadius: '8px', height: '12px', marginTop: '8px', overflow: 'hidden' }}>
                  <div style={{ 
                    width: `${(prediction.frames_stacked / 8) * 100}%`, 
                    backgroundColor: '#ff9800', 
                    height: '100%', 
                    transition: 'width 0.1s ease-in-out' 
                  }} />
                </div>
                <span style={{ fontSize: '12px', color: '#999', display: 'block', marginTop: '4px' }}>
                  Catturati {prediction.frames_stacked} di 8 fotogrammi chiave
                </span>
              </div>
            ) : (
              <div>
                <span style={{ fontSize: '14px', color: '#6c757d' }}>Indice di Affidabilità</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '4px' }}>
                  <span style={{ 
                    fontSize: '36px', 
                    fontWeight: '800', 
                    color: getConfidenceColor(prediction.confidence) 
                  }}>
                    {prediction.confidence}%
                  </span>
                </div>
                
                {/* Barra della Confidenza */}
                <div style={{ width: '100%', backgroundColor: '#e9ecef', borderRadius: '8px', height: '8px', marginTop: '8px', overflow: 'hidden' }}>
                  <div style={{ 
                    width: `${prediction.confidence}%`, 
                    backgroundColor: getConfidenceColor(prediction.confidence), 
                    height: '100%', 
                    transition: 'width 0.2s ease' 
                  }} />
                </div>
              </div>
            )}
          </div>

        </div>

      </div>
    </div>
  );
};

export default FitnessClassifier;