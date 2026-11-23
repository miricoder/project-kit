import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Me } from '@pankra/shared';
import { api } from './lib/client';

interface SessionState {
  me: Me | null;
  loading: boolean;
  refresh(): Promise<void>;
  signOut(): Promise<void>;
}

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    setLoading(true);
    try { setMe(await api.me()); } catch { setMe(null); } finally { setLoading(false); }
  }, []);
  const signOut = useCallback(async () => { await api.signOut(); setMe(null); }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  return <SessionContext.Provider value={{ me, loading, refresh, signOut }}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession outside SessionProvider');
  return ctx;
}
