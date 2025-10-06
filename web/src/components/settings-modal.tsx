'use client';

import { useEffect, useRef } from 'react';
import type { UserPreferences, ThemePreference, LocalePreference } from '../hooks/use-preferences';
import { FEATURE_FLAG_ORDER, useFeatureFlags } from '../lib/feature-flags';
import { useI18n } from '../i18n/context';
import { SUPPORTED_LOCALES, type MessageKey } from '../i18n/messages';

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea, input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export interface SettingsModalProps {
  open: boolean;
  preferences: UserPreferences;
  hydrated: boolean;
  onClose: () => void;
  onUpdate: (patch: Partial<UserPreferences>) => void;
  onReset: () => void;
  shortcutModifier?: string;
}

const LOCALE_LABEL_KEYS: Record<LocalePreference, MessageKey> = {
  en: 'settings.locale.en'
};

export function SettingsModal({
  open,
  preferences,
  hydrated,
  onClose,
  onUpdate,
  onReset,
  shortcutModifier = 'Ctrl'
}: SettingsModalProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const firstFieldRef = useRef<HTMLInputElement | null>(null);
  const previouslyFocused = useRef<Element | null>(null);
  const modifier = shortcutModifier;
  const { t } = useI18n();

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    previouslyFocused.current = document.activeElement;
    requestAnimationFrame(() => {
      firstFieldRef.current?.focus();
    });

    const trapFocus = (event: KeyboardEvent) => {
      if (!dialogRef.current || event.key !== 'Tab') {
        return;
      }
      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      if (!focusable.length) {
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (event.shiftKey) {
        if (!active || active === first) {
          event.preventDefault();
          last.focus();
        }
      } else if (!active || active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      }
    };

    document.addEventListener('keydown', trapFocus, true);
    document.addEventListener('keydown', closeOnEscape, true);

    return () => {
      document.removeEventListener('keydown', trapFocus, true);
      document.removeEventListener('keydown', closeOnEscape, true);
      if (previouslyFocused.current instanceof HTMLElement) {
        previouslyFocused.current.focus();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [open]);

  const featureFlagApi = useFeatureFlags();

  if (!open) {
    return null;
  }

  const disabled = !hydrated;
  const {
    flags: featureFlags,
    hydrated: featureFlagsHydrated,
    setFlag: setFeatureFlag,
    resetFlags: resetFeatureFlags
  } = featureFlagApi;
  const flagsDisabled = !featureFlagsHydrated;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-slate-950/70 px-4 py-10 backdrop-blur-sm sm:py-14">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-modal-title"
        aria-describedby="settings-modal-desc"
        id="hc-settings-modal"
        tabIndex={-1}
        className="w-full max-w-xl"
      >
        <div className="flex max-h-[min(90vh,680px)] flex-col overflow-hidden rounded-3xl border border-slate-800 bg-slate-900 text-slate-100 shadow-2xl">
          <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-slate-800 bg-slate-900/95 px-6 py-4 backdrop-blur">
            <div className="space-y-1">
              <h2 id="settings-modal-title" className="text-lg font-semibold">
                {t('settings.title')}
              </h2>
              <p id="settings-modal-desc" className="text-sm text-slate-400">
                {t('settings.subtitle')}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full bg-slate-800 px-3 py-1 text-sm text-slate-300 hover:bg-slate-700"
              aria-label={t('settings.close')}
            >
              {t('settings.close')}
            </button>
          </header>

          <div className="flex-1 overflow-y-auto px-6 py-6 text-sm">
            <div className="space-y-6">
              <fieldset className="space-y-2">
                <legend className="text-xs uppercase tracking-wide text-slate-500">{t('settings.section.chat')}</legend>
                <label className="flex items-start justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                  <div className="flex-1">
                    <span className="font-semibold text-slate-100">{t('settings.streaming.label')}</span>
                    <p className="mt-1 text-xs text-slate-400">{t('settings.streaming.help')}</p>
                  </div>
                  <input
                    ref={firstFieldRef}
                    type="checkbox"
                    className="h-5 w-5"
                    checked={preferences.streaming}
                    onChange={(event) => onUpdate({ streaming: event.target.checked })}
                    disabled={disabled}
                  />
                </label>
                <label className="flex items-start justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                  <div className="flex-1">
                    <span className="font-semibold text-slate-100">{t('settings.enter.label')}</span>
                    <p className="mt-1 text-xs text-slate-400">{t('settings.enter.help')}</p>
                  </div>
                  <input
                    type="checkbox"
                    className="h-5 w-5"
                    checked={preferences.enterToSend}
                    onChange={(event) => onUpdate({ enterToSend: event.target.checked })}
                    disabled={disabled}
                  />
                </label>
                <label className="flex items-start justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                  <div className="flex-1">
                    <span className="font-semibold text-slate-100">{t('settings.autoscroll.label')}</span>
                    <p className="mt-1 text-xs text-slate-400">{t('settings.autoscroll.help')}</p>
                  </div>
                  <input
                    type="checkbox"
                    className="h-5 w-5"
                    checked={preferences.autoScrollTranscript}
                    onChange={(event) => onUpdate({ autoScrollTranscript: event.target.checked })}
                    disabled={disabled}
                  />
                </label>
                <label className="flex items-start justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                  <div className="flex-1">
                    <span className="font-semibold text-slate-100">{t('settings.avatar.label')}</span>
                    <p className="mt-1 text-xs text-slate-400">{t('settings.avatar.help')}</p>
                  </div>
                  <input
                    type="checkbox"
                    className="h-5 w-5"
                    checked={preferences.showCoachAvatar}
                    onChange={(event) => onUpdate({ showCoachAvatar: event.target.checked })}
                    disabled={disabled}
                  />
                </label>
                <div className="space-y-3 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                  <div>
                    <span className="font-semibold text-slate-100">LLM provider overrides</span>
                    <p className="mt-1 text-xs text-slate-400">
                      Configure model, temperature, and max tokens forwarded to the provider. Leave blank to use defaults.
                    </p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <label className="flex flex-col gap-2 text-xs text-slate-300">
                      <span className="text-slate-400">Model</span>
                      <input
                        type="text"
                        className="rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600"
                        value={preferences.providerModel}
                        onChange={(event) => onUpdate({ providerModel: event.target.value })}
                        placeholder="e.g. gpt-4o-mini"
                        disabled={disabled}
                      />
                    </label>
                    <label className="flex flex-col gap-2 text-xs text-slate-300">
                      <span className="text-slate-400">Temperature</span>
                      <input
                        type="number"
                        min={0}
                        max={2}
                        step={0.1}
                        className="rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600"
                        value={preferences.providerTemperature ?? ''}
                        onChange={(event) => {
                          const raw = event.target.value;
                          if (!raw.trim()) {
                            onUpdate({ providerTemperature: null });
                            return;
                          }
                          const next = Number.parseFloat(raw);
                          if (Number.isFinite(next)) {
                            const clamped = Math.min(2, Math.max(0, next));
                            onUpdate({ providerTemperature: clamped });
                          } else {
                            onUpdate({ providerTemperature: null });
                          }
                        }}
                        placeholder="0 - 2"
                        disabled={disabled}
                      />
                    </label>
                    <label className="flex flex-col gap-2 text-xs text-slate-300">
                      <span className="text-slate-400">Max tokens</span>
                      <input
                        type="number"
                        min={0}
                        step={1}
                        className="rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600"
                        value={preferences.providerMaxTokens ?? ''}
                        onChange={(event) => {
                          const raw = event.target.value;
                          if (!raw.trim()) {
                            onUpdate({ providerMaxTokens: null });
                            return;
                          }
                          const next = Number.parseInt(raw, 10);
                          if (Number.isFinite(next) && next > 0) {
                            onUpdate({ providerMaxTokens: next });
                          } else {
                            onUpdate({ providerMaxTokens: null });
                          }
                        }}
                        placeholder="leave blank"
                        disabled={disabled}
                      />
                    </label>
                  </div>
                </div>
              </fieldset>

              <fieldset className="space-y-2">
                <legend className="text-xs uppercase tracking-wide text-slate-500">Analysis & Review</legend>
                <label className="flex items-start justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                  <div className="flex-1">
                    <span className="font-semibold text-slate-100">Holistic Review</span>
                    <p className="mt-1 text-xs text-slate-400">
                      Enable joint Core + UCN/RR analysis for comprehensive profile review. When enabled, the system will analyze traits using both traditional core analysis and UCN/RR refinement metrics.
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    className="h-5 w-5"
                    checked={preferences.holisticReview}
                    onChange={(event) => onUpdate({ holisticReview: event.target.checked })}
                    disabled={disabled}
                  />
                </label>
              </fieldset>

              <fieldset className="space-y-2">
                <legend className="text-xs uppercase tracking-wide text-slate-500">{t('settings.section.layout')}</legend>
                <label className="flex items-start justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                  <div className="flex-1">
                    <span className="font-semibold text-slate-100">{t('settings.compact.label')}</span>
                    <p className="mt-1 text-xs text-slate-400">{t('settings.compact.help')}</p>
                  </div>
                  <input
                    type="checkbox"
                    className="h-5 w-5"
                    checked={preferences.compactDensity}
                    onChange={(event) => onUpdate({ compactDensity: event.target.checked })}
                    disabled={disabled}
                  />
                </label>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                  <p className="font-semibold text-slate-100">{t('settings.theme.label')}</p>
                  <p className="mt-1 text-xs text-slate-400">{t('settings.theme.help')}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-3">
                    {(['dark', 'light'] as ThemePreference[]).map((theme) => (
                      <label key={theme} className="flex items-center gap-2 rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-200">
                        <input
                          type="radio"
                          name="settings-theme"
                          value={theme}
                          checked={preferences.theme === theme}
                          onChange={() => onUpdate({ theme })}
                          disabled={disabled}
                        />
                        {theme === 'light' ? t('settings.theme.light') : t('settings.theme.dark')}
                      </label>
                    ))}
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                  <p className="font-semibold text-slate-100">{t('settings.locale.label')}</p>
                  <p className="mt-1 text-xs text-slate-400">{t('settings.locale.help')}</p>
                  <select
                    className="mt-3 w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100"
                    value={preferences.locale}
                    onChange={(event) => onUpdate({ locale: event.target.value as LocalePreference })}
                    disabled={disabled}
                  >
                    {(SUPPORTED_LOCALES as LocalePreference[]).map((locale) => (
                      <option key={locale} value={locale}>
                        {t(LOCALE_LABEL_KEYS[locale])}
                      </option>
                    ))}
                  </select>
                </div>
              </fieldset>

              <fieldset className="space-y-2">
                <legend className="text-xs uppercase tracking-wide text-slate-500">{t('settings.section.shortcuts')}</legend>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                  <p className="font-semibold text-slate-100">{t('settings.shortcuts.title')}</p>
                  <p className="mt-1 text-xs text-slate-400">
                    {t('settings.shortcuts.help')} (<ShortcutChip text={`${modifier}+/`} />)
                  </p>
                  <ul className="mt-3 space-y-2 text-xs text-slate-300">
                    <li className="flex items-center gap-2">
                      <ShortcutChip text={`${modifier}+K`} /> <span>{t('settings.shortcuts.focusUser')}</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <ShortcutChip text={`${modifier}+Shift+F`} /> <span>{t('settings.shortcuts.search')}</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <ShortcutChip text="S" /> <span>{t('settings.shortcuts.openSettings')}</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <ShortcutChip text="D" /> <span>{t('settings.shortcuts.openDraft')}</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <ShortcutChip text="G" /> <span>{t('settings.shortcuts.openSnapshots')}</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <ShortcutChip text="P" /> <span>{t('settings.shortcuts.togglePin')}</span>
                    </li>
                  </ul>
                </div>
              </fieldset>

              {featureFlagsHydrated ? (
                <fieldset className="space-y-3">
                  <legend className="text-xs uppercase tracking-wide text-slate-500">
                    {t('settings.section.devFlags')}
                  </legend>
                  <p className="text-xs text-slate-500">{t('settings.devFlags.help')}</p>
                  <ul className="space-y-3">
                    {FEATURE_FLAG_ORDER.map((flag) => (
                      <li
                        key={flag}
                        className="flex items-start justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4"
                      >
                        <div>
                          <span className="font-semibold text-slate-100">
                            {t(`featureFlags.flag.${flag}.label` as any)}
                          </span>
                          <p className="mt-1 text-xs text-slate-400">
                            {t(`featureFlags.flag.${flag}.help` as any)}
                          </p>
                        </div>
                        <input
                          type="checkbox"
                          className="h-5 w-5"
                          checked={Boolean(featureFlags[flag])}
                          onChange={(event) => setFeatureFlag(flag, event.target.checked)}
                          disabled={flagsDisabled}
                        />
                      </li>
                    ))}
                  </ul>
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={() => resetFeatureFlags()}
                      className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:border-slate-500"
                      disabled={flagsDisabled}
                    >
                      {t('featureFlags.dialog.reset')}
                    </button>
                  </div>
                </fieldset>
              ) : null}
            </div>
          </div>

          <footer className="sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 bg-slate-900/95 px-6 py-4 text-xs text-slate-400 backdrop-blur">
            <button
              type="button"
              onClick={onReset}
              className="rounded-full border border-slate-700 px-3 py-2 font-semibold text-slate-200 transition hover:bg-slate-800"
              disabled={disabled}
            >
              {t('settings.reset')}
            </button>
            <span>{hydrated ? t('settings.autosave') : t('settings.loading')}</span>
          </footer>
        </div>
      </div>
    </div>
  );
}

function ShortcutChip({ text }: { text: string }) {
  return (
    <span className="rounded-full border border-slate-700 bg-slate-900 px-2 py-0.5 font-mono text-[11px] text-slate-200">
      {text}
    </span>
  );
}
