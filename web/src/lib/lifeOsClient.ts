import axios, { AxiosInstance } from 'axios';

import { CORE_API_BASE } from './api';

const CAP_TOKEN_KEY = 'DEVX_CAP_TOKEN';
const CAP_EXPIRES_KEY = 'DEVX_CAP_EXPIRES_AT';
const CAP_META_KEY = 'DEVX_CAP_META';

export function clearActiveCapabilityToken(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(CAP_TOKEN_KEY);
    window.localStorage.removeItem(CAP_EXPIRES_KEY);
    window.localStorage.removeItem(CAP_META_KEY);
  } catch {
    // ignore storage cleanup errors
  }
  (window as any).__devxCapToken = undefined;
}

export function getActiveCapabilityToken(): string | null {
  if (typeof window === 'undefined') return null;

  let token: string | null = null;
  let expiry: string | null = null;
  try {
    token = window.localStorage.getItem(CAP_TOKEN_KEY);
    expiry = window.localStorage.getItem(CAP_EXPIRES_KEY);
  } catch {
    clearActiveCapabilityToken();
    return null;
  }

  if (!token || !expiry) {
    clearActiveCapabilityToken();
    return null;
  }

  const expiryTs = Date.parse(expiry);
  if (Number.isNaN(expiryTs) || Date.now() >= expiryTs) {
    clearActiveCapabilityToken();
    return null;
  }

  return token;
}

const baseUrl = `${CORE_API_BASE.replace(/\/+$/, '')}/ui/hc`;

export const lifeOs: AxiosInstance = axios.create({
  baseURL: baseUrl,
});

lifeOs.interceptors.request.use((config) => {
  if (typeof window === 'undefined') {
    return config;
  }
  const memToken = (window as any).__devxCapToken as string | undefined;
  const stored = getActiveCapabilityToken();
  const capability = memToken || stored;
  if (capability) {
    // Use set method to properly set headers in axios
    config.headers.set('Authorization', `Bearer ${capability}`);
    if (!memToken && stored) {
      (window as any).__devxCapToken = stored;
    }
  }
  return config;
});

lifeOs.interceptors.response.use(
  (res) => res,
  (err) => {
    const status = err?.response?.status;
    if (status === 401 || status === 403) {
      clearActiveCapabilityToken();
    }
    return Promise.reject(err);
  }
);
