"use client";
import {createContext, useContext, useEffect, useState} from "react";

interface TenantState {
  activeTenantId: string | null;
  setActiveTenantId: (id: string | null) => void;
}

const TenantCtx = createContext<TenantState>({
  activeTenantId: null,
  setActiveTenantId: () => {},
});

export function TenantProvider({children}: {children: React.ReactNode}) {
  const [activeTenantId, setActiveTenantId] = useState<string | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem("brain_active_tenant");
    if (saved) setActiveTenantId(saved);
  }, []);

  return (
    <TenantCtx.Provider value={{activeTenantId, setActiveTenantId}}>
      {children}
    </TenantCtx.Provider>
  );
}

export const useTenant = () => useContext(TenantCtx);