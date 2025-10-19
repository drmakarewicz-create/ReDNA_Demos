'use client';

/**
 * Developer Mode Context
 *
 * Provides a global context for toggling between User Mode and Developer Mode.
 *
 * USER MODE:
 * - Pristine, production-ready interface
 * - Only shows features actual end users would see
 * - Clean, minimal, focused on coaching experience
 * - Relies on Head Coach delegation for coach switching
 *
 * DEVELOPER MODE:
 * - Additional debugging tools, metrics, and controls
 * - Manual coach switching buttons
 * - Performance metrics, feature flags, raw data views
 * - Development-only panels and diagnostics
 *
 * Architecture:
 * - State stored in localStorage for persistence
 * - React Context for global access
 * - DevOnly component for conditional rendering
 * - Mode-aware components can adapt their UI
 *
 * Usage:
 *   import { useDeveloperMode, DevOnly } from '@/lib/developer-mode';
 *
 *   const { isDeveloperMode, toggleDeveloperMode } = useDeveloperMode();
 *
 *   <DevOnly>
 *     <DebugPanel />
 *   </DevOnly>
 */

import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

const DEVELOPER_MODE_KEY = 'redna_developer_mode';

interface DeveloperModeContextValue {
  isDeveloperMode: boolean;
  toggleDeveloperMode: () => void;
  setDeveloperMode: (enabled: boolean) => void;
}

const DeveloperModeContext = createContext<DeveloperModeContextValue | undefined>(undefined);

export function DeveloperModeProvider({ children }: { children: ReactNode }) {
  // Initialize from localStorage (default to false for User Mode)
  const [isDeveloperMode, setIsDeveloperModeState] = useState<boolean>(false);
  const [isHydrated, setIsHydrated] = useState(false);

  // Hydrate from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(DEVELOPER_MODE_KEY);
    if (stored !== null) {
      setIsDeveloperModeState(stored === 'true');
    }
    setIsHydrated(true);
  }, []);

  const setDeveloperMode = (enabled: boolean) => {
    setIsDeveloperModeState(enabled);
    localStorage.setItem(DEVELOPER_MODE_KEY, String(enabled));

    // Log mode changes for debugging
    console.log(`[Developer Mode] ${enabled ? 'ENABLED' : 'DISABLED'}`);
  };

  const toggleDeveloperMode = () => {
    setDeveloperMode(!isDeveloperMode);
  };

  const value: DeveloperModeContextValue = {
    isDeveloperMode: isHydrated ? isDeveloperMode : false,
    toggleDeveloperMode,
    setDeveloperMode,
  };

  return (
    <DeveloperModeContext.Provider value={value}>
      {children}
    </DeveloperModeContext.Provider>
  );
}

/**
 * Hook to access developer mode state
 */
export function useDeveloperMode() {
  const context = useContext(DeveloperModeContext);
  if (!context) {
    throw new Error('useDeveloperMode must be used within DeveloperModeProvider');
  }
  return context;
}

/**
 * Component that only renders its children in Developer Mode
 *
 * Example:
 *   <DevOnly>
 *     <PersonaRail />
 *   </DevOnly>
 */
export function DevOnly({ children, fallback = null }: { children: ReactNode; fallback?: ReactNode }) {
  const { isDeveloperMode } = useDeveloperMode();
  return <>{isDeveloperMode ? children : fallback}</>;
}

/**
 * Component that only renders its children in User Mode
 *
 * Example:
 *   <UserOnly>
 *     <CleanCoachInterface />
 *   </UserOnly>
 */
export function UserOnly({ children, fallback = null }: { children: ReactNode; fallback?: ReactNode }) {
  const { isDeveloperMode } = useDeveloperMode();
  return <>{!isDeveloperMode ? children : fallback}</>;
}

/**
 * HOC that wraps a component to only render in Developer Mode
 */
export function withDevOnly<P extends object>(Component: React.ComponentType<P>) {
  return function DevOnlyComponent(props: P) {
    const { isDeveloperMode } = useDeveloperMode();
    if (!isDeveloperMode) return null;
    return <Component {...props} />;
  };
}

/**
 * HOC that wraps a component to only render in User Mode
 */
export function withUserOnly<P extends object>(Component: React.ComponentType<P>) {
  return function UserOnlyComponent(props: P) {
    const { isDeveloperMode } = useDeveloperMode();
    if (isDeveloperMode) return null;
    return <Component {...props} />;
  };
}
