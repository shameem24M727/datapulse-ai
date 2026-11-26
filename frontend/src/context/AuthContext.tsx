import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { UserProfile, Organization } from '../types';
import {
  loginUser,
  registerUser,
  logoutUser,
  fetchCurrentUser,
  fetchUserOrganizations,
  switchOrganization,
  createOrganization,
  getAccessToken,
  clearTokens,
} from '../services/api';

interface AuthContextType {
  user: UserProfile | null;
  activeOrg: Organization | null;
  organizations: Organization[];
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (email: string, pass: string) => Promise<void>;
  register: (payload: {
    email: string;
    password: string;
    full_name?: string;
    role?: string;
    organization_name?: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  switchOrg: (orgId: string) => Promise<void>;
  createOrg: (name: string, description?: string) => Promise<Organization>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [activeOrg, setActiveOrg] = useState<Organization | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadUserData = useCallback(async (rethrowOnError = false) => {
    try {
      const token = getAccessToken();
      console.debug('[Auth] loadUserData started', { hasToken: Boolean(token) });
      if (!token) {
        setIsLoading(false);
        return;
      }
      const [userData, orgsData] = await Promise.all([
        fetchCurrentUser(),
        fetchUserOrganizations(),
      ]);
      console.debug('[Auth] Profile and organizations loaded', {
        profileLoaded: Boolean(userData?.id),
        orgCount: orgsData.length,
      });
      setUser(userData);
      setOrganizations(orgsData);

      // Set active org based on active_organization_id, default_organization_id, or first available
      if (orgsData.length > 0) {
        const targetOrgId = userData.active_organization_id || userData.default_organization_id;
        const preferred = orgsData.find(o => o.id === targetOrgId) || orgsData[0];
        setActiveOrg(preferred);
      }
      setError(null);
      console.debug('[Auth] Authentication state updated', { isAuthenticated: true });
    } catch (err: any) {
      const message = err?.message || 'Unable to verify your session.';
      const status = err?.status;
      console.warn('[Auth] Authentication validation failed:', message);
      // Only discard stored tokens when the server explicitly rejects them (401/403).
      // For cold-start timeouts or temporary network outages, preserve tokens so a retry/refresh can restore the session.
      if (status === 401 || status === 403) {
        clearTokens();
      }
      setUser(null);
      setActiveOrg(null);
      setOrganizations([]);
      setError(message);
      console.debug('[Auth] Authentication state reset', { isAuthenticated: false, tokenCleared: status === 401 || status === 403 });
      if (rethrowOnError) {
        throw err;
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const startupWatchdog = setTimeout(() => {
      if (active) {
        console.warn('[Auth] Startup session check exceeded 95s cold-start timeout; showing Login view.');
        setIsLoading(false);
      }
    }, 95000);

    loadUserData(false).finally(() => {
      clearTimeout(startupWatchdog);
    });

    return () => {
      active = false;
      clearTimeout(startupWatchdog);
    };
  }, [loadUserData]);

  const login = async (email: string, pass: string) => {
    setError(null);
    try {
      console.debug('[Auth] Submitting login request');
      await loginUser(email, pass);
      console.debug('[Auth] Login succeeded, loading user profile', { hasToken: Boolean(getAccessToken()) });
      await loadUserData(true);
    } catch (err: any) {
      const message = err?.message || 'Login failed.';
      console.warn('[Auth] Login flow failed:', message);
      setError(message);
      throw err;
    }
  };

  const register = async (payload: {
    email: string;
    password: string;
    full_name?: string;
    role?: string;
    organization_name?: string;
  }) => {
    setError(null);
    try {
      console.debug('[Auth] Submitting registration request');
      await registerUser(payload);
      await loadUserData(true);
    } catch (err: any) {
      const message = err?.message || 'Registration failed.';
      console.warn('[Auth] Registration flow failed:', message);
      setError(message);
      throw err;
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await logoutUser();
    } finally {
      setUser(null);
      setActiveOrg(null);
      setOrganizations([]);
      setIsLoading(false);
    }
  };

  const switchOrg = async (orgId: string) => {
    setIsLoading(true);
    try {
      await switchOrganization(orgId);
      const selected = organizations.find(o => o.id === orgId);
      if (selected) {
        setActiveOrg(selected);
      }
      await loadUserData();
    } catch (err: any) {
      setError(err.message || 'Failed to switch organization.');
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const createOrg = async (name: string, description?: string) => {
    const newOrg = await createOrganization(name, description);
    await loadUserData();
    return newOrg;
  };

  const refreshProfile = async () => {
    await loadUserData();
  };

  const isAuthenticated = Boolean(user && getAccessToken());

  return (
    <AuthContext.Provider
      value={{
        user,
        activeOrg,
        organizations,
        isAuthenticated,
        isLoading,
        error,
        login,
        register,
        logout,
        switchOrg,
        createOrg,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
