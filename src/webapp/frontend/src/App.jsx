import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ColorProvider } from './context/ColorContext';
import GlobalHeader from './components/GlobalHeader'; // Importa il nuovo header
import FitnessClassifier from './components/FitnessClassifier';
import HomePage from './pages/HomePage';
import ClassificationPage from './pages/ClassificationPage';
import ExerciseListPage from './pages/ExerciseListPage';
import LoginPage from './pages/Login';
import RegisterPage from './pages/Register';
import Profilo from './pages/Profilo';
import ChronologyPage from './pages/ChronologyPage';
import WelcomePage from './pages/WelcomePage'; 
const isAuthenticated = () => localStorage.getItem('token') !== null;

const PrivateRoute = ({ children }) => {
  return isAuthenticated() ? children : <Navigate to="/welcome" />;
};

function App() {
  return (
    <ColorProvider>
      <Router>
        <GlobalHeader />

        {/* Un contenitore per il contenuto della pagina che evita di finire sotto l'header */}
        <main className="page-content">
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/welcome" element={<WelcomePage />} />
            <Route path="/" element={<PrivateRoute><HomePage /></PrivateRoute>} />
            <Route path="/live-session" element={<PrivateRoute><ClassificationPage /></PrivateRoute>} />
            <Route path="/allenamento" element={<PrivateRoute><ClassificationPage /></PrivateRoute>} />
            <Route path="/visualizza-esercizi" element={<PrivateRoute><ExerciseListPage /></PrivateRoute>} />
            <Route path="/profilo" element={<PrivateRoute><Profilo /></PrivateRoute>} />
            <Route path="/cronologia" element={<PrivateRoute><ChronologyPage /></PrivateRoute>} />
          </Routes>
        </main>
      </Router>
    </ColorProvider>
  );
}

export default App;