'use client';

import { useMemo, useState } from 'react';
import type { FeatureFlagKey } from '../lib/feature-flags';
import { FEATURE_FLAG_ORDER, useFeatureFlags } from '../lib/feature-flags';
import { useI18n } from '../i18n/context';

export function DevFlagsControl() {
  const { flags, activeKeys, setFlag, resetFlags, hydrated } = useFeatureFlags();
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const hasActive = activeKeys.length > 0;

  const flagItems = useMemo(
    () => FEATURE_FLAG_ORDER.map((key) => ({ key, enabled: Boolean(flags[key]) })),
    [flags]
  );

  if (!hydrated) {
    return null;
  }

  return (
    <>
      {hasActive ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="fixed bottom-4 right-4 z-[90] flex items-center gap-2 rounded-full border border-cyan-500/60 bg-slate-900/90 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-cyan-200 shadow-lg transition hover:border-cyan-300 hover:text-cyan-100"
          aria-label={t('featureFlags.banner.manage')}
        >
          <span className="inline-flex h-2 w-2 rounded-full bg-cyan-400" aria-hidden="true" />
          {t('featureFlags.banner.active')}
        </button>
      ) : null}

      {open ? (
        <div className="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/70 px-4 py-10 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-3xl border border-slate-800 bg-slate-900 text-slate-50 shadow-2xl">
            <header className="border-b border-slate-800 px-6 py-4">
              <h2 className="text-base font-semibold">{t('featureFlags.dialog.title')}</h2>
              <p className="mt-1 text-xs text-slate-400">{t('featureFlags.dialog.subtitle')}</p>
            </header>
            <div className="px-6 py-5">
              <ul className="space-y-3 text-sm">
                {flagItems.map((item) => (
                  <li key={item.key} className="flex items-start justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                    <div>
                      <p className="font-medium text-slate-100">{t(`featureFlags.flag.${item.key}.label` as any)}</p>
                      <p className="mt-1 text-xs text-slate-400">{t(`featureFlags.flag.${item.key}.help` as any)}</p>
                    </div>
                    <input
                      type="checkbox"
                      className="h-5 w-5"
                      checked={item.enabled}
                      onChange={(event) => setFlag(item.key, event.target.checked)}
                    />
                  </li>
                ))}
              </ul>
            </div>
            <footer className="flex items-center justify-between gap-4 border-t border-slate-800 px-6 py-4">
              <button
                type="button"
                onClick={resetFlags}
                className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:border-slate-500"
              >
                {t('featureFlags.dialog.reset')}
              </button>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-full bg-cyan-500/20 px-4 py-2 text-xs font-medium text-cyan-100 hover:bg-cyan-500/30"
              >
                {t('featureFlags.dialog.close')}
              </button>
            </footer>
          </div>
        </div>
      ) : null}
    </>
  );
}
