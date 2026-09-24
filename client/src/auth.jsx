import { createContext, useContext, useEffect, useState } from 'react';
import { api } from './api.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api('/me').then(setUser).catch(() => {}).finally(() => setLoading(false)); }, []);
  const login = async badgeId => { const u = await api('/login', { method: 'POST', body: { badgeId } }); setUser(u); };
  const logout = async () => { await api('/logout', { method: 'POST' }); setUser(null); };
  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
