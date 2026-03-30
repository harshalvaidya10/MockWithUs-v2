"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiRequest, ApiError } from "@/lib/api";
import { clearAccessToken, getAccessToken, setAccessToken } from "@/lib/auth";

export interface CurrentUser {
  id: string;
  email: string;
  full_name: string | null;
  created_at: string;
}

export interface AuthState {
  user: CurrentUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  accessToken: string | null;
  authError: string | null;
  refreshUser: () => Promise<void>;
  logout: () => void;
  loginWithToken: (token: string) => Promise<void>;
}

export function useAuth(): AuthState {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [accessToken, setAccessTokenState] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const authRequestIdRef = useRef(0);

  const logout = useCallback(() => {
    authRequestIdRef.current += 1;
    clearAccessToken();
    setAccessTokenState(null);
    setAuthError(null);
    setUser(null);
    setIsLoading(false);
  }, []);

  const refreshUser = useCallback(async () => {
    const requestId = ++authRequestIdRef.current;
    const token = getAccessToken();

    if (!token) {
      if (requestId !== authRequestIdRef.current) {
        return;
      }

      setAccessTokenState(null);
      setAuthError(null);
      setUser(null);
      setIsLoading(false);
      return;
    }

    if (requestId !== authRequestIdRef.current) {
      return;
    }

    setAccessTokenState(token);
    setAuthError(null);

    try {
      const currentUser = await apiRequest<CurrentUser>("/auth/me", {
        method: "GET",
      });

      if (requestId !== authRequestIdRef.current) {
        return;
      }

      setUser(currentUser);
    } catch (error) {
      if (requestId !== authRequestIdRef.current) {
        return;
      }

      if (error instanceof ApiError && error.status === 401) {
        logout();
      } else if (error instanceof ApiError) {
        setAuthError(error.message);
      } else {
        setAuthError("Unable to refresh session right now.");
      }
    } finally {
      if (requestId === authRequestIdRef.current) {
        setIsLoading(false);
      }
    }
  }, [logout]);

  const loginWithToken = useCallback(
    async (token: string) => {
      const requestId = ++authRequestIdRef.current;
      setAccessToken(token);
      setAccessTokenState(token);
      setAuthError(null);
      setIsLoading(true);

      try {
        const currentUser = await apiRequest<CurrentUser>("/auth/me", {
          method: "GET",
        });

        if (requestId !== authRequestIdRef.current) {
          return;
        }

        setUser(currentUser);
      } catch (error) {
        if (requestId !== authRequestIdRef.current) {
          return;
        }

        if (error instanceof ApiError && error.status === 401) {
          logout();
        } else if (error instanceof ApiError) {
          setAuthError(error.message);
        } else {
          setAuthError("Unable to refresh session right now.");
        }

        throw error;
      } finally {
        if (requestId === authRequestIdRef.current) {
          setIsLoading(false);
        }
      }
    },
    [logout],
  );

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);

  return {
    user,
    isAuthenticated: Boolean(user) || (Boolean(accessToken) && authError !== null),
    isLoading,
    accessToken,
    authError,
    refreshUser,
    logout,
    loginWithToken,
  };
}
