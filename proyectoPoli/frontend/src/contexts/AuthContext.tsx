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

  const loadUser = useCallback(async (access: string) => {
    try {
      const me = await getMe(access);
      setUser(me);
    } catch {
      const stored = localStorage.getItem(REFRESH_KEY);
      if (stored) {
        try {
          const { access: newAccess } = await refreshToken(stored);
          localStorage.setItem(ACCESS_KEY, newAccess);
          const me = await getMe(newAccess);
          setUser(me);
        } catch {
          localStorage.removeItem(ACCESS_KEY);
          localStorage.removeItem(REFRESH_KEY);
          setUser(null);
        }
      } else {
        setUser(null);
      }
    }
  }, []);

  useEffect(() => {
    const access = localStorage.getItem(ACCESS_KEY);
    if (!access) {
      setLoading(false);
      return;
    }
    loadUser(access).finally(() => setLoading(false));
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
