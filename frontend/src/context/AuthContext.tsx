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

  const loadUserData = useCallback(async () => {
    try {
      const token = getAccessToken();
      if (!token) {
        setIsLoading(false);
        return;
      }
      const [userData, orgsData] = await Promise.all([
        fetchCurrentUser(),
        fetchUserOrganizations(),
      ]);
      setUser(userData);
      setOrganizations(orgsData);

      // Set active org based on default_organization_id or first available
      if (orgsData.length > 0) {
        const preferred = orgsData.find(o => o.id === userData.default_organization_id) || orgsData[0];
        setActiveOrg(preferred);
      }
      setError(null);
    } catch (err: any) {
      console.warn('Authentication validation failed:', err);
      clearTokens();
      setUser(null);
      setActiveOrg(null);
      setOrganizations([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUserData();
  }, [loadUserData]);

  const login = async (email: string, pass: string) => {
    setIsLoading(true);
    setError(null);
    try {
      await loginUser(email, pass);
      await loadUserData();
    } catch (err: any) {
      setError(err.message || 'Login failed.');
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (payload: {
    email: string;
    password: string;
    full_name?: string;
    role?: string;
    organization_name?: string;
  }) => {
    setIsLoading(true);
    setError(null);
    try {
      await registerUser(payload);
      await loadUserData();
    } catch (err: any) {
      setError(err.message || 'Registration failed.');
      throw err;
    } finally {
      setIsLoading(false);
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
