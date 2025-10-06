'use client';

import { createContext, useContext, useMemo, type ReactNode } from 'react';
import { MESSAGES, type SupportedLocale, type MessageKey } from './messages';

export interface I18nContextValue {
  locale: SupportedLocale;
  t: (key: MessageKey, replacements?: Record<string, string | number>) => string;
}

const DEFAULT_LOCALE: SupportedLocale = 'en';
const DEFAULT_VALUE: I18nContextValue = {
  locale: DEFAULT_LOCALE,
  t: (key) => MESSAGES[DEFAULT_LOCALE][key] ?? key,
};

const I18nContext = createContext<I18nContextValue>(DEFAULT_VALUE);

export function I18nProvider({ locale, children }: { locale: string; children: ReactNode }) {
  const normalized = (locale in MESSAGES ? locale : DEFAULT_LOCALE) as SupportedLocale;
  const messages = MESSAGES[normalized];

  const value = useMemo<I18nContextValue>(() => {
    const translate = (key: MessageKey, replacements?: Record<string, string | number>) => {
      const template = messages[key] ?? MESSAGES[DEFAULT_LOCALE][key] ?? key;
      if (!replacements || !template) {
        return template;
      }
      return Object.keys(replacements).reduce((acc, token) => {
        const pattern = new RegExp(`\\{${token}\\}`, 'g');
        return acc.replace(pattern, String(replacements[token] ?? ''));
      }, template);
    };

    return {
      locale: normalized,
      t: translate,
    };
  }, [normalized, messages]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  return useContext(I18nContext);
}
