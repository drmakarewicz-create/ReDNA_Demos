'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  createUser,
  fetchUsers,
  initUserContainers,
  submitOnboardingProfile,
  type CreateUserRequest,
  type OnboardingFactPayload,
  type SubmitOnboardingRequest,
  type UserSummary
} from '../lib/api';

export interface OnboardUserModalProps {
  open: boolean;
  proposedId?: string;
  onClose: () => void;
  onCreated: (user: UserSummary) => void;
}

type QuickFactKey = 'eyeColor' | 'hairColor' | 'handedness';

type QuickFactState = {
  value: string;
  label: string;
  custom: string;
};

type ScriptPath = 'smart_defaults' | 'trust_walkthrough';

type OnboardingPath = 'undecided' | 'smart' | 'trust';
type StepKey = 'user' | 'trust' | 'quickFacts' | 'interests' | 'review';

interface StepConfig {
  key: StepKey;
  label: string;
}

type InitNoticeState = {
  status: 'idle' | 'pending' | 'error' | 'done';
  message: string | null;
  userId: string | null;
  label: string | null;
  scriptPath: ScriptPath | null;
  quickFacts: SubmitOnboardingRequest['quickFacts'];
  interests: SubmitOnboardingRequest['interests'];
  seedUsed: boolean | null;
};

interface InitOptions {
  user: string;
  displayName?: string | null;
  scriptPath: ScriptPath;
  quickFacts: SubmitOnboardingRequest['quickFacts'];
  interests: SubmitOnboardingRequest['interests'];
  seedUsed: boolean;
}

const SCRIPT_PATH_BY_CHOICE: Record<Exclude<OnboardingPath, 'undecided'>, ScriptPath> = {
  smart: 'smart_defaults',
  trust: 'trust_walkthrough'
};

const DEFAULT_BIG_FIVE: Record<'O' | 'C' | 'E' | 'A' | 'N', number> = {
  O: 0.5,
  C: 0.5,
  E: 0.5,
  A: 0.5,
  N: 0.5
};

const DEFAULT_QUICK_FACT_STATE: Record<QuickFactKey, QuickFactState> = {
  eyeColor: { value: '', label: '', custom: '' },
  hairColor: { value: '', label: '', custom: '' },
  handedness: { value: '', label: '', custom: '' }
};

const QUICK_FACT_OPTIONS: Record<QuickFactKey, { apiKey: keyof SubmitOnboardingRequest['quickFacts']; label: string; options: { value: string; label: string }[] }> = {
  eyeColor: {
    apiKey: 'eye_color',
    label: 'Eye color',
    options: [
      { value: 'brown', label: 'Brown' },
      { value: 'blue', label: 'Blue' },
      { value: 'green', label: 'Green' },
      { value: 'hazel', label: 'Hazel' },
      { value: 'gray', label: 'Gray' },
      { value: 'amber', label: 'Amber' },
      { value: 'other', label: 'Other' }
    ]
  },
  hairColor: {
    apiKey: 'hair_color',
    label: 'Hair color',
    options: [
      { value: 'black', label: 'Black' },
      { value: 'brown', label: 'Brown' },
      { value: 'blonde', label: 'Blonde' },
      { value: 'red', label: 'Red' },
      { value: 'gray', label: 'Gray' },
      { value: 'other', label: 'Other' }
    ]
  },
  handedness: {
    apiKey: 'handedness',
    label: 'Handedness',
    options: [
      { value: 'right', label: 'Right-handed' },
      { value: 'left', label: 'Left-handed' },
      { value: 'ambidextrous', label: 'Ambidextrous' },
      { value: 'other', label: 'Other' }
    ]
  }
};

interface InterestOption {
  value: string;
  label: string;
}

const INTEREST_OPTIONS: InterestOption[] = [
  { value: 'wellness', label: 'Wellness' },
  { value: 'fitness', label: 'Fitness' },
  { value: 'career', label: 'Career' },
  { value: 'relationships', label: 'Relationships' },
  { value: 'style', label: 'Style & Fashion' },
  { value: 'creativity', label: 'Creativity' },
  { value: 'travel', label: 'Travel' },
  { value: 'personal_growth', label: 'Personal Growth' }
];

const INTEREST_LABEL_LOOKUP = INTEREST_OPTIONS.reduce<Record<string, string>>((acc, option) => {
  acc[option.value] = option.label;
  return acc;
}, {});

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea, input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function OnboardUserModal({ open, proposedId, onClose, onCreated }: OnboardUserModalProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const firstFieldRef = useRef<HTMLInputElement | null>(null);
  const previouslyFocused = useRef<Element | null>(null);
  const fetchTicketRef = useRef<number>(0);

  const [pathChoice, setPathChoice] = useState<OnboardingPath>('undecided');
  const [step, setStep] = useState<number>(0);
  const [mode, setMode] = useState<'existing' | 'new'>(proposedId ? 'new' : 'existing');
  const [selectedExisting, setSelectedExisting] = useState<UserSummary | null>(null);
  const [existingQuery, setExistingQuery] = useState<string>('');
  const [existingResults, setExistingResults] = useState<UserSummary[]>([]);
  const [existingLoading, setExistingLoading] = useState<boolean>(false);
  const [existingError, setExistingError] = useState<string | null>(null);

  const [userId, setUserId] = useState<string>(proposedId ? coerceSlug(proposedId) : '');
  const [label, setLabel] = useState<string>('');
  const [seedEnabled, setSeedEnabled] = useState<boolean>(true);
  const [seed, setSeed] = useState<Record<'O' | 'C' | 'E' | 'A' | 'N', number>>({ ...DEFAULT_BIG_FIVE });
  const [quickFacts, setQuickFacts] = useState<Record<QuickFactKey, QuickFactState>>({ ...DEFAULT_QUICK_FACT_STATE });
  const [selectedInterests, setSelectedInterests] = useState<string[]>([]);
  const [customInterests, setCustomInterests] = useState<string[]>([]);
  const [customInterestInput, setCustomInterestInput] = useState<string>('');

  const [pending, setPending] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<string>('');
  const [initNotice, setInitNotice] = useState<InitNoticeState>({
    status: 'idle',
    message: null,
    userId: null,
    label: null,
    scriptPath: null,
    quickFacts: {} as SubmitOnboardingRequest['quickFacts'],
    interests: { selected: [], custom: [] },
    seedUsed: null
  });

  const stepConfig: StepConfig[] = useMemo(() => {
    if (pathChoice === 'smart') {
      return [
        { key: 'user', label: 'Choose user' },
        { key: 'quickFacts', label: 'Quick facts' },
        { key: 'interests', label: 'Interests' },
        { key: 'review', label: 'Review' }
      ];
    }
    if (pathChoice === 'trust') {
      return [
        { key: 'user', label: 'Choose user' },
        { key: 'trust', label: 'Trust & privacy' },
        { key: 'quickFacts', label: 'Quick facts' },
        { key: 'interests', label: 'Interests' },
        { key: 'review', label: 'Review' }
      ];
    }
    return [];
  }, [pathChoice]);

  useEffect(() => {
    if (stepConfig.length > 0 && step >= stepConfig.length) {
      setStep(stepConfig.length - 1);
    }
  }, [step, stepConfig]);

  useEffect(() => {
    if (!open) {
      return;
    }
    previouslyFocused.current = document.activeElement;
    setPathChoice('undecided');
    setStep(0);
    setMode(proposedId ? 'new' : 'existing');
    setSelectedExisting(null);
    setExistingQuery('');
    setExistingResults([]);
    setExistingError(null);
    setExistingLoading(false);
    setUserId(proposedId ? coerceSlug(proposedId) : '');
    setLabel('');
    setSeedEnabled(true);
    setSeed({ ...DEFAULT_BIG_FIVE });
    setQuickFacts({ ...DEFAULT_QUICK_FACT_STATE });
    setSelectedInterests([]);
    setCustomInterests([]);
    setCustomInterestInput('');
    setError(null);
    setPending(false);
    setLiveStatus('Onboarding dialog opened.');
    setInitNotice({
      status: 'idle',
      message: null,
      userId: null,
      label: null,
      scriptPath: null,
      quickFacts: {} as SubmitOnboardingRequest['quickFacts'],
      interests: { selected: [], custom: [] },
      seedUsed: null
    });
    requestAnimationFrame(() => {
      firstFieldRef.current?.focus();
    });
  }, [open, proposedId]);

  useEffect(() => {
    if (!open && previouslyFocused.current instanceof HTMLElement) {
      previouslyFocused.current.focus();
    }
  }, [open]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const trapFocus = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || !dialogRef.current) {
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
    document.addEventListener('keydown', trapFocus, true);
    return () => document.removeEventListener('keydown', trapFocus, true);
  }, [open]);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (!open) {
        return;
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', handleKey, true);
    return () => window.removeEventListener('keydown', handleKey, true);
  }, [onClose, open]);

  useEffect(() => {
    if (!open || mode !== 'existing') {
      return undefined;
    }
    const ticket = Date.now();
    fetchTicketRef.current = ticket;
    setExistingLoading(true);
    setExistingError(null);
    const handle = window.setTimeout(() => {
      void fetchUsers(existingQuery.trim())
        .then((users) => {
          if (fetchTicketRef.current === ticket) {
            setExistingResults(users);
          }
        })
        .catch((err) => {
          if (fetchTicketRef.current === ticket) {
            setExistingError(describeError(err));
            setExistingResults([]);
          }
        })
        .finally(() => {
          if (fetchTicketRef.current === ticket) {
            setExistingLoading(false);
          }
        });
    }, 200);
    return () => {
      window.clearTimeout(handle);
    };
  }, [existingQuery, mode, open]);

  const slugError = useMemo(() => {
    if (mode !== 'new') {
      return null;
    }
    return validateUserId(userId);
  }, [mode, userId]);

  const canContinueStep0 = useMemo(() => {
    if (mode === 'existing') {
      return Boolean(selectedExisting);
    }
    return !slugError && userId.trim().length >= 3;
  }, [mode, selectedExisting, slugError, userId]);

  const quickFactsComplete = useMemo(() => {
    return (Object.keys(quickFacts) as QuickFactKey[]).every((key) => {
      const fact = quickFacts[key];
      if (!fact.value) {
        return false;
      }
      if (fact.value === 'other') {
        return Boolean(fact.custom.trim());
      }
      return true;
    });
  }, [quickFacts]);

  const interestsComplete = useMemo(() => {
    return selectedInterests.length + customInterests.length > 0;
  }, [customInterests.length, selectedInterests.length]);

  const canContinue = useMemo(() => {
    if (pending || !stepConfig.length) {
      return false;
    }
    const currentStep = stepConfig[step]?.key;
    switch (currentStep) {
      case 'user':
        return canContinueStep0;
      case 'trust':
        return true;
      case 'quickFacts':
        return quickFactsComplete;
      case 'interests':
        return interestsComplete;
      case 'review':
        return true;
      default:
        return true;
    }
  }, [canContinueStep0, interestsComplete, pending, quickFactsComplete, step, stepConfig]);

  const resolvedUserId = useMemo(() => {
    if (mode === 'existing' && selectedExisting) {
      return selectedExisting.id;
    }
    return userId.trim();
  }, [mode, selectedExisting, userId]);

  const resolvedDisplayName = useMemo(() => {
    if (mode === 'existing' && selectedExisting) {
      return selectedExisting.label || selectedExisting.id;
    }
    return label.trim() || resolvedUserId;
  }, [label, mode, resolvedUserId, selectedExisting]);

  const resolvedInterestsLabels = useMemo(() => {
    const mapped = selectedInterests.map((value) => INTEREST_LABEL_LOOKUP[value] ?? value);
    return [...mapped, ...customInterests];
  }, [customInterests, selectedInterests]);

  const goToStep = useCallback(
    (nextStep: number) => {
      setStep(nextStep);
      const totalSteps = stepConfig.length;
      setLiveStatus(`Moved to step ${nextStep + 1} of ${totalSteps}.`);
      setError(null);
      if (nextStep === 0) {
        requestAnimationFrame(() => {
          firstFieldRef.current?.focus();
        });
      }
    },
    [stepConfig.length]
  );

  const handleNext = useCallback(() => {
    if (!stepConfig.length || step === stepConfig.length - 1) {
      return;
    }
    goToStep(step + 1);
  }, [goToStep, step, stepConfig.length]);

  const handleBack = useCallback(() => {
    if (!stepConfig.length || step === 0 || pending) {
      return;
    }
    goToStep(step - 1);
  }, [goToStep, pending, step, stepConfig.length]);

  const toggleInterest = useCallback((option: InterestOption) => {
    setSelectedInterests((prev) => {
      if (prev.includes(option.value)) {
        return prev.filter((entry) => entry !== option.value);
      }
      return [...prev, option.value];
    });
  }, []);

  const addCustomInterest = useCallback(() => {
    const trimmed = customInterestInput.trim();
    if (!trimmed) {
      return;
    }
    setCustomInterests((prev) => {
      if (prev.some((entry) => entry.toLowerCase() === trimmed.toLowerCase())) {
        return prev;
      }
      if (selectedInterests.some((entry) => (INTEREST_LABEL_LOOKUP[entry] ?? entry).toLowerCase() === trimmed.toLowerCase())) {
        return prev;
      }
      return [...prev, trimmed];
    });
    setCustomInterestInput('');
  }, [customInterestInput, selectedInterests]);

  const removeCustomInterest = useCallback((value: string) => {
    setCustomInterests((prev) => prev.filter((entry) => entry !== value));
  }, []);

  const triggerInit = useCallback(
    ({ user, displayName, scriptPath, quickFacts, interests, seedUsed }: InitOptions) => {
      const trimmedUser = user.trim();
      if (!trimmedUser) {
        return;
      }
      const nextQuickFacts = { ...quickFacts } as SubmitOnboardingRequest['quickFacts'];
      const nextInterests: SubmitOnboardingRequest['interests'] = {
        selected: [...(interests.selected ?? [])],
        custom: [...(interests.custom ?? [])]
      };
      setInitNotice({
        status: 'pending',
        message: 'Setting up user workspace…',
        userId: trimmedUser,
        label: displayName ?? null,
        scriptPath,
        quickFacts: nextQuickFacts,
        interests: nextInterests,
        seedUsed
      });
      void initUserContainers({
        userId: trimmedUser,
        label: displayName ?? undefined,
        scriptPath,
        quickFacts: nextQuickFacts,
        interests: nextInterests,
        seedUsed
      })
        .then(() => {
          setInitNotice({
            status: 'done',
            message: null,
            userId: trimmedUser,
            label: displayName ?? null,
            scriptPath,
            quickFacts: nextQuickFacts,
            interests: nextInterests,
            seedUsed
          });
          setLiveStatus('User containers initialized.');
          try {
            window.dispatchEvent(
              new CustomEvent('hc-onboarding-init', {
                detail: {
                  userId: trimmedUser,
                  label: displayName ?? null,
                  scriptPath
                }
              })
            );
          } catch (eventError) {
            console.warn('Failed to dispatch onboarding init event', eventError);
          }
        })
        .catch((err) => {
          setInitNotice({
            status: 'error',
            message: describeError(err),
            userId: trimmedUser,
            label: displayName ?? null,
            scriptPath,
            quickFacts: nextQuickFacts,
            interests: nextInterests,
            seedUsed
          });
          setLiveStatus('User containers need attention. Retry when ready.');
        });
    },
    [setLiveStatus]
  );

  const applyQuickFact = useCallback((key: QuickFactKey, option: { value: string; label: string }) => {
    setQuickFacts((prev) => ({
      ...prev,
      [key]: {
        value: option.value,
        label: option.label,
        custom: option.value === 'other' ? prev[key].custom : ''
      }
    }));
  }, []);

  const updateQuickFactCustom = useCallback((key: QuickFactKey, value: string) => {
    setQuickFacts((prev) => ({
      ...prev,
      [key]: {
        ...prev[key],
        custom: value
      }
    }));
  }, []);

  const handleFinish = useCallback(async () => {
    if (!canContinue || pending) {
      return;
    }
    const finalUserId = resolvedUserId;
    if (!finalUserId) {
      setError('Select or create a user before finishing.');
      return;
    }

    const scriptChoice = pathChoice === 'smart' || pathChoice === 'trust' ? pathChoice : null;
    if (!scriptChoice) {
      setError('Choose how you want to onboard first.');
      return;
    }
    const scriptPath = SCRIPT_PATH_BY_CHOICE[scriptChoice];

    setPending(true);
    setError(null);
    setLiveStatus('Saving onboarding profile…');

    try {
      let summary: UserSummary;
      if (mode === 'new') {
        const createRequest: CreateUserRequest = {
          userId: finalUserId,
          label: label.trim() || undefined,
          seed: seedEnabled
            ? {
                Big5: {
                  O: Number(seed.O.toFixed(2)),
                  C: Number(seed.C.toFixed(2)),
                  E: Number(seed.E.toFixed(2)),
                  A: Number(seed.A.toFixed(2)),
                  N: Number(seed.N.toFixed(2))
                }
              }
            : undefined
        };
        const response = await createUser(createRequest);
        summary = {
          id: response.user.id,
          label: response.user.label,
          created_ts: response.user.created_ts,
          last_used_ts: new Date().toISOString()
        };
      } else if (selectedExisting) {
        summary = {
          ...selectedExisting,
          last_used_ts: new Date().toISOString()
        };
      } else {
        throw new Error('Select a user to continue.');
      }

      const quickFactsPayload = buildQuickFactsPayload(quickFacts);
      const interestsPayload: SubmitOnboardingRequest['interests'] = {
        selected: [...selectedInterests],
        custom: [...customInterests]
      };
      const submitRequest: SubmitOnboardingRequest = {
        userId: summary.id,
        displayName: resolvedDisplayName,
        bigFive: seedEnabled
          ? {
              O: Number(seed.O.toFixed(2)),
              C: Number(seed.C.toFixed(2)),
              E: Number(seed.E.toFixed(2)),
              A: Number(seed.A.toFixed(2)),
              N: Number(seed.N.toFixed(2))
            }
          : null,
        quickFacts: quickFactsPayload,
        interests: interestsPayload,
        notes: null
      };

      await submitOnboardingProfile(submitRequest);
      setLiveStatus('Onboarding profile saved.');
      onCreated(summary);
      try {
        window.dispatchEvent(
          new CustomEvent('hc-wyr-kickoff', {
            detail: {
              userId: summary.id,
              displayName: resolvedDisplayName,
              path: pathChoice,
              ts: Date.now()
            }
          })
        );
        setLiveStatus('Onboarding profile saved. Warming up with a quick WYR prompt.');
      } catch (eventError) {
        console.warn('Failed to dispatch WYR kickoff event', eventError);
      }
      triggerInit({
        user: summary.id,
        displayName: resolvedDisplayName,
        scriptPath,
        quickFacts: quickFactsPayload,
        interests: interestsPayload,
        seedUsed: Boolean(seedEnabled)
      });
    } catch (err) {
      setError(describeError(err));
      setLiveStatus('Failed to save onboarding profile.');
    } finally {
      setPending(false);
    }
  }, [
    canContinue,
    customInterests,
    label,
    mode,
    onCreated,
    pending,
    quickFacts,
    resolvedDisplayName,
    resolvedUserId,
    seed,
    seedEnabled,
    selectedExisting,
    selectedInterests,
    pathChoice,
    triggerInit
  ]);

  if (!open) {
    return null;
  }

  const renderQuickFactSection = (key: QuickFactKey) => {
    const state = quickFacts[key];
    const config = QUICK_FACT_OPTIONS[key];
    return (
      <section key={key} className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold text-slate-100">{config.label}</h4>
          <span className="text-xs text-slate-500">Pick one</span>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {config.options.map((option) => {
            const selected = state.value === option.value;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  applyQuickFact(key, option);
                  setLiveStatus(`${config.label} set to ${option.label}.`);
                }}
                className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                  selected
                    ? 'bg-cyan-500 text-slate-950'
                    : 'border border-slate-600 bg-slate-900 text-slate-200 hover:border-cyan-400 hover:text-cyan-200'
                }`}
              >
                {option.label}
              </button>
            );
          })}
        </div>
        {state.value === 'other' ? (
          <div className="mt-3">
            <label htmlFor={`quickfact-${key}`} className="text-xs uppercase tracking-wide text-slate-400">
              Describe other
            </label>
            <input
              id={`quickfact-${key}`}
              type="text"
              value={state.custom}
              onChange={(event) => updateQuickFactCustom(key, event.target.value)}
              className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm focus:border-cyan-400 focus:outline-none"
            />
          </div>
        ) : null}
      </section>
    );
  };

  const renderSeedSection = () => (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-slate-100">Tune the starting tone (optional)</h4>
        <label className="flex items-center gap-2 text-xs text-slate-400">
          <input
            type="checkbox"
            checked={seedEnabled}
            onChange={(event) => setSeedEnabled(event.target.checked)}
            className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-cyan-500 focus:ring-cyan-400"
          />
          Adjust manually
        </label>
      </div>
      <p className="text-xs text-slate-500">
        Leave this off to keep the balanced default. Turn it on if you want to nudge specific traits before the first session.
      </p>
      {seedEnabled ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {(['O', 'C', 'E', 'A', 'N'] as const).map((trait) => {
            const displayValue = Math.round(seed[trait] * 100);
            return (
              <div key={trait} className="rounded-2xl border border-slate-800 bg-slate-950/50 p-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-semibold text-slate-200">{SLIDER_LABELS[trait]}</span>
                  <span className="text-xs text-cyan-200">{displayValue}</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={1}
                  value={displayValue}
                  onChange={(event) => {
                    const raw = Number(event.target.value);
                    const clamped = Number.isNaN(raw) ? 0 : Math.min(Math.max(raw, 0), 100);
                    setSeed((prev) => ({
                      ...prev,
                      [trait]: clamped / 100
                    }));
                  }}
                  className="mt-3 w-full"
                />
              </div>
            );
          })}
        </div>
      ) : (
        <p className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/50 p-6 text-xs text-slate-400">
          Balanced seed locked in. You can always update traits later.
        </p>
      )}
    </section>
  );

  const renderStepContent = (stepKey?: StepKey) => {
    switch (stepKey) {
      case 'user':
        return (
          <div className="space-y-6">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-400">Mode</p>
              <div className="mt-2 flex gap-2">
                {[
                  { value: 'existing', label: 'Existing user' },
                  { value: 'new', label: 'Create new user' }
                ].map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => {
                      setMode(option.value as 'existing' | 'new');
                      setSelectedExisting(null);
                      setExistingQuery('');
                      setError(null);
                      setLiveStatus(`Mode set to ${option.label}.`);
                      requestAnimationFrame(() => {
                        firstFieldRef.current?.focus();
                      });
                    }}
                    className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                      mode === option.value
                        ? 'bg-cyan-500 text-slate-950'
                        : 'border border-slate-600 bg-slate-900 text-slate-200 hover:border-cyan-400 hover:text-cyan-200'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
            {mode === 'existing' ? (
              <section className="space-y-4">
                <div>
                  <label htmlFor="onboard-existing-search" className="text-xs uppercase tracking-wide text-slate-400">
                    Search users
                  </label>
                  <input
                    id="onboard-existing-search"
                    ref={firstFieldRef}
                    type="search"
                    value={existingQuery}
                    onChange={(event) => {
                      setExistingQuery(event.target.value);
                      setSelectedExisting(null);
                    }}
                    placeholder="Type a name or id"
                    className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-2 text-sm focus:border-cyan-400 focus:outline-none"
                  />
                </div>
                <div className="space-y-2">
                  {existingLoading ? <p className="text-xs text-slate-500">Loading suggestions…</p> : null}
                  {existingError ? <p className="text-xs text-rose-300">{existingError}</p> : null}
                  {!existingLoading && !existingResults.length && !existingError ? (
                    <p className="text-xs text-slate-500">No users match that search.</p>
                  ) : null}
                  <div className="grid gap-2">
                    {existingResults.slice(0, 8).map((entry) => {
                      const selected = selectedExisting?.id === entry.id;
                      return (
                        <button
                          key={entry.id}
                          type="button"
                          onClick={() => {
                            setSelectedExisting(entry);
                            setLiveStatus(`Selected ${entry.label || entry.id}.`);
                          }}
                          className={`flex flex-col rounded-2xl border px-4 py-3 text-left transition ${
                            selected
                              ? 'border-cyan-400 bg-cyan-500/20 text-cyan-100'
                              : 'border-slate-700 bg-slate-950/70 text-slate-200 hover:border-cyan-400 hover:text-cyan-100'
                          }`}
                        >
                          <span className="text-sm font-semibold">{entry.label || entry.id}</span>
                          <span className="text-xs text-slate-400">{entry.id}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </section>
            ) : (
              <section className="space-y-4">
                <div>
                  <label htmlFor="onboard-user-id" className="text-xs uppercase tracking-wide text-slate-400">
                    User ID (slug)
                  </label>
                  <input
                    id="onboard-user-id"
                    ref={firstFieldRef}
                    value={userId}
                    onChange={(event) => {
                      setUserId(coerceSlug(event.target.value));
                      setError(null);
                    }}
                    placeholder="demo_member"
                    className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-2 text-sm focus:border-cyan-400 focus:outline-none"
                    autoComplete="off"
                    required
                    aria-invalid={Boolean(slugError)}
                  />
                  {slugError ? <p className="mt-1 text-xs text-rose-300">{slugError}</p> : null}
                </div>
                <div>
                  <label htmlFor="onboard-user-label" className="text-xs uppercase tracking-wide text-slate-400">
                    Display name (optional)
                  </label>
                  <input
                    id="onboard-user-label"
                    value={label}
                    onChange={(event) => setLabel(event.target.value)}
                    placeholder="Demo Member"
                    className="mt-1 w-full rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-2 text-sm focus:border-cyan-400 focus:outline-none"
                    autoComplete="off"
                  />
                </div>
              </section>
            )}
          </div>
        );
      case 'trust':
        return (
          <div className="space-y-5">
            <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
              <h3 className="text-sm font-semibold text-slate-100">Trust & privacy</h3>
              <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-200">
                <li>You choose what to share and can change it anytime.</li>
                <li>Everything stays inside this workspace.</li>
                <li>Updates get a timestamp so the trail stays clear.</li>
                <li>Need a break? Ask Head Coach to pause nudges.</li>
              </ul>
            </section>
            <p className="text-xs text-slate-400">Optional: set the starting tone before we capture quick facts.</p>
            {renderSeedSection()}
          </div>
        );
      case 'quickFacts':
        return (
          <div className="space-y-4">
            <p className="text-xs text-slate-500">Grab a quick detail for each line so Head Coach can greet them like they belong.</p>
            <div className="grid gap-4">
              {(Object.keys(QUICK_FACT_OPTIONS) as QuickFactKey[]).map(renderQuickFactSection)}
            </div>
          </div>
        );
      case 'interests':
        return (
          <div className="space-y-4">
            <p className="text-xs text-slate-500">Tap what lights them up. Add your own words if it’s not listed.</p>
            <div className="flex flex-wrap gap-2">
              {INTEREST_OPTIONS.map((option) => {
                const selected = selectedInterests.includes(option.value);
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => toggleInterest(option)}
                    className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                      selected
                        ? 'bg-cyan-500 text-slate-950'
                        : 'border border-slate-600 bg-slate-900 text-slate-200 hover:border-cyan-400 hover:text-cyan-200'
                    }`}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
              <label htmlFor="custom-interest" className="text-xs uppercase tracking-wide text-slate-400">
                Add custom interest
              </label>
              <div className="mt-2 flex gap-2">
                <input
                  id="custom-interest"
                  type="text"
                  value={customInterestInput}
                  onChange={(event) => setCustomInterestInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      addCustomInterest();
                    }
                  }}
                  placeholder="Nutrition, Public speaking…"
                  className="flex-1 rounded-2xl border border-slate-700 bg-slate-950/70 px-3 py-2 text-sm focus:border-cyan-400 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={addCustomInterest}
                  className="rounded-full bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400"
                >
                  Add
                </button>
              </div>
              {customInterests.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {customInterests.map((entry) => (
                    <button
                      key={entry}
                      type="button"
                      onClick={() => removeCustomInterest(entry)}
                      className="rounded-full border border-slate-600 bg-slate-900 px-3 py-1 text-xs text-slate-200 hover:border-rose-400 hover:text-rose-200"
                    >
                      {entry}
                      <span className="ml-2 text-rose-300">×</span>
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        );
      case 'review':
        return (
          <div className="space-y-4">
            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
              <h3 className="text-sm font-semibold text-slate-100">Review</h3>
              <dl className="mt-3 space-y-2 text-sm text-slate-200">
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">User</dt>
                  <dd className="text-right">
                    <div className="font-semibold">{resolvedDisplayName}</div>
                    <div className="text-xs text-slate-500">{resolvedUserId}</div>
                  </dd>
                </div>
                {seedEnabled ? (
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-400">Big Five seed</dt>
                    <dd className="text-right text-xs text-slate-300">
                      {(['O', 'C', 'E', 'A', 'N'] as const)
                        .map((trait) => `${SLIDER_LABELS[trait]} ${Math.round(seed[trait] * 100)}`)
                        .join(', ')}
                    </dd>
                  </div>
                ) : (
                  <div className="flex justify-between gap-4">
                    <dt className="text-slate-400">Big Five seed</dt>
                    <dd className="text-right text-xs text-slate-300">Balanced default</dd>
                  </div>
                )}
                {(Object.keys(quickFacts) as QuickFactKey[]).map((key) => {
                  const state = quickFacts[key];
                  const config = QUICK_FACT_OPTIONS[key];
                  let display = state.label;
                  if (state.value === 'other' && state.custom.trim()) {
                    display = state.custom.trim();
                  }
                  return (
                    <div key={key} className="flex justify-between gap-4">
                      <dt className="text-slate-400">{config.label}</dt>
                      <dd className="text-right text-xs text-slate-300">{display || '—'}</dd>
                    </div>
                  );
                })}
                <div className="flex justify-between gap-4">
                  <dt className="text-slate-400">Interests</dt>
                  <dd className="text-right text-xs text-slate-300">
                    {resolvedInterestsLabels.length ? resolvedInterestsLabels.join(', ') : '—'}
                  </dd>
                </div>
              </dl>
            </div>
            <p className="text-xs text-slate-500">Looks good? Start coaching. Adjust anything later.</p>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 backdrop-blur-sm">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboard-title"
        aria-describedby="onboard-desc onboard-status-live"
        tabIndex={-1}
        className="w-full max-w-3xl rounded-3xl border border-slate-800 bg-slate-900 p-6 text-slate-100 shadow-2xl"
      >
        <header className="flex items-start justify-between">
          <div>
            <h2 id="onboard-title" className="text-lg font-semibold">
              Onboard user
            </h2>
            <p id="onboard-desc" className="text-sm text-slate-400">
              Share a few basics so Head Coach can greet them with context.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full bg-slate-800 px-3 py-1 text-sm text-slate-300 hover:bg-slate-700"
            aria-label="Close onboarding"
          >
            Close
          </button>
        </header>

        {pathChoice === 'undecided' ? (
          <section className="mt-6 space-y-6">
            <p className="text-sm text-slate-300">Pick the launch path that fits the moment.</p>
            <div className="grid gap-4 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => {
                  setPathChoice('smart');
                  setSeedEnabled(false);
                  setStep(0);
                  setLiveStatus('Smart defaults selected. First, choose or create a user.');
                  requestAnimationFrame(() => {
                    firstFieldRef.current?.focus();
                  });
                }}
                className="rounded-3xl border border-cyan-500/30 bg-cyan-500/10 p-6 text-left transition hover:border-cyan-400 hover:bg-cyan-500/20"
              >
                <h3 className="text-base font-semibold text-cyan-100">Smart defaults</h3>
                <p className="mt-3 text-sm text-cyan-200">Balanced start. Choose a user, add quick facts, and jump in.</p>
              </button>
              <button
                type="button"
                onClick={() => {
                  setPathChoice('trust');
                  setSeedEnabled(true);
                  setStep(0);
                  setLiveStatus('Trust & privacy walkthrough selected. First, choose or create a user.');
                  requestAnimationFrame(() => {
                    firstFieldRef.current?.focus();
                  });
                }}
                className="rounded-3xl border border-slate-700 bg-slate-950/60 p-6 text-left transition hover:border-cyan-400 hover:bg-slate-900"
              >
                <h3 className="text-base font-semibold text-slate-100">Trust & privacy first</h3>
                <p className="mt-3 text-sm text-slate-300">Review the trust basics, then gather the same quick facts and interests.</p>
              </button>
            </div>
          </section>
        ) : null}

        {pathChoice !== 'undecided' && stepConfig.length ? (
          <>
            <nav className="mt-4 flex flex-wrap items-center gap-2 text-xs uppercase tracking-wide text-slate-500">
              {stepConfig.map((config, index) => (
                <span
                  key={config.key}
                  className={`rounded-full px-2 py-1 ${
                    step === index ? 'bg-cyan-500/20 text-cyan-200' : 'bg-slate-800 text-slate-500'
                  }`}
                >
                  {config.label}
                </span>
              ))}
            </nav>

            <form
              className="mt-6 space-y-6"
              onSubmit={(event) => {
                event.preventDefault();
                if (step < stepConfig.length - 1) {
                  handleNext();
                } else {
                  void handleFinish();
                }
              }}
            >
              {renderStepContent(stepConfig[step]?.key)}

              {error ? <p className="text-sm text-rose-300">{error}</p> : null}

              <footer className="flex items-center justify-between">
                <div className="text-xs text-slate-500">
                  Step {step + 1} of {stepConfig.length}
                </div>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={handleBack}
                    className="rounded-full border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:border-cyan-400 hover:text-cyan-200 disabled:opacity-40"
                    disabled={step === 0 || pending}
                  >
                    Back
                  </button>
                  <button
                    type="submit"
                    className="rounded-full bg-cyan-500 px-6 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-40"
                    disabled={!canContinue}
                    aria-busy={pending}
                  >
                    {step === stepConfig.length - 1 ? (pending ? 'Saving…' : 'Start coaching') : 'Next'}
                  </button>
                </div>
              </footer>
            </form>

            {initNotice.status === 'pending' ? (
              <div
                className="mt-4 rounded-2xl border border-cyan-500/40 bg-cyan-500/10 px-4 py-3 text-xs text-cyan-100"
                role="status"
                aria-live="polite"
              >
                Setting up user containers…
              </div>
            ) : null}
            {initNotice.status === 'done' ? (
              <div
                className="mt-4 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-xs text-emerald-100"
                role="status"
                aria-live="polite"
              >
                Onboarding completed. Containers ready to use.
              </div>
            ) : null}
            {initNotice.status === 'error' ? (
              <div
                className="mt-4 flex flex-wrap items-center gap-3 rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-xs text-rose-100"
                role="alert"
              >
                <span>
                  Failed to initialize user containers. {initNotice.message ?? 'Try again when ready.'}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    if (initNotice.userId && initNotice.scriptPath) {
                      triggerInit({
                        user: initNotice.userId,
                        displayName: initNotice.label,
                        scriptPath: initNotice.scriptPath,
                        quickFacts: { ...initNotice.quickFacts },
                        interests: {
                          selected: [...(initNotice.interests.selected ?? [])],
                          custom: [...(initNotice.interests.custom ?? [])]
                        },
                        seedUsed: Boolean(initNotice.seedUsed)
                      });
                    }
                  }}
                  className="rounded-full border border-rose-300 px-3 py-1 text-xs font-semibold text-rose-100 hover:border-rose-100 hover:text-rose-50"
                >
                  Retry setup
                </button>
              </div>
            ) : null}
          </>
        ) : null}

        <div id="onboard-status-live" className="sr-only" aria-live="polite" aria-atomic="true">
          {liveStatus}
        </div>
      </div>
    </div>
  );
}

const SLIDER_LABELS: Record<'O' | 'C' | 'E' | 'A' | 'N', string> = {
  O: 'Openness',
  C: 'Conscientiousness',
  E: 'Extraversion',
  A: 'Agreeableness',
  N: 'Neuroticism'
};

function buildQuickFactsPayload(
  quickFacts: Record<QuickFactKey, QuickFactState>
): SubmitOnboardingRequest['quickFacts'] {
  const payload: SubmitOnboardingRequest['quickFacts'] = {};
  (Object.keys(quickFacts) as QuickFactKey[]).forEach((key) => {
    const config = QUICK_FACT_OPTIONS[key];
    const state = quickFacts[key];
    if (!state.value) {
      return;
    }
    const factPayload: OnboardingFactPayload = {};
    if (state.value) {
      factPayload.value = state.value;
    }
    if (state.value !== 'other' && state.label) {
      factPayload.label = state.label;
    }
    if (state.value === 'other' && state.custom.trim()) {
      factPayload.custom = state.custom.trim();
    }
    payload[config.apiKey] = factPayload;
  });
  return payload;
}

function coerceSlug(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9_-]/g, '_')
    .replace(/_{2,}/g, '_')
    .slice(0, 40);
}

function validateUserId(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return 'User id required.';
  }
  if (trimmed.length < 3) {
    return 'Use at least 3 characters.';
  }
  if (!/^[-_a-z0-9]+$/.test(trimmed)) {
    return 'Only lowercase letters, numbers, - and _ are allowed.';
  }
  return null;
}

function describeError(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  if (typeof error === 'string') {
    return error;
  }
  return 'Something went wrong. Please try again.';
}
