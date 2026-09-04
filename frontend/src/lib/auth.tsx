import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { clearToken, getToken, setToken as persistToken } from "./token";
type AuthContextValue = {
  enabled: boolean | null;
  authenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  error: string | null;
};
const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [token, setToken] = useState(() => getToken());
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api
      .get<{ auth_enabled: boolean }>("auth/config")
      .then(({ data }) => setEnabled(data.auth_enabled))
      .catch(() => {
        setError("Backend is unavailable.");
        setEnabled(true);
      });
  }, []);
  const value = useMemo(
    () => ({
      enabled,
      authenticated: !enabled || Boolean(token),
      error,
      login: async (username: string, password: string) => {
        setError(null);
        try {
          const { data } = await api.post<{ access_token: string }>("auth/login", {
            username,
            password,
          });
          if (!data.access_token) throw new Error("Authentication is not enabled.");
          persistToken(data.access_token);
          setToken(data.access_token);
        } catch {
          setError("Login failed. Check credentials and backend availability.");
          throw new Error("login failed");
        }
      },
      logout: () => {
        clearToken();
        setToken(null);
      },
    }),
    [enabled, error, token],
  );
  if (enabled === null)
    return (
      <div className="grid min-h-screen place-items-center">Checking backend authentication…</div>
    );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
