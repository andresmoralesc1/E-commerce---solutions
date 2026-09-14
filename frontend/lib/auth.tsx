"use client";
import {createContext, useContext, useEffect, useState} from "react";

interface AuthState {
  token: string | null;
  setToken: (t: string | null) => void;
}

const AuthCtx = createContext<AuthState>({token: null, setToken: () => {}});

export function AuthProvider({children}: {children: React.ReactNode}) {
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const t = localStorage.getItem("brain_token");
    if (t) setToken(t);
  }, []);

  useEffect(() => {
    if (token) localStorage.setItem("brain_token", token);
    else localStorage.removeItem("brain_token");
  }, [token]);

  return (
    <AuthCtx.Provider value={{token, setToken}}>{children}</AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);