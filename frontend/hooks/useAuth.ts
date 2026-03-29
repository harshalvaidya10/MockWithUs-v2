"use client";

import { useEffect, useState } from "react";

import { getAccessToken } from "@/lib/auth";

export interface AuthState {
  isAuthenticated: boolean;
  accessToken: string | null;
}

export function useAuth(): AuthState {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    accessToken: null,
  });

  useEffect(() => {
    const token = getAccessToken();
    setState({
      isAuthenticated: Boolean(token),
      accessToken: token,
    });
  }, []);

  return state;
}
