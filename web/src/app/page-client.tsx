'use client';

import { useCallback, useEffect, useMemo, useRef, useState, ChangeEvent, Profiler } from 'react';
import type { ReactNode, RefObject, ProfilerOnRenderCallback } from 'react';
import Link from 'next/link';
import type { Route } from 'next';
import { useRouter, useSearchParams } from 'next/navigation';
import { PersonaRail, DEFAULT_CANONICAL_PERSONAS } from '../components/persona-rail';
import { TranscriptPanel, type TranscriptPanelHandle } from '../components/transcript-panel';
import { ChatComposer, type ChatComposerHandle } from '../components/chat-composer';
import { UploadDrawerProvider } from '../components/upload-drawer';
import { CoachAsksPanel } from '../components/coach-asks-panel';
import { ObservationSummary } from '../components/observation-summary';
import { UnabridgedPanel } from '../components/unabridged-panel';
import { RRDnaPanel } from '../components/rr-dna-panel';
import { PanelError } from '../components/panel-error';
import { NudgeInboxPanel } from '../components/nudge-inbox-panel';
import { TimelineDrawer } from '../components/timeline-drawer';
import { UserSwitcher } from '../components/user-switcher';
import { OnboardUserModal } from '../components/onboard-user-modal';
import { OnboardingWizard, type OnboardingData } from '../components/onboarding/onboarding-wizard';
import { AvatarRenderPanel } from '../components/rendering/avatar-render-panel';
import { PortraitRenderCard } from '../components/padna/portrait-render-card';
import { PhotoPanel } from '../components/photo/photo-panel';
import { HeadCoachToolbar } from '../components/head-coach/head-coach-toolbar';
import { DraftChatPanel } from '../components/draft-chat/draft-chat-panel';
import { SnapshotsPanel } from '../components/snapshots/snapshots-panel';
import { PanelBoundary } from '../components/panel-boundary';
import { MilestonesPanel } from '../components/milestones-panel';
import { SettingsModal } from '../components/settings-modal';
import ClientOnly from '../components/util/client-only';
import {
  actOnAsk,
  actOnNudge,
  fetchObservationAggregates,
  fetchPersonaRoster,
  fetchAsks,
  fetchNudges,
  fetchTraitTimeline,
  fetchUnabridged,
  fetchUsers,
  fetchCoreHealth,
  fetchUcnrrHealth,
  importUserBundle,
  importUsersBulk,
  isApiError,
  createSnapshotMetadata,
  fetchOnboardingStatus,
  submitOnboardingWizardData,
  createUser,
  type ImportUserResponse,
  type AskAction,
  type NudgeAction,
  type ObservationAggregates,
  type PersonaRosterEntry,
  type PlannerAsk,
  type TraitTimelineEntry,
  type NudgeItem,
  type UnabridgedSnapshot,
  type UserSummary
} from '../lib/api';
import { readCache, writeCache } from '../lib/offline-cache';
import { subscribePerfMetrics, type PerfMetricsSnapshot } from '../lib/perf-hud';
import { usePreferences } from '../hooks/use-preferences';
import { addRecentUser, getUserFromUrl, setUserInUrl } from '../lib/user-history';
import { CommandPalette, buildCommandPaletteActions, type CommandContext } from '../components/command-palette/command-palette';
import { I18nProvider, useI18n } from '../i18n/context';
import { MESSAGES, type MessageKey, type SupportedLocale } from '../i18n/messages';
import { IntroTour, type TourStep } from '../components/tour/intro-tour';
import { useTourState } from '../hooks/use-tour';
import { useShortcutManager } from '../hooks/use-shortcuts';
import { ShortcutCheatsheet } from '../components/shortcut-cheatsheet';
import { useCelebrationsAgent, type MilestoneItem } from '../agents/celebrations-agent';
import { LayoutSwitcher } from '../components/layout-switcher';
import { useFeatureFlags } from '../lib/feature-flags';
import { CoachToolsPane } from '../components/coach-tools-pane';
import { LifeOSChatPanel } from '../components/life-os-chat-panel';
import { CoachCatalogModal } from '../components/coach-catalog-modal';

const LOCAL_STORAGE_KEY = '_active_user_id';

const DEFAULT_USER_ID = 'TEST';

const WORKSPACE_LABEL = process.env.NEXT_PUBLIC_WORKSPACE_LABEL ?? 'Default workspace';
const WORKSPACE_LINK = process.env.NEXT_PUBLIC_CP_PROFILES_URL ?? '';
const WORKSPACE_ROOT_HINT = process.env.NEXT_PUBLIC_WORKSPACE_ROOT ?? '';
const CORE_DOWNLOAD_BASE = (process.env.NEXT_PUBLIC_CORE_API_BASE ?? '').replace(/\/$/, '');
const PROVENANCE_LAB_BASE = (process.env.NEXT_PUBLIC_PROVENANCE_LAB_URL ?? 'http://127.0.0.1:8501/?tab=provenance').trim();

const OBSERVATION_WINDOW_PRIORITY = ['session', '24h', '1h'] as const;
const USER_SWITCH_DEBOUNCE_MS = 180;

const CENTER_ROUTES = ['coach', 'draft', 'snapshots'] as const;
type CenterRoute = (typeof CENTER_ROUTES)[number];

const DEFAULT_CENTER_ROUTE: CenterRoute = 'coach';
const DEFAULT_PERSONA_KEY = 'head_coach';

function makeTranslator(locale: string) {
  const normalized = (locale in MESSAGES ? locale : 'en') as SupportedLocale;
  const messages = MESSAGES[normalized];
  const fallback = MESSAGES.en;
  return (key: MessageKey, replacements?: Record<string, string | number>) => {
    const template = messages[key] ?? fallback[key] ?? key;
    if (!replacements) {
      return template;
    }
    return Object.keys(replacements).reduce((acc, token) => {
      const pattern = new RegExp(`\\{${token}\\}`, 'g');
      return acc.replace(pattern, String(replacements[token] ?? ''));
    }, template);
  };
}

function pickObservationWindow(preferred: string | undefined, aggregates: ObservationAggregates): string {
  const windows = Object.keys(aggregates.windows ?? {});
  if (preferred && (preferred === 'all' || windows.includes(preferred))) {
    return preferred;
  }
  for (const key of OBSERVATION_WINDOW_PRIORITY) {
    if (windows.includes(key)) {
      return key;
    }
  }
  return windows[0] ?? 'all';
}

function normalizePersonaParam(value: string | null): string | null {
  if (!value) {
    return null;
  }
  const normalized = value.trim().toLowerCase();
  return normalized.length ? normalized : null;
}

function normalizeCenterParam(value: string | null): CenterRoute | null {
  if (!value) {
    return null;
  }
  const normalized = value.trim().toLowerCase();
  return CENTER_ROUTES.includes(normalized as CenterRoute) ? (normalized as CenterRoute) : null;
}

type NoticeTone = 'success' | 'info' | 'warning' | 'error';

interface Notice {
  id: number;
  text: string;
  tone: NoticeTone;
  linkHref?: string;
  linkLabel?: string;
}

export default function HeadCoachPage() {
  const { preferences, updatePreference, resetPreferences, hydrated: preferencesHydrated } = usePreferences();
  const { flags } = useFeatureFlags();
  const translate = useMemo(() => makeTranslator(preferences.locale), [preferences.locale]);
  const workspaceLabel = WORKSPACE_LABEL;
  const workspaceLink = WORKSPACE_LINK;
  const workspaceRootHint = WORKSPACE_ROOT_HINT;
  const coreApiConfigured = Boolean(process.env.NEXT_PUBLIC_CORE_API_BASE?.trim());
  const [personas, setPersonas] = useState<PersonaRosterEntry[]>([]);
  const [activePersona, setActivePersona] = useState<string>(DEFAULT_PERSONA_KEY);
  const [activeUser, setActiveUser] = useState<string>(DEFAULT_USER_ID);
  const [asks, setAsks] = useState<PlannerAsk[]>([]);
  const [nudges, setNudges] = useState<NudgeItem[]>([]);
  const [aggregates, setAggregates] = useState<ObservationAggregates | null>(null);
  const [observationWindow, setObservationWindow] = useState<string>('all');
  const [unabridged, setUnabridged] = useState<UnabridgedSnapshot | null>(null);
  const [personaError, setPersonaError] = useState<string | null>(null);
  const [asksError, setAsksError] = useState<string | null>(null);
  const [nudgeError, setNudgeError] = useState<string | null>(null);
  const [aggregatesError, setAggregatesError] = useState<string | null>(null);
  const [unabridgedError, setUnabridgedError] = useState<string | null>(null);
  const [asksLoading, setAsksLoading] = useState(false);
  const [nudgeLoading, setNudgeLoading] = useState(false);
  const [aggregatesLoading, setAggregatesLoading] = useState(false);
  const [unabridgedLoading, setUnabridgedLoading] = useState(false);
  const [askActionPending, setAskActionPending] = useState<Record<string, boolean>>({});
  const [askActionErrors, setAskActionErrors] = useState<Record<string, string | null>>({});
  const [nudgeActionPending, setNudgeActionPending] = useState<Record<string, boolean>>({});
  const [nudgeActionErrors, setNudgeActionErrors] = useState<Record<string, string | null>>({});
  const [timelineOpen, setTimelineOpen] = useState(false);
  const [timelineTraitId, setTimelineTraitId] = useState<string | null>(null);
  const [timelineEntries, setTimelineEntries] = useState<TraitTimelineEntry[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineError, setTimelineError] = useState<string | null>(null);
  const [quickSnapshotPending, setQuickSnapshotPending] = useState(false);
  const [snapshotRefreshToken, setSnapshotRefreshToken] = useState(0);
  const [padnaRefreshToken, setPadnaRefreshToken] = useState(0);
  const [transcriptResetToken, setTranscriptResetToken] = useState(0);
  const [centerView, setCenterView] = useState<CenterRoute>(DEFAULT_CENTER_ROUTE);
  const singleImportInputRef = useRef<HTMLInputElement | null>(null);
  const bulkImportInputRef = useRef<HTMLInputElement | null>(null);
  const healthPollRef = useRef<number | null>(null);
  const composerRef = useRef<ChatComposerHandle | null>(null);
  const [importPending, setImportPending] = useState(false);
  const [bulkImportPending, setBulkImportPending] = useState(false);
  const [activeUserLabel, setActiveUserLabel] = useState<string>('');
  const [userModalOpen, setUserModalOpen] = useState(false);
  const [proposedUserId, setProposedUserId] = useState('');
  const [userSwitchRefresh, setUserSwitchRefresh] = useState(0);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [onboardingWizardOpen, setOnboardingWizardOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [coachCatalogOpen, setCoachCatalogOpen] = useState(false);
  const [isMac, setIsMac] = useState(false);
  const { dismissed: tourDismissed, hydrated: tourHydrated, markDismissed: markTourDismissed } = useTourState();
  const [tourOpen, setTourOpen] = useState(false);
  const [tourSession, setTourSession] = useState(0);
  const tourAutoOpenedRef = useRef(false);
  const shortcutManager = useShortcutManager();
  const [cheatSheetOpen, setCheatSheetOpen] = useState(false);
  const [asksCached, setAsksCached] = useState(false);
  const [nudgesCached, setNudgesCached] = useState(false);
  const [snapshotsCached, setSnapshotsCached] = useState(false);
  const [perfEnabled, setPerfEnabled] = useState(false);
  const [fps, setFps] = useState(0);
  const [lastCommitDuration, setLastCommitDuration] = useState(0);
  const [coreHealth, setCoreHealth] = useState<{
    status: 'unknown' | 'online' | 'offline';
    lastChecked: number | null;
    retrying: boolean;
  }>({ status: 'unknown', lastChecked: null, retrying: false });
  const [curiosityHealth, setCuriosityHealth] = useState<{
    enabled: boolean | null;
    lastChecked: number | null;
    retrying: boolean;
  }>({ enabled: null, lastChecked: null, retrying: false });
  const [ucnrrHealth, setUcnrrHealth] = useState<{
    reachable: boolean | null;
    lastChecked: number | null;
    retrying: boolean;
  }>({ reachable: null, lastChecked: null, retrying: false });
  const [healthTick, setHealthTick] = useState(0);
  const [commitCount, setCommitCount] = useState(0);
  const [virtualizerMetrics, setVirtualizerMetrics] = useState<Record<string, { total: number; visible: number }>>({});
  const handleSnapshotsCachedChange = useCallback((cached: boolean) => {
    setSnapshotsCached(cached);
  }, []);

  const asksRef = useRef<PlannerAsk[]>(asks);
  const nudgesRef = useRef<NudgeItem[]>(nudges);

  useEffect(() => {
    asksRef.current = asks;
  }, [asks]);

  useEffect(() => {
    nudgesRef.current = nudges;
  }, [nudges]);

  const tourSteps = useMemo<TourStep[]>(
    () => [
      {
        id: 'tour-active-user',
        title: translate('tour.activeUser.title'),
        description: translate('tour.activeUser.description'),
        targetId: 'tour-user-switcher'
      },
      {
        id: 'tour-personas',
        title: translate('tour.personas.title'),
        description: translate('tour.personas.description'),
        targetId: 'tour-persona-rail'
      },
      {
        id: 'tour-views',
        title: translate('tour.views.title'),
        description: translate('tour.views.description'),
        targetId: 'tour-center-tabs'
      },
      {
        id: 'tour-toolbar',
        title: translate('tour.toolbar.title'),
        description: translate('tour.toolbar.description'),
        targetId: 'tour-toolbar'
      },
      {
        id: 'tour-composer',
        title: translate('tour.composer.title'),
        description: translate('tour.composer.description'),
        targetId: 'tour-composer'
      }
    ],
    [translate]
  );

  const openTourFromHelp = useCallback(() => {
    setTourSession((prev) => prev + 1);
    setTourOpen(true);
  }, []);

  const handleTourClose = useCallback(
    (dismiss: boolean) => {
      setTourOpen(false);
      if (dismiss) {
        markTourDismissed();
      }
    },
    [markTourDismissed]
  );
  const searchParams = useSearchParams();
  const router = useRouter();
  const debugEnabled = searchParams?.get('ui_debug') === '1';
  const activeUserRef = useRef(activeUser);
  const noticeTimerRef = useRef<number | null>(null);
  const observationWindowPinnedRef = useRef(false);
  const initialHydratedRef = useRef(false);
  const userSelectionTimerRef = useRef<number | null>(null);
  const lastSyncedParamsRef = useRef<{
    user: string;
    persona: string;
    center: CenterRoute;
    tour: boolean;
  }>({
    user: '',
    persona: DEFAULT_PERSONA_KEY,
    center: DEFAULT_CENTER_ROUTE,
    tour: false,
  });
  const userSwitchInitialSyncRef = useRef(true);
  const transcriptRef = useRef<TranscriptPanelHandle | null>(null);
  const transcriptSearchRef = useRef<HTMLInputElement | null>(null);
  const userSwitcherInputRef = useRef<HTMLInputElement | null>(null);
  const quickSnapshotPendingRef = useRef(false);
  const perfFrameRef = useRef<number | null>(null);

  useEffect(() => {
    activeUserRef.current = activeUser;
  }, [activeUser]);

  useEffect(() => {
    if (typeof navigator !== 'undefined') {
      setIsMac(/mac/i.test(navigator.platform));
    }
  }, []);

  useEffect(() => {
    if (!coreApiConfigured) {
      setCoreHealth({ status: 'unknown', lastChecked: null, retrying: false });
      setCuriosityHealth({ enabled: null, lastChecked: null, retrying: false });
      setUcnrrHealth({ reachable: null, lastChecked: null, retrying: false });
      setHealthTick(0);
      if (healthPollRef.current != null) {
        window.clearTimeout(healthPollRef.current);
        healthPollRef.current = null;
      }
      return;
    }

    let cancelled = false;

    const poll = async () => {
      try {
        const result = await fetchCoreHealth();
        if (cancelled) {
          return;
        }
        setCoreHealth({
          status: result.ok ? 'online' : 'offline',
          lastChecked: result.ts,
          retrying: false
        });
        setCuriosityHealth({
          enabled: Boolean(result.curiosity_enabled),
          lastChecked: result.ts,
          retrying: false
        });

        // Also check UCN/RR health
        try {
          const ucnrrResult = await fetchUcnrrHealth();
          if (!cancelled) {
            setUcnrrHealth({
              reachable: ucnrrResult.reachable,
              lastChecked: Date.now(),
              retrying: false
            });
          }
        } catch (ucnrrError) {
          if (!cancelled) {
            setUcnrrHealth((prev) => ({
              reachable: prev.reachable,
              lastChecked: prev.lastChecked,
              retrying: true
            }));
          }
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        setCoreHealth((prev) => ({
          status: 'offline',
          lastChecked: prev.lastChecked,
          retrying: true
        }));
        setCuriosityHealth((prev) => ({
          enabled: prev.enabled,
          lastChecked: prev.lastChecked,
          retrying: true
        }));
        setUcnrrHealth((prev) => ({
          reachable: prev.reachable,
          lastChecked: prev.lastChecked,
          retrying: true
        }));
      } finally {
        if (!cancelled) {
          if (healthPollRef.current != null) {
            window.clearTimeout(healthPollRef.current);
          }
          healthPollRef.current = window.setTimeout(poll, 20000);
        }
      }
    };

    poll();

    return () => {
      cancelled = true;
      if (healthPollRef.current != null) {
        window.clearTimeout(healthPollRef.current);
        healthPollRef.current = null;
      }
    };
  }, [coreApiConfigured]);

  useEffect(() => {
    if (!tourHydrated || tourDismissed || tourAutoOpenedRef.current) {
      return;
    }
    tourAutoOpenedRef.current = true;
    setTourSession((prev) => prev + 1);
    setTourOpen(true);
  }, [tourHydrated, tourDismissed]);

  useEffect(() => {
    return () => {
      if (userSelectionTimerRef.current) {
        window.clearTimeout(userSelectionTimerRef.current);
        userSelectionTimerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!coreHealth.lastChecked && !curiosityHealth.lastChecked) {
      return;
    }
    const timer = window.setInterval(() => {
      setHealthTick((tick) => tick + 1);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [coreHealth.lastChecked, curiosityHealth.lastChecked]);

  const pushNotice = useCallback(
    (text: string, tone: NoticeTone = 'info', options?: { linkHref?: string; linkLabel?: string }) => {
      setNotice({ id: Date.now(), text, tone, linkHref: options?.linkHref, linkLabel: options?.linkLabel });
    },
    [actOnAsk]
  );

  const { milestones, clearMilestone, clearAllMilestones } = useCelebrationsAgent({
    activeUserId: activeUser,
    asks,
    unabridged,
    onNotify: pushNotice,
  });

  useEffect(() => {
    if (!coreApiConfigured) {
      pushNotice(translate('notice.coreMissingBase'), 'warning');
    }
  }, [coreApiConfigured, pushNotice, translate]);

  const focusUserSwitcher = useCallback(() => {
    const node = userSwitcherInputRef.current;
    if (!node) {
      return false;
    }
    node.focus();
    if (typeof node.select === 'function') {
      node.select();
    }
    return true;
  }, []);

  const focusTranscriptSearch = useCallback(() => {
    const node = transcriptSearchRef.current;
    if (!node) {
      return false;
    }
    node.focus();
    if (typeof node.select === 'function') {
      node.select();
    }
    return true;
  }, []);

  const toggleFocusedPin = useCallback(() => {
    if (settingsOpen || userModalOpen || cheatSheetOpen) {
      return;
    }
    if (centerView !== 'coach') {
      pushNotice(translate('notice.pinSwitchView'), 'info');
      return;
    }
    const result = transcriptRef.current?.togglePinFocused() ?? null;
    if (result === 'pinned') {
      pushNotice(translate('notice.pinAdded'), 'success');
    } else if (result === 'unpinned') {
      pushNotice(translate('notice.pinRemoved'), 'info');
    } else {
      pushNotice(translate('notice.pinFocusInstruction'), 'warning');
    }
  }, [centerView, cheatSheetOpen, pushNotice, settingsOpen, translate, userModalOpen]);

  const toggleCompactDensity = useCallback(() => {
    const next = !preferences.compactDensity;
    updatePreference({ compactDensity: next });
    pushNotice(next ? translate('notice.compactOn') : translate('notice.compactOff'), 'info');
  }, [preferences.compactDensity, pushNotice, translate, updatePreference]);

  const toggleStreamingPreference = useCallback(() => {
    const next = !preferences.streaming;
    updatePreference({ streaming: next });
    pushNotice(next ? translate('notice.streamingOn') : translate('notice.streamingOff'), 'info');
  }, [preferences.streaming, pushNotice, translate, updatePreference]);

  const openCommandPaletteShortcut = useCallback(() => {
    if (cheatSheetOpen) {
      setCheatSheetOpen(false);
    }
    if (settingsOpen || userModalOpen || commandOpen) {
      return;
    }
    setCommandOpen(true);
  }, [cheatSheetOpen, commandOpen, settingsOpen, userModalOpen]);

  const openSettingsShortcut = useCallback(() => {
    if (cheatSheetOpen) {
      setCheatSheetOpen(false);
    }
    if (userModalOpen) {
      return;
    }
    setSettingsOpen(true);
  }, [cheatSheetOpen, userModalOpen]);

  const toggleSettingsShortcut = useCallback(() => {
    if (userModalOpen) {
      return;
    }
    if (cheatSheetOpen) {
      setCheatSheetOpen(false);
    }
    setSettingsOpen((prev) => !prev);
  }, [cheatSheetOpen, userModalOpen]);

  const focusSearchShortcut = useCallback(() => {
    if (cheatSheetOpen) {
      setCheatSheetOpen(false);
    }
    if (settingsOpen || userModalOpen) {
      return;
    }
    if (!focusTranscriptSearch()) {
      pushNotice(translate('notice.openTranscriptFirst'), 'warning');
    }
  }, [cheatSheetOpen, focusTranscriptSearch, pushNotice, settingsOpen, translate, userModalOpen]);

  const centerDraftShortcut = useCallback(() => {
    if (cheatSheetOpen) {
      setCheatSheetOpen(false);
    }
    if (settingsOpen || userModalOpen) {
      return;
    }
    setCenterView('draft');
  }, [cheatSheetOpen, settingsOpen, setCenterView, userModalOpen]);

  const centerSnapshotsShortcut = useCallback(() => {
    if (cheatSheetOpen) {
      setCheatSheetOpen(false);
    }
    if (settingsOpen || userModalOpen) {
      return;
    }
    setCenterView('snapshots');
  }, [cheatSheetOpen, settingsOpen, setCenterView, userModalOpen]);

  const openCheatSheetShortcut = useCallback(() => {
    if (!cheatSheetOpen) {
      setCheatSheetOpen(true);
    }
  }, [cheatSheetOpen]);

  async function handleQuickSnapshot() {
    const currentUser = activeUserRef.current.trim();
    if (!currentUser) {
      pushNotice(translate('notice.snapshotNeedsUser'), 'warning');
      return;
    }
    if (quickSnapshotPendingRef.current) {
      return;
    }
    quickSnapshotPendingRef.current = true;
    setQuickSnapshotPending(true);
    try {
      const result = await createSnapshotMetadata(currentUser);
      if (!result.ok) {
        pushNotice(translate('notice.snapshotFailed'), 'error');
        return;
      }
      setSnapshotRefreshToken((token) => token + 1);
      let noticeOptions: { linkHref?: string; linkLabel?: string } | undefined;
      if (PROVENANCE_LAB_BASE && result.filename) {
        const separator = PROVENANCE_LAB_BASE.includes('?') ? '&' : '?';
        const provenanceLink = `${PROVENANCE_LAB_BASE}${separator}user_id=${encodeURIComponent(currentUser)}&snapshot=${encodeURIComponent(result.filename)}`;
        noticeOptions = { linkHref: provenanceLink, linkLabel: translate('notice.link.provenanceLab') };
      } else if (result.download_url && CORE_DOWNLOAD_BASE) {
        noticeOptions = {
          linkHref: `${CORE_DOWNLOAD_BASE}${result.download_url}`,
          linkLabel: translate('notice.link.downloadSnapshot')
        };
      }
      const snapshotMessage = result.version
        ? translate('notice.snapshotSavedVersion', { version: result.version })
        : translate('notice.snapshotSaved');
      pushNotice(snapshotMessage, 'success', noticeOptions);
    } catch (err) {
      pushNotice(describeError(err), 'error');
    } finally {
      quickSnapshotPendingRef.current = false;
      setQuickSnapshotPending(false);
    }
  }

  const coreRelativeSeconds = useMemo(() => {
    if (!coreHealth.lastChecked) {
      return null;
    }
    return Math.max(0, Math.round((Date.now() - coreHealth.lastChecked) / 1000));
  }, [coreHealth.lastChecked, healthTick]);

  const curiosityRelativeSeconds = useMemo(() => {
    if (!curiosityHealth.lastChecked) {
      return null;
    }
    return Math.max(0, Math.round((Date.now() - curiosityHealth.lastChecked) / 1000));
  }, [curiosityHealth.lastChecked, healthTick]);

  const coreBadgeTone: StatusLightState = coreApiConfigured ? coreHealth.status : 'unknown';
  const coreBadgeDescription = coreApiConfigured
    ? coreHealth.status === 'online'
      ? 'Online'
      : coreHealth.status === 'offline'
      ? coreHealth.retrying
        ? 'Offline (retrying…)'
        : 'Offline'
      : 'Checking…'
    : 'Unavailable';
  const coreBadgeTooltip = coreApiConfigured
    ? (() => {
        if (coreHealth.status === 'online') {
          const lastCheckedText = coreRelativeSeconds != null ? ` (last checked ${coreRelativeSeconds}s ago)` : '';
          return `Core: Online${lastCheckedText}`;
        }
        if (coreHealth.status === 'offline') {
          const retryText = coreHealth.retrying ? ' (retrying…)' : '';
          const lastCheckedText = coreRelativeSeconds != null ? ` (last checked ${coreRelativeSeconds}s ago)` : '';
          return `Core: Offline${retryText}${lastCheckedText}`;
        }
        return 'Core: Checking…';
      })()
    : 'Core API not configured.';

  const curiosityBadgeTone: StatusLightState = coreApiConfigured
    ? curiosityHealth.enabled === null
      ? 'unknown'
      : curiosityHealth.enabled
      ? 'online'
      : 'offline'
    : 'unknown';
  const curiosityBadgeDescription = coreApiConfigured
    ? curiosityHealth.enabled === null
      ? 'Checking…'
      : curiosityHealth.enabled
      ? 'Enabled'
      : curiosityHealth.retrying
      ? 'Disabled (retrying…)'
      : 'Disabled'
    : 'Unavailable';
  const curiosityBadgeTooltip = coreApiConfigured
    ? curiosityHealth.enabled === null
      ? 'Curiosity: Checking…'
      : (() => {
          const base = curiosityHealth.enabled ? 'Curiosity: Enabled' : 'Curiosity: Disabled';
          const retryText = !curiosityHealth.enabled && curiosityHealth.retrying ? ' (retrying…)' : '';
          const lastCheckedText = curiosityRelativeSeconds != null ? ` (last checked ${curiosityRelativeSeconds}s ago)` : '';
          return `${base}${retryText}${lastCheckedText}`;
        })()
    : 'Curiosity status unavailable.';

  const ucnrrRelativeSeconds = useMemo(() => {
    if (!ucnrrHealth.lastChecked) {
      return null;
    }
    return Math.max(0, Math.round((Date.now() - ucnrrHealth.lastChecked) / 1000));
  }, [ucnrrHealth.lastChecked, healthTick]);

  const ucnrrBadgeTone: StatusLightState = coreApiConfigured
    ? ucnrrHealth.reachable === null
      ? 'unknown'
      : ucnrrHealth.reachable
      ? 'online'
      : 'offline'
    : 'unknown';
  const ucnrrBadgeDescription = coreApiConfigured
    ? ucnrrHealth.reachable === null
      ? 'Checking…'
      : ucnrrHealth.reachable
      ? 'Online'
      : ucnrrHealth.retrying
      ? 'Offline (retrying…)'
      : 'Offline'
    : 'Unavailable';
  const ucnrrBadgeTooltip = coreApiConfigured
    ? ucnrrHealth.reachable === null
      ? 'UCN/RR: Checking…'
      : (() => {
          const base = ucnrrHealth.reachable ? 'UCN/RR: Online' : 'UCN/RR: Offline';
          const retryText = !ucnrrHealth.reachable && ucnrrHealth.retrying ? ' (retrying…)' : '';
          const lastCheckedText = ucnrrRelativeSeconds != null ? ` (last checked ${ucnrrRelativeSeconds}s ago)` : '';
          return `${base}${retryText}${lastCheckedText}`;
        })()
    : 'UCN/RR status unavailable.';

  const commandContext = useMemo<CommandContext>(
    () => ({
      focusUserSwitcher: () => {
        if (!focusUserSwitcher()) {
          pushNotice(translate('notice.userSwitcherUnavailable'), 'warning');
        }
      },
      openSettings: () => setSettingsOpen(true),
      openSnapshots: () => setCenterView('snapshots'),
      startTour: openTourFromHelp,
      quickSnapshot: () => {
        void handleQuickSnapshot();
      },
      focusTranscriptSearch: () => {
        if (!focusTranscriptSearch()) {
          pushNotice(translate('notice.openTranscriptFirst'), 'warning');
        }
      },
      toggleCompactDensity,
      toggleStreaming: toggleStreamingPreference,
      compactDensityEnabled: preferences.compactDensity,
      streamingEnabled: preferences.streaming,
    }),
    [
      focusTranscriptSearch,
      focusUserSwitcher,
      handleQuickSnapshot,
      openTourFromHelp,
      preferences.compactDensity,
      preferences.streaming,
      pushNotice,
      setCenterView,
      translate,
      toggleCompactDensity,
      toggleStreamingPreference,
      setSettingsOpen,
    ]
  );

  const commandActions = useMemo(
    () => buildCommandPaletteActions(commandContext, translate),
    [commandContext, translate]
  );

  const commandPaletteText = useMemo(
    () => ({
      placeholder: translate('commandPalette.searchPlaceholder'),
      ariaLabel: translate('commandPalette.ariaLabel'),
      empty: translate('commandPalette.noResults'),
    }),
    [translate]
  );

  const handleProfileRender = useCallback<ProfilerOnRenderCallback>(
    (
      _id,
      _phase,
      actualDuration,
      _baseDuration,
      _startTime,
      _commitTime,
      _interactions
    ) => {
      if (!perfEnabled) {
        return;
      }
      const rounded = Number(actualDuration.toFixed(2));
      setLastCommitDuration(rounded);
      setCommitCount((prev) => prev + 1);
    },
    [perfEnabled]
  );

  useEffect(() => {
    const shortcuts = [
      { combo: 'cmd+,', description: 'Open settings', run: openSettingsShortcut, group: 'Navigation' },
      { combo: 'ctrl+,', description: 'Open settings', run: openSettingsShortcut, group: 'Navigation' },
      { combo: 'cmd+k', description: 'Open command palette', run: openCommandPaletteShortcut, group: 'Navigation' },
      { combo: 'ctrl+k', description: 'Open command palette', run: openCommandPaletteShortcut, group: 'Navigation' },
      { combo: 'shift+f', description: 'Focus transcript search', run: focusSearchShortcut, group: 'Navigation' },
      { combo: 's', description: 'Toggle settings', run: toggleSettingsShortcut, group: 'View' },
      { combo: 'd', description: 'Show draft chat view', run: centerDraftShortcut, group: 'Navigation' },
      { combo: 'g', description: 'Show snapshots view', run: centerSnapshotsShortcut, group: 'Navigation' },
      { combo: 'p', description: 'Toggle transcript pin', run: toggleFocusedPin, group: 'Actions' },
      { combo: 'cmd+/', description: 'Show shortcut cheat sheet', run: openCheatSheetShortcut, group: 'Help' },
      { combo: 'ctrl+/', description: 'Show shortcut cheat sheet', run: openCheatSheetShortcut, group: 'Help' }
    ];
    const cleanup = shortcutManager.registerMany(shortcuts);
    return cleanup;
  }, [
    centerDraftShortcut,
    centerSnapshotsShortcut,
    focusSearchShortcut,
    openCheatSheetShortcut,
    openCommandPaletteShortcut,
    openSettingsShortcut,
    shortcutManager,
    toggleFocusedPin,
    toggleSettingsShortcut
  ]);

  useEffect(() => {
    if (!notice) {
      return;
    }
    if (noticeTimerRef.current) {
      window.clearTimeout(noticeTimerRef.current);
    }
    noticeTimerRef.current = window.setTimeout(() => {
      setNotice(null);
      noticeTimerRef.current = null;
    }, 4000);
    return () => {
      if (noticeTimerRef.current) {
        window.clearTimeout(noticeTimerRef.current);
        noticeTimerRef.current = null;
      }
    };
  }, [notice]);

  useEffect(() => {
    if (commandOpen && (settingsOpen || userModalOpen)) {
      setCommandOpen(false);
    }
  }, [commandOpen, settingsOpen, userModalOpen]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const readPerfFlag = () => window.localStorage.getItem('_hc_perf') === '1';
    const syncFlag = () => {
      const next = readPerfFlag();
      setPerfEnabled((prev) => (prev === next ? prev : next));
    };
    syncFlag();
    const handleStorage = (event: StorageEvent) => {
      if (event.key === '_hc_perf') {
        const next = event.newValue === '1';
        setPerfEnabled((prev) => (prev === next ? prev : next));
      }
    };
    window.addEventListener('storage', handleStorage);
    const interval = window.setInterval(syncFlag, 1500);
    return () => {
      window.removeEventListener('storage', handleStorage);
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (!perfEnabled) {
      setFps(0);
      setVirtualizerMetrics({});
      return;
    }
    setCommitCount(0);
    setLastCommitDuration(0);
  }, [perfEnabled]);

  useEffect(() => {
    if (!perfEnabled) {
      return;
    }
    const unsubscribe = subscribePerfMetrics((snapshot: PerfMetricsSnapshot) => {
      setVirtualizerMetrics(snapshot.virtualizers);
    });
    return () => {
      unsubscribe();
    };
  }, [perfEnabled]);

  useEffect(() => {
    if (!perfEnabled || typeof window === 'undefined') {
      return;
    }
    let lastTimestamp = performance.now();
    let frameCount = 0;

    const step = (timestamp: number) => {
      frameCount += 1;
      const delta = timestamp - lastTimestamp;
      if (delta >= 500) {
        const nextFps = Math.round((frameCount * 1000) / delta);
        setFps((prev) => (prev === nextFps ? prev : nextFps));
        frameCount = 0;
        lastTimestamp = timestamp;
      }
      perfFrameRef.current = window.requestAnimationFrame(step);
    };

    perfFrameRef.current = window.requestAnimationFrame(step);

    return () => {
      if (perfFrameRef.current != null) {
        window.cancelAnimationFrame(perfFrameRef.current);
        perfFrameRef.current = null;
      }
    };
  }, [perfEnabled]);

  const loadPersonas = useCallback(async () => {
    try {
      const roster = await fetchPersonaRoster();
      setPersonas(roster);
      setPersonaError(null);
      setActivePersona((current) => {
        if (roster.some((item) => item.key === current && item.enabled)) {
          return current;
        }
        const firstEnabled = roster.find((item) => item.enabled) ?? roster[0];
        return firstEnabled ? firstEnabled.key : current;
      });
    } catch (fetchErr) {
      console.warn('failed to load personas', fetchErr);
      setPersonaError(describeError(fetchErr));
    }
  }, []);

  const loadAsks = useCallback(
    async (userId: string, options?: { reset?: boolean }) => {
      const target = userId.trim();
      if (!target) {
        setAsks([]);
        setAsksError(null);
        setAsksLoading(false);
        setAsksCached(false);
        return;
      }
      if (options?.reset) {
        setAsks([]);
        setAsksCached(false);
      }
      setAsksLoading(true);
      setAsksError(null);
      try {
        const askPayload = await fetchAsks(target, { limit: 5 });
        if (activeUserRef.current === target) {
          setAsks(askPayload);
          setAsksError(null);
          setAsksCached(false);
          writeCache('asks', target, askPayload);
        }
      } catch (err) {
        if (activeUserRef.current === target) {
          const cachedPayload = readCache<PlannerAsk[]>('asks', target);
          if (cachedPayload !== null) {
            setAsks(cachedPayload);
            setAsksError(null);
            setAsksCached(true);
          } else {
            console.warn('failed to load planner asks', err);
            setAsks([]);
            setAsksError(describeError(err));
            setAsksCached(false);
          }
        }
      } finally {
        if (activeUserRef.current === target) {
          setAsksLoading(false);
        }
      }
    },
    []
  );

  const loadNudges = useCallback(
    async (userId: string, options?: { reset?: boolean }) => {
      const target = userId.trim();
      if (!target) {
        setNudges([]);
        setNudgeError(null);
        setNudgeLoading(false);
        setNudgesCached(false);
        return;
      }
      if (options?.reset) {
        setNudges([]);
        setNudgesCached(false);
      }
      setNudgeLoading(true);
      setNudgeError(null);
      try {
        const nudgesPayload = await fetchNudges(target, { limit: 50 });
        if (activeUserRef.current === target) {
          setNudges(nudgesPayload);
          setNudgeError(null);
          setNudgesCached(false);
          writeCache('nudges', target, nudgesPayload);
        }
      } catch (err) {
        if (activeUserRef.current === target) {
          const cachedPayload = readCache<NudgeItem[]>('nudges', target);
          if (cachedPayload !== null) {
            setNudges(cachedPayload);
            setNudgeError(null);
            setNudgesCached(true);
          } else {
            console.warn('failed to load nudges', err);
            setNudges([]);
            setNudgeError(describeError(err));
            setNudgesCached(false);
          }
        }
      } finally {
        if (activeUserRef.current === target) {
          setNudgeLoading(false);
        }
      }
    },
    []
  );

  const loadAggregates = useCallback(
    async (userId: string, options?: { reset?: boolean }) => {
      const target = userId.trim();
      if (!target) {
        setAggregates(null);
        setAggregatesError(null);
        setAggregatesLoading(false);
        setObservationWindow('all');
        observationWindowPinnedRef.current = false;
        return;
      }
      if (options?.reset) {
        setAggregates(null);
        setObservationWindow('all');
        observationWindowPinnedRef.current = false;
      }
      setAggregatesLoading(true);
      setAggregatesError(null);
      try {
        const aggregatesPayload = await fetchObservationAggregates(target);
        if (activeUserRef.current === target) {
          setAggregates(aggregatesPayload);
          setObservationWindow((current) =>
            pickObservationWindow(
              observationWindowPinnedRef.current ? current : undefined,
              aggregatesPayload,
            ),
          );
        }
      } catch (err) {
        console.warn('failed to load observation aggregates', err);
        if (activeUserRef.current === target) {
          setAggregatesError(describeError(err));
        }
      } finally {
        if (activeUserRef.current === target) {
          setAggregatesLoading(false);
        }
      }
    },
    []
  );

  // NORTHSTAR PHASE 2: Unabridged auto-refreshes when Core snapshot updates
  // After ingestion → Core stores traits → refreshSnapshot() → refreshAllPanels() → loadUnabridged()
  const loadUnabridged = useCallback(
    async (userId: string, options?: { reset?: boolean }) => {
      const target = userId.trim();
      if (!target) {
        setUnabridged(null);
        setUnabridgedError(null);
        setUnabridgedLoading(false);
        return;
      }
      if (options?.reset) {
        setUnabridged(null);
      }
      setUnabridgedLoading(true);
      setUnabridgedError(null);
      try {
        const unabridgedPayload = await fetchUnabridged(target);
        if (activeUserRef.current === target) {
          setUnabridged(unabridgedPayload);
        }
      } catch (err) {
        console.warn('failed to load unabridged snapshot', err);
        if (activeUserRef.current === target) {
          setUnabridgedError(describeError(err));
        }
      } finally {
        if (activeUserRef.current === target) {
          setUnabridgedLoading(false);
        }
      }
    },
    []
  );

  useEffect(() => {
    if (typeof window === 'undefined' || initialHydratedRef.current) {
      return;
    }
    initialHydratedRef.current = true;
    const url = new URL(window.location.href);
    const paramUser = getUserFromUrl()?.trim() ?? '';
    const stored = window.localStorage.getItem(LOCAL_STORAGE_KEY)?.trim() ?? '';
    const initialUser = paramUser || stored || activeUser || DEFAULT_USER_ID;
    if (initialUser && initialUser !== activeUser) {
      setActiveUser(initialUser);
    }
    if (initialUser) {
      setActiveUserLabel((current) => (current ? current : initialUser));
    }
    const personaFromUrl = normalizePersonaParam(url.searchParams.get('persona'));
    if (personaFromUrl && personaFromUrl !== activePersona) {
      setActivePersona(personaFromUrl);
    }
    const centerFromUrl = normalizeCenterParam(url.searchParams.get('center'));
    if (centerFromUrl && centerFromUrl !== centerView) {
      setCenterView(centerFromUrl);
    }
    const tourParam = url.searchParams.get('tour');
    if (tourParam === 'open') {
      tourAutoOpenedRef.current = true;
      setTourSession((prev) => prev + 1);
      setTourOpen(true);
    }
  }, [activePersona, activeUser, centerView]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const trimmedUser = activeUser.trim();
    const personaParam = activePersona.trim();
    const centerParam = centerView;
    const tourParam = tourOpen;
    const previous = lastSyncedParamsRef.current;

    if (trimmedUser) {
      window.localStorage.setItem(LOCAL_STORAGE_KEY, trimmedUser);
      addRecentUser(trimmedUser, activeUserLabel || trimmedUser);
    } else {
      window.localStorage.removeItem(LOCAL_STORAGE_KEY);
    }

    const url = new URL(window.location.href);

    const applyParam = (key: string, value: string | null): boolean => {
      const current = url.searchParams.get(key);
      if (value && value.trim()) {
        if (current === value) {
          return false;
        }
        url.searchParams.set(key, value);
        return true;
      }
      if (current) {
        url.searchParams.delete(key);
        return true;
      }
      return false;
    };

    let changed = false;
    changed = applyParam('user', trimmedUser || null) || changed;
    changed = applyParam('persona', personaParam || null) || changed;
    changed = applyParam('center', centerParam || null) || changed;
    if (tourParam) {
      changed = applyParam('tour', 'open') || changed;
    } else if (url.searchParams.get('tour')) {
      url.searchParams.delete('tour');
      changed = true;
    }

    if (
      !changed &&
      previous.user === trimmedUser &&
      previous.persona === personaParam &&
      previous.center === centerParam &&
      previous.tour === tourParam
    ) {
      return;
    }

    if (changed) {
      const href = `${url.pathname}${url.search}${url.hash}` as Route;
      router.replace(href, { scroll: false });
    }

    lastSyncedParamsRef.current = {
      user: trimmedUser,
      persona: personaParam,
      center: centerParam,
      tour: tourParam,
    };
  }, [activeUser, activePersona, centerView, tourOpen, router]);

  useEffect(() => {
    const trimmed = activeUser.trim();
    if (!trimmed) {
      setActiveUserLabel('');
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const results = await fetchUsers(trimmed);
        if (cancelled) {
          return;
        }
        const match = results.find((entry) => entry.id.toLowerCase() === trimmed.toLowerCase());
        setActiveUserLabel(match?.label ?? trimmed);
      } catch (err) {
        if (!cancelled) {
          setActiveUserLabel(trimmed);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeUser]);

  useEffect(() => {
    if (userSwitchInitialSyncRef.current) {
      userSwitchInitialSyncRef.current = false;
      return;
    }
    setUserSwitchRefresh((token) => token + 1);
  }, [activeUser]);

  useEffect(() => {
    void loadPersonas();
  }, [loadPersonas]);

  useEffect(() => {
    const trimmed = activeUser.trim();
    if (!trimmed) {
      setAsks([]);
      setNudges([]);
      setAggregates(null);
      setUnabridged(null);
      setAsksError(null);
      setNudgeError(null);
      setAggregatesError(null);
      setUnabridgedError(null);
      setAsksLoading(false);
      setNudgeLoading(false);
      setAggregatesLoading(false);
      setUnabridgedLoading(false);
      setAskActionPending({});
      setAskActionErrors({});
      setNudgeActionErrors({});
      setNudgeActionPending({});
      setTimelineOpen(false);
      setTimelineTraitId(null);
      setTimelineEntries([]);
      setTimelineError(null);
      return;
    }
    void loadAsks(trimmed, { reset: true });
    void loadNudges(trimmed, { reset: true });
    void loadAggregates(trimmed, { reset: true });
    void loadUnabridged(trimmed, { reset: true });
  }, [activeUser, loadAsks, loadAggregates, loadNudges, loadUnabridged]);

  

  const personaRoster = useMemo(
    () => (personas.length ? personas : DEFAULT_CANONICAL_PERSONAS),
    [personas]
  );
  const activePersonaMeta = useMemo(
    () => personaRoster.find((item) => item.key === activePersona) ?? personaRoster[0],
    [personaRoster, activePersona]
  );
  const personaSendKey = personaSendKeyFromRosterKey(activePersonaMeta?.key ?? 'head_coach');
  const firstWidgetType = 'TranscriptPanel';
  const composerRendered = true;

  // NORTHSTAR FIX: Robust persona change handler that updates both URL and state
  const handlePersonaChange = useCallback((newPersona: string) => {
    // Update URL first for reliable routing
    const url = new URL(window.location.href);
    url.searchParams.set('persona', newPersona);
    const href = (url.pathname + url.search + url.hash) as Route;
    router.push(href, { scroll: false });

    // Update state (this will be redundant after URL update triggers useEffect, but ensures immediate response)
    setActivePersona(newPersona);
  }, [router]);
  const personaDensity = preferences.compactDensity ? 'compact' : 'comfortable';
  const offlineBannerActive = asksCached || nudgesCached || snapshotsCached;
  const retryAsks = useCallback(() => {
    const trimmed = activeUser.trim();
    if (trimmed) {
      void loadAsks(trimmed);
    }
  }, [activeUser, loadAsks]);

  const retryAggregates = useCallback(() => {
    const trimmed = activeUser.trim();
    if (trimmed) {
      void loadAggregates(trimmed);
    }
  }, [activeUser, loadAggregates]);

  const retryUnabridged = useCallback(() => {
    const trimmed = activeUser.trim();
    if (trimmed) {
      void loadUnabridged(trimmed);
    }
  }, [activeUser, loadUnabridged]);

  const refreshAllPanels = useCallback(() => {
    retryAggregates();
    retryUnabridged();
  }, [retryAggregates, retryUnabridged]);

  const retryNudges = useCallback(() => {
    const trimmed = activeUser.trim();
    if (trimmed) {
      void loadNudges(trimmed);
    }
  }, [activeUser, loadNudges]);

  const retrySnapshots = useCallback(() => {
    setSnapshotRefreshToken((token) => token + 1);
  }, []);

  const retryPadna = useCallback(() => {
    setPadnaRefreshToken((token) => token + 1);
  }, []);

  const retryTranscript = useCallback(() => {
    setTranscriptResetToken((token) => token + 1);
    retryAggregates();
  }, [retryAggregates]);

  const handleAskAction = useCallback(
    async (ask: PlannerAsk, action: AskAction, options?: { minutes?: number }) => {
      const currentUser = activeUserRef.current.trim();
      if (!currentUser) {
        setAskActionErrors((prev) => ({ ...prev, [ask.id]: 'Pick a user before acting on asks.' }));
        return;
      }

      const previousState = asksRef.current;

      const optimisticState = previousState.map((row) => {
        if (row.id !== ask.id) {
          return row;
        }
        const metadata = { ...(row.metadata ?? {}) } as Record<string, unknown>;
        metadata.last_action = action;
        if (action === 'snooze' && typeof options?.minutes === 'number') {
          metadata.snoozed_minutes = options.minutes;
        }
        return {
          ...row,
          status: action === 'snooze' ? row.status ?? 'pending' : 'completed',
          metadata,
        };
      });

      setAsks(optimisticState);
      setAskActionPending((prev) => ({ ...prev, [ask.id]: true }));
      setAskActionErrors((prev) => ({ ...prev, [ask.id]: null }));

      try {
        const response = await actOnAsk({
          userId: currentUser,
          id: ask.id,
          action,
          minutes: options?.minutes
        });

        if (!response.ok) {
          console.warn('Ask action rejected', action, response.reason);
          setAskActionErrors((prev) => ({ ...prev, [ask.id]: response.reason ?? 'Action blocked.' }));
          window.setTimeout(() => {
            setAsks(previousState);
          }, 200);
          return;
        }

        if (response.ask) {
          setAsks((prev) => prev.map((row) => (row.id === ask.id ? response.ask! : row)));
        } else if (action !== 'snooze') {
          setAsks((prev) =>
            prev.map((row) =>
              row.id === ask.id
                ? {
                    ...row,
                    status: 'completed'
                  }
                : row
            )
          );
        }

        if (action === 'approve') {
          try {
            window.dispatchEvent(
              new CustomEvent('hc-ask-approved', {
                detail: {
                  userId: currentUser,
                  askId: ask.id
                }
              })
            );
          } catch (eventError) {
            console.warn('Failed to dispatch ask approved event', eventError);
          }
        }
      } catch (err) {
        console.warn('Ask action failed', action, err);
        setAskActionErrors((prev) => ({ ...prev, [ask.id]: describeError(err) }));
        window.setTimeout(() => {
          setAsks(previousState);
        }, 200);
      } finally {
        setAskActionPending((prev) => ({ ...prev, [ask.id]: false }));
      }
    },
    []
  );

  const handleObservationWindowChange = useCallback(
    (nextWindow: string) => {
      observationWindowPinnedRef.current = true;
      setObservationWindow(nextWindow);
    },
    []
  );

  const handleClearChat = useCallback(
    (userId: string) => {
      const trimmedActive = activeUser.trim();
      const label = trimmedActive && trimmedActive === userId ? activeUserLabel || userId : userId;
      pushNotice(translate('notice.transcriptCleared', { label }), 'info');
    },
    [activeUser, activeUserLabel, pushNotice, translate]
  );

  const handleNudgeAction = useCallback(
    async (nudge: NudgeItem, action: NudgeAction) => {
      const currentUser = activeUserRef.current.trim();
      if (!currentUser) {
        setNudgeActionErrors((prev) => ({ ...prev, [nudge.id]: 'Pick a user before acting on nudges.' }));
        return;
      }

      const previousState = nudgesRef.current;
      let optimisticState: NudgeItem[] = previousState;

      if (action === 'accept' || action === 'dismiss') {
        optimisticState = previousState.filter((row) => row.id !== nudge.id);
      } else if (action === 'undo') {
        optimisticState = previousState.map((row) =>
          row.id === nudge.id ? { ...row, status: 'pending' } : row
        );
      }

      setNudges(optimisticState);
      setNudgeActionPending((prev) => ({ ...prev, [nudge.id]: true }));
      setNudgeActionErrors((prev) => ({ ...prev, [nudge.id]: null }));

      try {
        const response = await actOnNudge({ userId: currentUser, id: nudge.id, action });
        if (!response.ok) {
          console.warn('Nudge action rejected', action, response.reason);
          setNudgeActionErrors((prev) => ({ ...prev, [nudge.id]: response.reason ?? 'Action blocked.' }));
          window.setTimeout(() => {
            setNudges(previousState);
          }, 200);
          return;
        }

        if (response.nudge) {
          setNudges((prev) => prev.map((row) => (row.id === nudge.id ? response.nudge! : row)));
        } else {
          setNudges((prev) => prev.filter((row) => row.id !== nudge.id));
        }

        void loadNudges(currentUser);
      } catch (err) {
        console.warn('Nudge action failed', action, err);
        setNudgeActionErrors((prev) => ({ ...prev, [nudge.id]: describeError(err) }));
        window.setTimeout(() => {
          setNudges(previousState);
        }, 200);
      } finally {
        setNudgeActionPending((prev) => ({ ...prev, [nudge.id]: false }));
      }
    },
    [loadNudges]
  );

  const personaContext = useMemo<PersonaCenterContext>(
    () => ({
      activeUser,
      activePersona,
      aggregates,
      aggregatesLoading,
      aggregatesError,
      retryAggregates,
      observationWindow,
      onObservationWindowChange: handleObservationWindowChange,
      personaRoster,
      handleClearChat,
      asks,
      asksLoading,
      asksError,
      asksCached,
      retryAsks,
      handleAskAction,
      askActionPending,
      askActionErrors,
      nudges,
      nudgeLoading,
      nudgeError,
      nudgesCached,
      retryNudges,
      handleNudgeAction,
      nudgeActionPending,
      nudgeActionErrors,
      onNotify: pushNotice,
      transcriptAutoScroll: preferences.autoScrollTranscript,
      density: personaDensity,
      fillHeightMode: flags.focusedChatLayout,
      transcriptRef,
      transcriptSearchRef,
      composerRef,
      handleQuickSnapshot,
      quickSnapshotPending,
      snapshotRefreshToken,
      retrySnapshots,
      snapshotsCached,
      onSnapshotsCachedChange: handleSnapshotsCachedChange,
      padnaRefreshToken,
      retryPadna,
      transcriptResetToken,
      retryTranscript,
      milestones,
      clearMilestone,
      clearAllMilestones,
      refreshAllPanels,
    }),
    [
      activeUser,
      activePersona,
      aggregates,
      aggregatesLoading,
      aggregatesError,
      retryAggregates,
      observationWindow,
      handleObservationWindowChange,
      personaRoster,
      handleClearChat,
      asks,
      asksLoading,
      asksError,
      asksCached,
      retryAsks,
      handleAskAction,
      askActionPending,
      askActionErrors,
      nudges,
      nudgeLoading,
      nudgeError,
      nudgesCached,
      retryNudges,
      handleNudgeAction,
      nudgeActionPending,
      nudgeActionErrors,
      pushNotice,
      preferences.autoScrollTranscript,
      personaDensity,
      transcriptRef,
      transcriptSearchRef,
      handleQuickSnapshot,
      quickSnapshotPending,
      snapshotRefreshToken,
      retrySnapshots,
      snapshotsCached,
      handleSnapshotsCachedChange,
      padnaRefreshToken,
      retryPadna,
      transcriptResetToken,
      retryTranscript,
      milestones,
      clearMilestone,
      clearAllMilestones,
      flags.focusedChatLayout
    ]
  );

  interface UserChangeOptions {
    immediate?: boolean;
    noticeText?: string;
    noticeTone?: NoticeTone;
    suppressNotice?: boolean;
  }

  const queueActiveUserChange = useCallback(
    (id: string, label?: string | null, options?: UserChangeOptions) => {
      const trimmed = (id ?? '').trim();
      if (!trimmed) {
        return;
      }

      const labelText = label?.trim() ? label.trim() : trimmed;

      const applyChange = () => {
        setActiveUserLabel((current) => (current === labelText ? current : labelText));
        setActiveUser((current) => {
          if (current === trimmed) {
            return current;
          }
          if (!options?.suppressNotice) {
            const text = options?.noticeText ?? translate('notice.userSwitched', { label: labelText });
            const tone = options?.noticeTone ?? 'info';
            pushNotice(text, tone);
          }
          return trimmed;
        });
      };

      if (options?.immediate) {
        if (userSelectionTimerRef.current) {
          window.clearTimeout(userSelectionTimerRef.current);
          userSelectionTimerRef.current = null;
        }
        applyChange();
        return;
      }

      if (userSelectionTimerRef.current) {
        window.clearTimeout(userSelectionTimerRef.current);
      }
      userSelectionTimerRef.current = window.setTimeout(() => {
        userSelectionTimerRef.current = null;
        applyChange();
      }, USER_SWITCH_DEBOUNCE_MS);
    },
    [pushNotice, translate]
  );

  const handleUserSelected = useCallback(
    (user: UserSummary) => {
      queueActiveUserChange(user.id, user.label);
    },
    [queueActiveUserChange]
  );

  const handleRequestCreateUser = useCallback((proposedId: string) => {
    // Instead of opening the old modal, open the onboarding wizard directly
    setOnboardingWizardOpen(true);
  }, []);

  const handleUserCreationComplete = useCallback(
    (user: UserSummary) => {
      setUserModalOpen(false);
      setProposedUserId('');
      queueActiveUserChange(user.id, user.label, { immediate: true, suppressNotice: true });
      const name = user.label || user.id;
      pushNotice(translate('notice.userCreated', { name }), 'success');

      // Automatically launch onboarding wizard for new user
      setOnboardingWizardOpen(true);
    },
    [pushNotice, queueActiveUserChange, translate]
  );

  const handleOnboardingComplete = useCallback(
    async (data: OnboardingData & { userId: string; displayName?: string }) => {
      try {
        // User was already created by the wizard, so just switch to them and save onboarding data
        const targetUserId = data.userId;

        if (!targetUserId) {
          throw new Error('No userId provided in onboarding data');
        }

        // Switch to the newly created user
        queueActiveUserChange(targetUserId, data.displayName || targetUserId, { immediate: true, suppressNotice: true });

        // NORTHSTAR PHASE 2: Use unified Core ingestion instead of direct trait writes
        // Import dynamically to avoid top-level circular deps
        const { formatOnboardingPayload, ingestToCore } = await import('../lib/hcIngestor');
        const { refreshSnapshot } = await import('../lib/coreSnapshot');

        // Format onboarding data as structured payload
        const payload = formatOnboardingPayload({
          name: data.displayName || targetUserId,
          ...data.basic_setup,
          wyrdChoice: data.wyr_answer?.selected_text,
          headCoachName: data.head_coach_name
        });

        // Show brief toast while processing
        pushNotice('Analyzing in Core…', 'info');

        // Ingest to Core → UCN/RR → normalized traits
        const ingestionResult = await ingestToCore(targetUserId, payload, 'onboarding');

        if (!ingestionResult.success) {
          throw new Error(ingestionResult.error || 'Core ingestion failed');
        }

        // Refresh snapshot to get updated profile
        await refreshSnapshot(targetUserId);

        // NORTHSTAR PHASE 2: Set flag for first-message experience
        if (typeof window !== 'undefined') {
          window.localStorage.setItem(`northstar_just_onboarded_${targetUserId}`, 'true');
        }

        // Close wizard and show success with context-aware message
        setOnboardingWizardOpen(false);

        // NORTHSTAR PHASE 2: Context-aware first message
        const welcomeName = data.displayName || targetUserId;
        const wyrChoice = data.wyr_answer?.selected_text;
        const contextMsg = wyrChoice
          ? `Welcome, ${welcomeName}! I see you chose "${wyrChoice}". Your profile is building in Core - let's explore what that means for you.`
          : `Welcome, ${welcomeName}! Profile updated from Core. Ready to chat?`;

        pushNotice(contextMsg, 'success');

        // Trigger panel refreshes to show new data
        refreshAllPanels();

      } catch (err) {
        console.error('Onboarding submission error:', err);
        const message = isApiError(err) ? err.message : 'Failed to save onboarding.';
        pushNotice(message, 'error');
      }
    },
    [pushNotice, refreshAllPanels, queueActiveUserChange]
  );


  const handleProviderConfigError = useCallback(
    (message: string) => {
      const base = message?.trim() ? message.trim() : translate('notice.providerMissing');
      const hint = translate('notice.providerConfigureHint');
      pushNotice(`${base} ${hint}`, 'warning', {
        linkHref: 'http://127.0.0.1:8501/?tab=environment',
        linkLabel: translate('notice.link.openCppEnvironment')
      });
    },
    [pushNotice, translate]
  );

  const triggerSingleImport = useCallback(() => {
    singleImportInputRef.current?.click();
  }, []);

  const handleSingleImportChange = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0] ?? null;
      event.target.value = '';
      if (!file) {
        return;
      }

      const finalize = (result: ImportUserResponse, tone: NoticeTone) => {
        const trimmedId = result.user.id.trim();
        const previousActive = activeUserRef.current;
        queueActiveUserChange(result.user.id, result.user.label, { immediate: true, suppressNotice: true });
        if (previousActive === trimmedId) {
          setUserSwitchRefresh((token) => token + 1);
        }
        const name = result.user.label || trimmedId;
        const messageKey = result.overwrote ? 'notice.userReplaced' : 'notice.userImported';
        pushNotice(translate(messageKey, { name }), tone);
      };

      setImportPending(true);
      try {
        const response = await importUserBundle(file);
        finalize(response, response.overwrote ? 'info' : 'success');
      } catch (err) {
        if (isApiError(err) && err.status === 409) {
          const confirmOverwrite = window.confirm(translate('confirm.importOverwrite'));
          if (confirmOverwrite) {
            try {
              const retry = await importUserBundle(file, { overwrite: true });
              finalize(retry, 'info');
            } catch (retryErr) {
              console.error('Import overwrite failed', retryErr);
              pushNotice(describeError(retryErr), 'error');
            }
          } else {
            pushNotice(translate('notice.importCancelled'), 'info');
          }
        } else {
          console.error('Import failed', err);
          pushNotice(describeError(err), 'error');
        }
      } finally {
        setImportPending(false);
      }
    },
    [importUserBundle, isApiError, pushNotice, queueActiveUserChange, translate]
  );

  const triggerBulkImport = useCallback(() => {
    bulkImportInputRef.current?.click();
  }, []);

  const handleBulkImportChange = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0] ?? null;
      event.target.value = '';
      if (!file) {
        return;
      }

      setBulkImportPending(true);
      try {
        const response = await importUsersBulk(file);
        const imported = Number(response.imported ?? 0);
        const overwritten = Number(response.overwritten ?? 0);
        const conflicts = Number(response.conflicts ?? 0);
        const errors = response.results.filter((entry) => entry.status === 'error').length;

        if (imported > 0) {
          setUserSwitchRefresh((token) => token + 1);
        }

        if (response.results.length) {
          console.table(response.results);
        }

        const parts: string[] = [];
        parts.push(`${imported} imported`);
        if (overwritten > 0) {
          parts.push(`${overwritten} overwritten`);
        }
        if (conflicts > 0) {
          parts.push(`${conflicts} conflicts`);
        }
        if (errors > 0) {
          parts.push(`${errors} errors`);
        }

        let tone: NoticeTone = 'info';
        if (imported > 0 && errors === 0 && conflicts === 0) {
          tone = 'success';
        } else if (errors > 0) {
          tone = 'error';
        } else if (conflicts > 0) {
          tone = 'warning';
        }

        const message = `Bulk import: ${parts.join(', ')}.`;
        pushNotice(message, tone);
      } catch (err) {
        console.error('Bulk import failed', err);
        pushNotice(describeError(err), 'error');
      } finally {
        setBulkImportPending(false);
      }
    },
    [importUsersBulk, pushNotice]
  );

  const retryPersonas = useCallback(() => {
    void loadPersonas();
  }, [loadPersonas]);

  const openTimeline = useCallback(
    (traitId: string) => {
      const currentUser = activeUserRef.current.trim();
      if (!currentUser) {
        window.alert('Pick a user before viewing trait timelines.');
        return;
      }
      setTimelineOpen(true);
      setTimelineTraitId(traitId);
      setTimelineEntries([]);
      setTimelineError(null);
      setTimelineLoading(true);
      void fetchTraitTimeline(currentUser, traitId)
        .then((data) => {
          setTimelineEntries(data);
        })
        .catch((err) => {
          setTimelineError(describeError(err));
        })
        .finally(() => setTimelineLoading(false));
    },
    []
  );

  const closeTimeline = useCallback(() => {
    setTimelineOpen(false);
    setTimelineTraitId(null);
    setTimelineEntries([]);
    setTimelineError(null);
  }, []);

  const handleJump = useCallback((sectionId: string) => {
    if (typeof window === 'undefined') {
      return;
    }
    const target = document.getElementById(sectionId);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      window.history.replaceState(null, '', `#${sectionId}`);
    }
  }, []);

  // Extract layout sections for LayoutSwitcher
  const headerSection = (
    <header className="sticky top-0 z-40 border-b border-slate-800 bg-hc-background/95 backdrop-blur">
          <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6 sm:py-4">
            <div className="flex flex-col gap-1">
              <div className="text-xl font-semibold text-slate-100">{translate('app.title')}</div>
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                <span className="uppercase tracking-wide text-slate-500">{translate('workspace.label')}</span>
                {workspaceLink ? (
                  <a
                    href={workspaceLink}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 rounded-full border border-cyan-500/40 px-2 py-0.5 font-semibold text-cyan-200 hover:bg-cyan-500/10"
                    title={workspaceRootHint ? `${workspaceLabel} — ${workspaceRootHint}` : translate('workspace.open')}
                    aria-label={workspaceRootHint ? translate('workspace.openFor', { label: workspaceLabel }) : translate('workspace.open')}
                  >
                    {workspaceLabel}
                    <span aria-hidden="true">↗</span>
                  </a>
                ) : (
                  <span
                    className="inline-flex items-center rounded-full border border-slate-700 px-2 py-0.5 font-semibold text-slate-200"
                    title={workspaceRootHint || undefined}
                  >
                    {workspaceLabel}
                  </span>
                )}
              </div>
            </div>
            <nav
              id="tour-center-tabs"
              className="flex flex-wrap items-center gap-2 text-sm font-medium text-slate-300"
              aria-label={translate('nav.quickLinks')}
            >
              <Link href="/" className="hover:text-slate-50">
                {translate('nav.home')}
              </Link>
              <button
                type="button"
                onClick={() => handleJump('unabridged')}
                className="rounded-full px-3 py-1 text-slate-300 transition hover:text-slate-50"
                data-testid="nav-unabridged"
              >
                {translate('nav.unabridged')}
              </button>
              <button
                type="button"
                onClick={() => setCenterView('coach')}
                className={`rounded-full px-3 py-1 transition ${
                  centerView === 'coach' ? 'bg-cyan-500/10 text-cyan-200' : 'text-slate-300 hover:text-slate-50'
                }`}
              >
                {translate('nav.coachChat')}
              </button>
              <button
                type="button"
                onClick={() => setCenterView('draft')}
                className={`rounded-full px-3 py-1 transition ${
                  centerView === 'draft' ? 'bg-cyan-500/10 text-cyan-200' : 'text-slate-300 hover:text-slate-50'
                }`}
              >
                {translate('nav.draftChat')}
              </button>
              <button
                type="button"
                onClick={() => setCenterView('snapshots')}
                className={`rounded-full px-3 py-1 transition ${
                  centerView === 'snapshots' ? 'bg-cyan-500/10 text-cyan-200' : 'text-slate-300 hover:text-slate-50'
                }`}
              >
                {translate('nav.snapshots')}
              </button>
              <button
                type="button"
                onClick={openTourFromHelp}
                className="rounded-full px-3 py-1 transition text-slate-300 hover:text-slate-50"
                aria-label={translate('nav.helpTourAria')}
              >
                {translate('nav.helpTour')}
              </button>
            </nav>
            <div className="flex w-full flex-wrap items-center justify-end gap-3 text-sm text-slate-300 sm:w-auto">
              <ClientOnly fallback={<div className="w-48 h-9 rounded-full border border-slate-700 bg-slate-900/60 animate-pulse" />}>
                <UserSwitcher
                  id="tour-user-switcher"
                  activeUserId={activeUser}
                  activeUserLabel={activeUserLabel}
                  onSelectUser={handleUserSelected}
                  onCreateUser={handleRequestCreateUser}
                  busy={
                    asksLoading ||
                    nudgeLoading ||
                    aggregatesLoading ||
                    unabridgedLoading ||
                    importPending ||
                    bulkImportPending
                  }
                  refreshToken={userSwitchRefresh}
                  inputRef={userSwitcherInputRef}
                />
              </ClientOnly>
              <div className="flex flex-wrap items-center gap-2">
                {/* REMOVED: Import User and Bulk Import buttons per user request
                <input
                  ref={singleImportInputRef}
                  type="file"
                  accept="application/json,.json"
                  className="hidden"
                  onChange={handleSingleImportChange}
                  aria-hidden="true"
                />
                <button
                  type="button"
                  onClick={triggerSingleImport}
                  className="rounded-full border border-slate-700 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:bg-slate-800 disabled:opacity-40"
                  disabled={importPending}
                  aria-label="Import single user bundle"
                >
                  {importPending ? 'Importing…' : 'Import user…'}
                </button>
                <input
                  ref={bulkImportInputRef}
                  type="file"
                  accept="application/zip,.zip"
                  className="hidden"
                  onChange={handleBulkImportChange}
                  aria-hidden="true"
                />
                <button
                  type="button"
                  onClick={triggerBulkImport}
                  className="rounded-full border border-slate-700 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:bg-slate-800 disabled:opacity-40"
                  disabled={bulkImportPending}
                  aria-label="Import bulk user archive"
                >
                  {bulkImportPending ? 'Importing zip…' : 'Import bulk…'}
                </button>
                */}
                <button
                  type="button"
                  onClick={() => setSettingsOpen(true)}
                  className="rounded-full border border-slate-700 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:bg-slate-800"
                  aria-haspopup="dialog"
                  aria-controls="hc-settings-modal"
                  aria-label="Open settings"
                >
                  Settings
                </button>
                <button
                  type="button"
                  onClick={() => setCenterView('snapshots')}
                  className="rounded-full border border-cyan-400/60 px-3 py-2 text-xs font-semibold text-cyan-200 hover:bg-cyan-400/10 disabled:opacity-40"
                  disabled={!activeUser.trim()}
                  data-testid="snapshot-export"
                  aria-label={translate('actions.openSnapshots')}
                >
                  {translate('actions.openSnapshots')}
                </button>
              </div>
              <ClientOnly
                fallback={
                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                    <StatusBadge label="Core" tone="unknown" description="Checking…" tooltip="Core: Checking…" />
                    <StatusBadge label="UCN/RR" tone="unknown" description="Checking…" tooltip="UCN/RR: Checking…" />
                    <StatusBadge label="Curiosity" tone="unknown" description="Checking…" tooltip="Curiosity: Checking…" />
                  </div>
                }
              >
                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                  <StatusBadge label="Core" tone={coreBadgeTone} description={coreBadgeDescription} tooltip={coreBadgeTooltip} />
                  <StatusBadge
                    label="UCN/RR"
                    tone={ucnrrBadgeTone}
                    description={ucnrrBadgeDescription}
                    tooltip={ucnrrBadgeTooltip}
                  />
                  <StatusBadge
                    label="Curiosity"
                    tone={curiosityBadgeTone}
                    description={curiosityBadgeDescription}
                    tooltip={curiosityBadgeTooltip}
                  />
                </div>
              </ClientOnly>
            </div>
          </div>
        </header>
  );

  const noticesSection = (
    <>
      {notice ? <NoticeBanner notice={notice} onDismiss={() => setNotice(null)} /> : null}
      {offlineBannerActive ? (
        <div className="mb-4 rounded-2xl border border-amber-400/50 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          {translate('notice.cachedBanner')}
        </div>
      ) : null}
      {personaError ? (
        <PanelError message={personaError} onRetry={retryPersonas} />
      ) : null}
    </>
  );

  const centerContentSection = (
    <ClientOnly
      fallback={
        <div className={flags.focusedChatLayout ? "flex flex-col h-full min-h-0" : "flex-1 space-y-6"}>
          <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-6 text-sm text-slate-500">Loading…</div>
        </div>
      }
    >
      <div className={flags.focusedChatLayout ? "flex flex-col h-full min-h-0 space-y-6" : "flex-1 space-y-6"}>
        {renderPersonaCenter(
          centerView,
          activePersonaMeta?.key ?? 'head_coach',
          personaContext
        )}
      </div>
    </ClientOnly>
  );

  const sidebarSection = flags.focusedChatLayout ? (
    <CoachToolsPane title="Coach Tools">
      {/* Persona-specific tools FIRST (Coach Catalog, Life OS, Photo upload, Avatar rendering, etc.) */}
      {renderPersonaTools(activePersonaMeta?.key ?? 'head_coach', personaContext, () => setCoachCatalogOpen(true))}
      <PanelBoundary resetKeys={[activeUser]} onRetry={retryUnabridged}>
        <RRDnaPanel
          snapshot={unabridged}
          loading={unabridgedLoading}
          error={unabridgedError}
          onRetry={retryUnabridged}
        />
      </PanelBoundary>
      <PanelBoundary resetKeys={[activeUser]} onRetry={retryUnabridged}>
        <UnabridgedPanel
          snapshot={unabridged}
          loading={unabridgedLoading}
          error={unabridgedError}
          onRetry={retryUnabridged}
          id="unabridged"
          onRefresh={refreshAllPanels}
        />
      </PanelBoundary>
      {/* Support panels (ObservationSummary, CoachAsks, NudgeInbox) */}
      {renderSharedSupportPanels(personaContext)}
    </CoachToolsPane>
  ) : (
    <>
      <aside className="w-full shrink-0 space-y-6 lg:w-72">
        <PersonaRail
          id="tour-persona-rail"
          personas={personas}
          activePersona={activePersona}
          onPersonaChange={handlePersonaChange}
        />
        <PanelBoundary resetKeys={[activeUser]} onRetry={retryUnabridged}>
          <UnabridgedPanel
            snapshot={unabridged}
            loading={unabridgedLoading}
            error={unabridgedError}
            onRetry={retryUnabridged}
            id="unabridged"
            onRefresh={refreshAllPanels}
          />
        </PanelBoundary>
      </aside>
    </>
  );

  const composerSection = (
    <ChatComposer
          ref={composerRef}
          id="tour-composer"
          personaLabel={activePersonaMeta?.label ?? translate('app.title')}
          personaIcon={activePersonaMeta?.icon ?? '🧭'}
          personaSendKey={personaSendKey}
          activeUserId={activeUser}
          disabled={!activeUser.trim()}
          onProviderConfigError={handleProviderConfigError}
          onPersonaChange={handlePersonaChange}
          streamingPreference={preferences.streaming}
          enterToSendPreference={preferences.enterToSend}
          providerModel={preferences.providerModel}
          providerTemperature={preferences.providerTemperature}
          providerMaxTokens={preferences.providerMaxTokens}
        />
  );

  const modalsSection = (
    <>
      {debugEnabled ? (
        <DebugOverlay
            roster={personaRoster}
            activePersona={activePersonaMeta?.key ?? 'head_coach'}
            activePersonaLabel={activePersonaMeta?.label ?? translate('app.title')}
            composerReady={composerRendered}
            firstWidget={firstWidgetType}
            activeUser={activeUser}
          />
      ) : null}
      <TimelineDrawer
          open={timelineOpen}
          traitId={timelineTraitId}
          entries={timelineEntries}
          loading={timelineLoading}
          error={timelineError}
          onClose={closeTimeline}
          userId={activeUser}
        />
      <SettingsModal
          open={settingsOpen}
          preferences={preferences}
          hydrated={preferencesHydrated}
          onClose={() => setSettingsOpen(false)}
          onUpdate={updatePreference}
          onReset={resetPreferences}
          shortcutModifier={isMac ? '⌘' : 'Ctrl'}
        />
      <CoachCatalogModal
          isOpen={coachCatalogOpen}
          onClose={() => setCoachCatalogOpen(false)}
          onSelectCoach={(coachId) => {
            // Use unified persona change handler
            handlePersonaChange(coachId);
            pushNotice(`Switched to ${coachId}`, 'success');
          }}
          currentCoach={activePersonaMeta?.key}
        />
      <OnboardUserModal
          open={userModalOpen}
          proposedId={proposedUserId}
          onClose={() => {
            setUserModalOpen(false);
            setProposedUserId('');
          }}
          onCreated={handleUserCreationComplete}
        />
      {onboardingWizardOpen ? (
        <OnboardingWizard
            userId={undefined} // Always undefined to show user_creation phase
            onComplete={handleOnboardingComplete}
            onClose={() => setOnboardingWizardOpen(false)}
          />
      ) : null}
      <CommandPalette
          open={commandOpen}
          onClose={() => setCommandOpen(false)}
          actions={commandActions}
          text={commandPaletteText}
        />
      <ShortcutCheatsheet open={cheatSheetOpen} onClose={() => setCheatSheetOpen(false)} />
      {tourHydrated ? (
        <IntroTour
            key={tourSession}
            open={tourOpen}
            steps={tourSteps}
            onRequestClose={handleTourClose}
          />
      ) : null}
    </>
  );

  const page = (
    <UploadDrawerProvider>
      <LayoutSwitcher
        header={headerSection}
        centerContent={centerContentSection}
        sidebar={sidebarSection}
        composer={composerSection}
        modals={modalsSection}
        notices={noticesSection}
      />
    </UploadDrawerProvider>
  );

  return (
    <Profiler id="head-coach-root" onRender={handleProfileRender}>
      <I18nProvider locale={preferences.locale}>
        {page}
        <PerfHud
          enabled={perfEnabled}
          fps={fps}
          commitDuration={lastCommitDuration}
          commitCount={commitCount}
          virtualizers={virtualizerMetrics}
        />
      </I18nProvider>
    </Profiler>
  );
}

function NoticeBanner({ notice, onDismiss }: { notice: Notice; onDismiss: () => void }) {
  const { t } = useI18n();
  const toneClasses: Record<NoticeTone, string> = {
    success: 'border-emerald-400/50 bg-emerald-500/10 text-emerald-100',
    info: 'border-cyan-400/50 bg-cyan-500/10 text-cyan-100',
    warning: 'border-amber-400/50 bg-amber-500/10 text-amber-100',
    error: 'border-rose-400/50 bg-rose-500/10 text-rose-100'
  };
  return (
    <div
      className={`mb-4 flex items-center justify-between gap-3 rounded-2xl border px-4 py-3 text-sm ${toneClasses[notice.tone]}`}
      role="status"
      aria-live="polite"
    >
      <span className="flex-1">
        {notice.text}
        {notice.linkHref ? (
          <a
            href={notice.linkHref}
            target="_blank"
            rel="noreferrer"
            className="ml-2 inline-flex items-center gap-1 rounded-full bg-slate-900/40 px-2 py-0.5 text-xs font-semibold underline decoration-dotted underline-offset-2"
          >
            {notice.linkLabel ?? t('noticebar.openLink')}
          </a>
        ) : null}
      </span>
      <button
        type="button"
        onClick={onDismiss}
        className="rounded-full bg-slate-900/40 px-3 py-1 text-xs text-slate-200 hover:bg-slate-900/70"
      >
        {t('noticebar.dismiss')}
      </button>
    </div>
  );
}

function DebugOverlay({
  roster,
  activePersona,
  activePersonaLabel,
  composerReady,
  firstWidget,
  activeUser
}: {
  roster: PersonaRosterEntry[];
  activePersona: string;
  activePersonaLabel: string;
  composerReady: boolean;
  firstWidget: string;
  activeUser: string;
}) {
  return (
    <div className="pointer-events-none fixed inset-x-0 top-0 z-40 flex justify-center p-4 sm:items-start sm:justify-end sm:p-6">
      <div className="pointer-events-auto w-full max-w-sm rounded-2xl border border-slate-700 bg-slate-900/95 p-4 text-xs text-slate-200 shadow-2xl sm:w-80">
        <header className="mb-3 flex items-center justify-between text-slate-300">
          <span className="font-semibold uppercase tracking-wide">UI Debug</span>
          <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-400">?ui_debug=1</span>
        </header>
        <section className="space-y-2">
          <div>
            <p className="text-[11px] uppercase tracking-wide text-slate-500">Persona roster</p>
            <ul className="mt-1 space-y-1">
              {roster.map((persona) => (
                <li
                  key={persona.key}
                  className={`flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950/60 px-2 py-1 ${
                    persona.key === activePersona ? 'border-cyan-500/40' : ''
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <span aria-hidden>{persona.icon}</span>
                    <span>{persona.label}</span>
                  </span>
                  <span className={`text-[11px] ${persona.enabled ? 'text-emerald-300' : 'text-rose-300'}`}>
                    {persona.enabled ? 'on' : 'off'}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-2">
            <p className="text-[11px] uppercase tracking-wide text-slate-500">Current persona</p>
            <p className="mt-1 text-sm text-slate-100">{activePersonaLabel}</p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400">
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-2">
              <p className="uppercase tracking-wide">Composer</p>
              <p className="mt-1 text-sm text-slate-100">{composerReady ? '✓ rendered' : '⚠︎ missing'}</p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-2">
              <p className="uppercase tracking-wide">First widget</p>
              <p className="mt-1 text-sm text-slate-100">{firstWidget}</p>
            </div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-2">
            <p className="text-[11px] uppercase tracking-wide text-slate-500">Active user id</p>
            <p className="mt-1 break-all text-sm text-slate-100">{activeUser || '(none)'}</p>
          </div>
        </section>
      </div>
    </div>
  );
}

interface PerfHudProps {
  enabled: boolean;
  fps: number;
  commitDuration: number;
  commitCount: number;
  virtualizers: Record<string, { total: number; visible: number }>;
}

function PerfHud({ enabled, fps, commitDuration, commitCount, virtualizers }: PerfHudProps) {
  if (!enabled) {
    return null;
  }
  const virtualizerEntries = Object.entries(virtualizers);
  return (
    <div className="pointer-events-none fixed bottom-4 left-4 z-[250] w-64 rounded-2xl border border-slate-800 bg-slate-950/90 p-3 text-xs text-slate-200 shadow-2xl">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Perf HUD</p>
      <div className="mt-2 space-y-1">
        <div className="flex items-center justify-between">
          <span>FPS</span>
          <span>{Math.max(0, Math.round(fps))}</span>
        </div>
        <div className="flex items-center justify-between">
          <span>Last commit</span>
          <span>{commitDuration.toFixed(1)} ms</span>
        </div>
        <div className="flex items-center justify-between text-slate-500">
          <span>Commits</span>
          <span>{commitCount}</span>
        </div>
        {virtualizerEntries.length ? (
          <div className="pt-2 text-slate-400">
            {virtualizerEntries.map(([key, metrics]) => (
              <div key={key} className="flex items-center justify-between">
                <span>{key}</span>
                <span>
                  {metrics.visible}/{metrics.total}
                </span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

interface PersonaCenterContext {
  activeUser: string;
  activePersona: string;
  aggregates: ObservationAggregates | null;
  aggregatesLoading: boolean;
  aggregatesError: string | null;
  retryAggregates: () => void;
  observationWindow: string;
  onObservationWindowChange: (window: string) => void;
  personaRoster: PersonaRosterEntry[];
  handleClearChat: (userId: string) => void;
  asks: PlannerAsk[];
  asksLoading: boolean;
  asksError: string | null;
  asksCached: boolean;
  retryAsks: () => void;
  handleAskAction: (ask: PlannerAsk, action: AskAction, options?: { minutes?: number }) => void | Promise<void>;
  askActionPending: Record<string, boolean>;
  askActionErrors: Record<string, string | null>;
  nudges: NudgeItem[];
  nudgeLoading: boolean;
  nudgeError: string | null;
  nudgesCached: boolean;
  retryNudges: () => void;
  handleNudgeAction: (nudge: NudgeItem, action: NudgeAction) => void | Promise<void>;
  nudgeActionPending: Record<string, boolean>;
  nudgeActionErrors: Record<string, string | null>;
  onNotify: (message: string, tone?: NoticeTone) => void;
  transcriptAutoScroll: boolean;
  density: 'comfortable' | 'compact';
  transcriptRef: RefObject<TranscriptPanelHandle>;
  transcriptSearchRef: RefObject<HTMLInputElement>;
  composerRef: RefObject<ChatComposerHandle>;
  handleQuickSnapshot: () => void | Promise<void>;
  quickSnapshotPending: boolean;
  snapshotRefreshToken: number;
  retrySnapshots: () => void;
  snapshotsCached: boolean;
  onSnapshotsCachedChange: (cached: boolean) => void;
  padnaRefreshToken: number;
  retryPadna: () => void;
  transcriptResetToken: number;
  retryTranscript: () => void;
  milestones: MilestoneItem[];
  clearMilestone: (id: string) => void;
  clearAllMilestones: () => void;
  refreshAllPanels: () => void;
  fillHeightMode: boolean;
}

/**
 * Render persona-specific tools for the RIGHT pane
 * Each persona can have specialized tools that appear alongside the chat
 */
function renderPersonaTools(
  personaKey: string,
  context: PersonaCenterContext,
  onOpenCoachCatalog?: () => void
): ReactNode {
  const normalized = normalizePersonaKey(personaKey);

  switch (normalized) {
    case 'head_coach':
      return (
        <>
          {/* Coach Catalog Button */}
          <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-4">
            <button
              type="button"
              onClick={onOpenCoachCatalog}
              className="w-full rounded-lg bg-gradient-to-r from-cyan-500/10 to-violet-500/10 border border-cyan-500/30 px-4 py-3 text-left transition hover:from-cyan-500/20 hover:to-violet-500/20"
            >
              <div className="flex items-center gap-3">
                <div className="text-2xl">👥</div>
                <div>
                  <div className="font-semibold text-cyan-200">Coach Catalog</div>
                  <div className="text-xs text-slate-400">Browse and switch coaches</div>
                </div>
              </div>
            </button>
          </div>
          {/* Life OS Panel */}
          <PanelBoundary resetKeys={[personaKey, context.activeUser]}>
            <LifeOSChatPanel userId={context.activeUser} variant="full" />
          </PanelBoundary>
        </>
      );
    case 'rendering':
      return (
        <>
          <PanelBoundary resetKeys={[personaKey, context.activeUser]}>
            <AvatarRenderPanel userId={context.activeUser} />
          </PanelBoundary>
          <PanelBoundary resetKeys={[personaKey, context.activeUser]}>
            <PortraitRenderCard userId={context.activeUser} />
          </PanelBoundary>
        </>
      );
    case 'photo':
      return (
        <PanelBoundary resetKeys={[personaKey, context.activeUser]}>
          <PhotoPanel userId={context.activeUser} />
        </PanelBoundary>
      );
    default:
      // RC and other personas: no specialized tools, just support panels
      return null;
  }
}

/**
 * Render chat interface for the LEFT pane
 * ALL personas use the same chat interface structure
 *
 * ⚠️ LEFT PANE SANCTITY RULE ⚠️
 * This function controls the LEFT chat pane.
 * DO NOT add new components here without reading LEFT_PANE_SANCTITY_RULE.md
 * ALL new features should go in renderPersonaTools() for the RIGHT pane.
 */
function renderPersonaCenter(
  centerView: CenterRoute,
  personaKey: string,
  context: PersonaCenterContext
): ReactNode {
  // Draft and Snapshots are special full-screen views
  if (centerView === 'draft') {
    return (
      <PanelBoundary resetKeys={[centerView, context.activeUser]}>
        <DraftChatPanel userId={context.activeUser} />
      </PanelBoundary>
    );
  }

  if (centerView === 'snapshots') {
    return (
      <PanelBoundary resetKeys={[centerView, context.activeUser]} onRetry={context.retrySnapshots}>
        <SnapshotsPanel
          userId={context.activeUser}
          onNotify={context.onNotify}
          refreshToken={context.snapshotRefreshToken}
          onCachedChange={context.onSnapshotsCachedChange}
        />
      </PanelBoundary>
    );
  }

  // ALL personas (Head Coach, RC, Photo, PaDNA) use the same chat interface
  return (
    <>
      <div className={context.fillHeightMode ? "shrink-0" : ""}>
        <HeadCoachToolbar
          id="tour-toolbar"
          userId={context.activeUser}
          asks={context.asks}
          loading={context.asksLoading}
          onRefresh={context.retryAsks}
          onNotify={context.onNotify}
          getComposerText={() => context.composerRef.current?.getText() ?? ''}
          clearComposerText={() => context.composerRef.current?.clearText()}
          onRefreshPanels={context.refreshAllPanels}
        />
      </div>
      <div className={context.fillHeightMode ? "flex-1 min-h-0" : ""}>
        {/* NORTHSTAR PHASE 2: Force remount when persona changes by including activePersona in resetKeys */}
        <PanelBoundary resetKeys={[context.activePersona, context.activeUser]} onRetry={context.retryTranscript}>
          <TranscriptPanel
            ref={context.transcriptRef}
            aggregates={context.aggregates}
            loading={context.aggregatesLoading}
            activeUserId={context.activeUser}
            onClearChat={context.handleClearChat}
            autoScroll={context.transcriptAutoScroll}
            density={context.density}
            searchInputRef={context.transcriptSearchRef}
            onQuickSnapshot={context.handleQuickSnapshot}
            quickSnapshotPending={context.quickSnapshotPending}
            resetToken={context.transcriptResetToken}
            fillHeight={context.fillHeightMode}
          />
        </PanelBoundary>
      </div>
      {!context.fillHeightMode && renderSharedSupportPanels(context)}
    </>
  );
}

function normalizePersonaKey(key: string): 'head_coach' | 'photo' | 'rc' | 'rendering' {
  const normalized = key.trim().toLowerCase();
  switch (normalized) {
    case 'padna':
    case 'padna coach':
    case 'rendering':
    case 'rendering coach':
    case 'avatar':
    case 'renderer':
      return 'rendering';
    case 'photo':
    case 'photo_coach':
    case 'photo coach':
      return 'photo';
    case 'rc':
    case 'relationship':
    case 'relationship_coach':
      return 'rc';
    default:
      return 'head_coach';
  }
}

function renderSharedSupportPanels(context: PersonaCenterContext): ReactNode {
  return (
    <>
      <PanelBoundary resetKeys={[context.activeUser]} onRetry={context.retryAggregates}>
        <ObservationSummary
          aggregates={context.aggregates}
          personas={context.personaRoster}
          windowKey={context.observationWindow}
          onWindowChange={context.onObservationWindowChange}
          loading={context.aggregatesLoading}
          error={context.aggregatesError}
          onRetry={context.aggregatesError ? context.retryAggregates : undefined}
        />
      </PanelBoundary>
      <PanelBoundary resetKeys={[context.activeUser]} onRetry={context.retryAsks}>
        <CoachAsksPanel
          asks={context.asks}
          loading={context.asksLoading}
          error={context.asksError}
          onRetry={context.retryAsks}
          onAction={context.handleAskAction}
          actionPending={context.askActionPending}
          actionErrors={context.askActionErrors}
          cached={context.asksCached}
        />
      </PanelBoundary>
      <PanelBoundary resetKeys={[context.activeUser]} onRetry={context.retryNudges}>
        <NudgeInboxPanel
          nudges={context.nudges}
          loading={context.nudgeLoading}
          error={context.nudgeError}
          onRetry={context.retryNudges}
          onAction={context.handleNudgeAction}
          actionPending={context.nudgeActionPending}
          actionErrors={context.nudgeActionErrors}
          cached={context.nudgesCached}
        />
      </PanelBoundary>
      <PanelBoundary resetKeys={[context.activeUser, context.milestones.length]}>
        <MilestonesPanel
          items={context.milestones}
          onClearAll={context.clearAllMilestones}
          onDismiss={context.clearMilestone}
        />
      </PanelBoundary>
    </>
  );
}

type StatusLightState = 'online' | 'offline' | 'unknown';

function StatusBadge({
  label,
  tone,
  description,
  tooltip
}: {
  label: string;
  tone: StatusLightState;
  description: string;
  tooltip: string;
}) {
  const colorClass = tone === 'online' ? 'bg-emerald-400' : tone === 'offline' ? 'bg-rose-500' : 'bg-slate-600';
  const pulseClass = tone === 'unknown' ? 'animate-pulse' : '';
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900/60 px-3 py-1"
      title={tooltip}
      aria-label={tooltip}
    >
      <span className={`h-2.5 w-2.5 rounded-full ${colorClass} ${pulseClass}`} aria-hidden="true" />
      <span className="text-slate-200">{label}</span>
      <span className="text-slate-500">• {description}</span>
    </span>
  );
}

function personaSendKeyFromRosterKey(key: string): string {
  const normalized = key.trim().toLowerCase();
  switch (normalized) {
    case 'head_coach':
    case 'head coach':
      return 'head coach';
    case 'relationship_coach':
    case 'relationship coach':
    case 'rc':
      return 'rc';
    case 'padna':
    case 'padna_coach':
    case 'padna coach':
      return 'padna';
    case 'photo':
    case 'photo_coach':
    case 'photo coach':
      return 'photo';
    default:
      return 'head coach';
  }
}

function describeError(error: unknown): string {
  if (isApiError(error)) {
    if (error.status >= 500) {
      return 'Head Coach service is unavailable right now. Please retry in a moment.';
    }
    if (error.status === 404) {
      return 'No data available yet for this user.';
    }
    if (error.status === 401 || error.status === 403) {
      return 'Not authorized to access this data. Check your credentials.';
    }
    if (error.status === 429) {
      return 'We are rate limiting requests. Try again shortly.';
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'Unexpected error. Please try again.';
}
