"use client";

import { useCallback, useEffect, useState } from "react";

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
  refreshUser: () => Promise<void>;
  logout: () => void;
  loginWithToken: (token: string) => Promise<void>;
}

export function useAuth(): AuthState {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [accessToken, setAccessTokenState] = useState<string | null>(null);

  const logout = useCallback(() => {
    clearAccessToken();
    setAccessTokenState(null);
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    const token = getAccessToken();

    if (!token) {
      setAccessTokenState(null);
      setUser(null);
      setIsLoading(false);
      return;
    }

    setAccessTokenState(token);

    try {
      const currentUser = await apiRequest<CurrentUser>("/auth/me", {
        method: "GET",
      });

      setUser(currentUser);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        logout();
      } else {
        setUser(null);
      }
    } finally {
      setIsLoading(false);
    }
  }, [logout]);

  const loginWithToken = useCallback(
    async (token: string) => {
      setAccessToken(token);
      setAccessTokenState(token);
      setIsLoading(true);

      try {
        const currentUser = await apiRequest<CurrentUser>("/auth/me", {
          method: "GET",
        });

        setUser(currentUser);
      } catch (error) {
        logout();
        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [logout],
  );

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);

  return {
    user,
    isAuthenticated: Boolean(user),
    isLoading,
    accessToken,
    refreshUser,
    logout,
    loginWithToken,
  };
}