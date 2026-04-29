import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { getMe, login as apiLogin, refreshToken, type User } from "@/services/api";

const ACCESS_KEY = "segupak_access";
const REFRESH_KEY = "segupak_refresh";

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
}

interface AuthContextValue extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadUser = useCallback(
    async (access: string, signal?: AbortSignal, isStale?: () => boolean) => {
      const fetchInit = signal ? { signal } : undefined;
      const stale = () => isStale?.() ?? false;
      try {
        const me = await getMe(access, fetchInit);
        if (stale()) return;
        setUser(me);
      } catch {
        if (signal?.aborted) {
          localStorage.removeItem(ACCESS_KEY);
          localStorage.removeItem(REFRESH_KEY);
          if (!stale()) setUser(null);
          return;
        }
        const stored = localStorage.getItem(REFRESH_KEY);
        if (stored) {
          try {
            const { access: newAccess } = await refreshToken(stored, fetchInit);
            if (stale()) return;
            localStorage.setItem(ACCESS_KEY, newAccess);
            const me = await getMe(newAccess, fetchInit);
            if (stale()) return;
            setUser(me);
          } catch {
            if (signal?.aborted) {
              localStorage.removeItem(ACCESS_KEY);
              localStorage.removeItem(REFRESH_KEY);
              if (!stale()) setUser(null);
              return;
            }
            localStorage.removeItem(ACCESS_KEY);
            localStorage.removeItem(REFRESH_KEY);
            if (!stale()) setUser(null);
          }
        } else {
          if (!stale()) setUser(null);
        }
      }
    },
    [],
  );

  useEffect(() => {
    let stale = false;
    const access = localStorage.getItem(ACCESS_KEY);
    if (!access) {
      setLoading(false);
      return () => {
        stale = true;
      };
    }
    const controller = new AbortController();
    const timeoutMs = 15_000;
    const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
    loadUser(access, controller.signal, () => stale).finally(() => {
      window.clearTimeout(timeoutId);
      if (!stale) setLoading(false);
    });
    return () => {
      stale = true;
      window.clearTimeout(timeoutId);
    };
  }, [loadUser]);

  const login = useCallback(
    async (username: string, password: string) => {
      setError(null);
      try {
        const { access, refresh } = await apiLogin(username, password);
        localStorage.setItem(ACCESS_KEY, access);
        localStorage.setItem(REFRESH_KEY, refresh);
        await loadUser(access);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Error al iniciar sesión");
        throw err;
      }
    },
    [loadUser]
  );

  const logout = useCallback(() => {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    setUser(null);
    setError(null);
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const value: AuthContextValue = {
    user,
    loading,
    error,
    login,
    logout,
    clearError,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}

export function useAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}
