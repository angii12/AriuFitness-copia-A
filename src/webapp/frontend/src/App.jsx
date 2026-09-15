import React from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  useLocation,
} from 'react-router-dom';

import { ColorProvider } from './context/ColorContext';
import { PredictionProvider } from './context/PredictionContext';
import { AuthProvider } from './context/AuthContext';

import {
  ProtectedRoute,
  DoctorRoute,
  PatientRoute,
} from './components/ProtectedRoute';

import GlobalHeader from './components/GlobalHeader';

import HomePage from './pages/HomePage';
import ClassificationPage from './pages/ClassificationPage';
import ExerciseListPage from './pages/ExerciseListPage';

import LoginPage from './pages/Login';
import RegisterPage from './pages/Register';
import AuthCallback from './pages/AuthCallback';

import Profilo from './pages/Profilo';
import EserciziSalvatiPage from './pages/ChronologyPage';
import WelcomePage from './pages/WelcomePage';
import OpzioniPage from './pages/OpzioniPage';

import DoctorCreateExercisePage from './pages/DoctorCreateExercisePage';
import ExerciseLibraryPage from './pages/ExerciseLibraryPage';
import ExerciseRepsPage from './pages/ExerciseRepsPage';
import DoctorPatientsPage from './pages/DoctorPatientsPage';
import DoctorPatientDetailPage from './pages/DoctorPatientDetailPage';
import DoctorHomePage from './pages/DoctorHomePage';

import ConnectDoctorPage from './pages/ConnectDoctorPage';
import PatientDashboardPage from './pages/PatientDashboardPage';
import PatientSessionPage from './pages/PatientSessionPage';
import PatientHomePage from './pages/PatientHomePage';
import PatientDoctorsPage from './pages/PatientDoctorsPage';


function AppContent() {
  const location = useLocation();

  const isPublicRoute =
    location.pathname === '/' ||
    location.pathname === '/welcome' ||
    location.pathname === '/login' ||
    location.pathname === '/register' ||
    location.pathname === '/auth/callback';

  return (
    <>
      <GlobalHeader />

      <main
        className={
          isPublicRoute
            ? 'page-content page-content--public'
            : 'page-content page-content--private'
        }
      >
        <Routes>

          {/* =========================
              PAGINE PUBBLICHE
          ========================== */}

          <Route
            path="/"
            element={<WelcomePage />}
          />

          <Route
            path="/welcome"
            element={<WelcomePage />}
          />

          <Route
            path="/login"
            element={<LoginPage />}
          />

          <Route
            path="/register"
            element={<RegisterPage />}
          />

          <Route
            path="/auth/callback"
            element={<AuthCallback />}
          />


          {/* =========================
              ROTTE PROTETTE GENERICHE
          ========================== */}

          <Route
            path="/vecchia-home"
            element={
              <ProtectedRoute>
                <HomePage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/live-session"
            element={
              <ProtectedRoute>
                <ClassificationPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/allenamento"
            element={
              <ProtectedRoute>
                <ClassificationPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/visualizza-esercizi"
            element={
              <ProtectedRoute>
                <ExerciseListPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/profilo"
            element={
              <ProtectedRoute>
                <Profilo />
              </ProtectedRoute>
            }
          />

          <Route
            path="/cronologia"
            element={
              <ProtectedRoute>
                <EserciziSalvatiPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/opzioni"
            element={
              <ProtectedRoute>
                <OpzioniPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/collega-medico"
            element={
              <ProtectedRoute>
                <ConnectDoctorPage />
              </ProtectedRoute>
            }
          />


          {/* =========================
              AREA MEDICO
          ========================== */}

          <Route
            path="/medico"
            element={
              <DoctorRoute>
                <DoctorHomePage />
              </DoctorRoute>
            }
          />

          <Route
            path="/medico/crea-esercizio"
            element={
              <DoctorRoute>
                <DoctorCreateExercisePage />
              </DoctorRoute>
            }
          />

          <Route
            path="/medico/esercizi"
            element={
              <DoctorRoute>
                <ExerciseLibraryPage />
              </DoctorRoute>
            }
          />

          <Route
            path="/medico/esercizi/:exerciseId"
            element={
              <DoctorRoute>
                <ExerciseLibraryPage />
              </DoctorRoute>
            }
          />

          <Route
            path="/medico/esercizi/:exerciseId/reps"
            element={
              <DoctorRoute>
                <ExerciseRepsPage />
              </DoctorRoute>
            }
          />

          <Route
            path="/medico/pazienti"
            element={
              <DoctorRoute>
                <DoctorPatientsPage />
              </DoctorRoute>
            }
          />

          <Route
            path="/medico/pazienti/:patientId"
            element={
              <DoctorRoute>
                <DoctorPatientDetailPage />
              </DoctorRoute>
            }
          />


          <Route
            path="/medico/profilo"
            element={
              <DoctorRoute>
                <Profilo />
              </DoctorRoute>
            }
          />

          {/* =========================
              AREA PAZIENTE
          ========================== */}

          {/* Home paziente */}
          <Route
            path="/paziente"
            element={
              <PatientRoute>
                <PatientHomePage />
              </PatientRoute>
            }
          />

          {/* I miei esercizi — riusa PatientDashboardPage esistente */}
          <Route
            path="/paziente/esercizi"
            element={
              <PatientRoute>
                <PatientDashboardPage />
              </PatientRoute>
            }
          />

          {/* I miei medici */}
          <Route
            path="/paziente/medici"
            element={
              <PatientRoute>
                <PatientDoctorsPage />
              </PatientRoute>
            }
          />

          {/* Collega un medico */}
          <Route
            path="/paziente/collega-medico"
            element={
              <PatientRoute>
                <ConnectDoctorPage />
              </PatientRoute>
            }
          />

          {/* Profilo paziente */}
          <Route
            path="/paziente/profilo"
            element={
              <PatientRoute>
                <Profilo />
              </PatientRoute>
            }
          />

          {/* Alias legacy — mantenuti per retrocompatibilità */}
          <Route
            path="/piano-riabilitativo"
            element={
              <PatientRoute>
                <PatientDashboardPage />
              </PatientRoute>
            }
          />

          <Route
            path="/patient-session"
            element={
              <PatientRoute>
                <PatientSessionPage />
              </PatientRoute>
            }
          />

        </Routes>
      </main>
    </>
  );
}


function App() {
  return (
    <AuthProvider>
      <ColorProvider>
        <PredictionProvider>
          <Router>
            <AppContent />
          </Router>
        </PredictionProvider>
      </ColorProvider>
    </AuthProvider>
  );
}

export default App;