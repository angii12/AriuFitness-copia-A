import React, { createContext, useContext, useEffect, useState } from 'react';
import { supabase } from '../SupabaseClient';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const [role, setRole] = useState(null);
  const [loading, setLoading] = useState(true);

  // Helper per recuperare il profilo da public.profili (Fonte Autorevole DB)
  const fetchProfile = async (currentUser) => {
    if (!currentUser) {
      setProfile(null);
      setRole(null);
      localStorage.removeItem('token');
      localStorage.removeItem('userRole');
      return null;
    }

    try {
      const { data, error } = await supabase
        .from('profili')
        .select('*')
        .eq('id', currentUser.id)
        .maybeSingle();

      if (error && error.code !== 'PGRST116') {
        console.error('Errore nel recupero del profilo Supabase:', error);
      }

      if (data) {
        setProfile(data);
        const userRole = data.ruolo; // ruoli consentiti nel DB: 'medico' o 'paziente'
        if (userRole === 'medico' || userRole === 'paziente') {
            setRole(userRole);
            localStorage.setItem('userRole', userRole);
        } else {
            setRole(null);
            localStorage.removeItem('userRole');
        }
        localStorage.setItem('token', currentUser.id);
        return data;
      } else {
        // Se il profilo non esiste su public.profili, impostiamo lo stato a incompleto/null
        // NON si auto-crea il profilo arbitrariamente e NON si eleva mai l'utente a medico.
        setProfile(null);
        setRole(null);
        localStorage.removeItem('userRole');
        return null;
      }
    } catch (e) {
      console.error('Eccezione durante la gestione del profilo:', e);
      setProfile(null);
      setRole(null);
    }
    return null;
  };

  useEffect(() => {
    let mounted = true;

    const initAuth = async () => {
      setLoading(true);
      try {
        const { data: { session }, error } = await supabase.auth.getSession();
        if (error) throw error;
        
        const currentUser = session?.user ?? null;
        if (mounted) {
          setUser(currentUser);
          if (currentUser) {
            await fetchProfile(currentUser);
          } else {
            setProfile(null);
            setRole(null);
            localStorage.removeItem('token');
            localStorage.removeItem('userRole');
          }
        }
      } catch (error) {
        console.error('Errore durante initAuth:', error);
        if (mounted) {
          setUser(null);
          setProfile(null);
          setRole(null);
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    initAuth();

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      const currentUser = session?.user || null;
      setUser(currentUser);
      if (currentUser) {
        // Non-blocking fetch
        setTimeout(() => {
          fetchProfile(currentUser);
        }, 0);
      } else {
        setProfile(null);
        setRole(null);
        localStorage.removeItem('token');
        localStorage.removeItem('userRole');
      }
      setLoading(false);
    });

    return () => {
      mounted = false;
      subscription?.unsubscribe();
    };
  }, []);

  const logout = async () => {
    setLoading(true);
    try {
      await supabase.auth.signOut();
    } finally {
      setUser(null);
      setProfile(null);
      setRole(null);
      localStorage.removeItem('token');
      localStorage.removeItem('userRole');
      setLoading(false);
    }
  };

  const refreshProfile = async (targetUser = user) => {
    if (!targetUser) return null;
    return await fetchProfile(targetUser);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        role,
        loading,
        logout,
        refreshProfile,
        isMedico: role === 'medico',
        isPaziente: role === 'paziente'
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth deve essere usato dentro AuthProvider');
  }
  return context;
};
