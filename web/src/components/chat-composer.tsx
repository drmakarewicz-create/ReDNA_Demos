'use client';

import {
  ChangeEvent,
  FormEvent,
  KeyboardEvent,
  MutableRefObject,
  forwardRef,
  useCallback,
  useEffect,
  useId,
  useImperativeHandle,
  useRef,
  useState
} from 'react';

import type { TranscriptEntry } from './transcript-panel';
import { PanelError } from './panel-error';
import { useUploadDrawer } from './upload-drawer';
import { isApiError, sendChat, recordChatTurn, type RecordChatTurnParams } from '../lib/api';
import type { ChatProviderSettings } from '../lib/api';
import { useI18n } from '../i18n/context';
import { useFeatureFlags } from '../lib/feature-flags';
import { CoachAvatar, type CoachAvatarState } from './avatar/coach-avatar';

type PendingSend = {
  clientMessageId: string;
  userId: string;
  personaSendKey: string;
  personaLabel: string;
  text: string;
  clientTs: number;
};

type LocalMessageDetail = {
  entry: TranscriptEntry;
  clientMessageId: string;
  personaLabel: string;
  streaming?: boolean;
};

type AssistantSuccessDetail = {
  clientMessageId: string;
  message: {
    text: string;
    ts: number;
    personaLabel: string;
  };
  apiMessageId: string;
};

type AssistantErrorDetail = {
  clientMessageId: string;
  error: string;
};

type AssistantStreamDetail = {
  clientMessageId: string;
  delta: string;
  personaLabel: string;
};

function isAbortError(error: unknown): boolean {
  if (error instanceof DOMException) {
    return error.name === 'AbortError';
  }
  if (error && typeof error === 'object' && 'name' in error) {
    return String((error as { name?: string }).name).toLowerCase() === 'aborterror';
  }
  return false;
}

function dispatchCustomEvent<T>(name: string, detail: T): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.dispatchEvent(new CustomEvent<T>(name, { detail }));
}

type PersonaKey = 'head_coach' | 'rc' | 'padna' | 'photo';

function personaKeyFromSendKey(key: string): PersonaKey {
  const normalized = key.trim().toLowerCase();
  if (normalized === 'rc' || normalized.includes('relationship')) {
    return 'rc';
  }
  if (normalized.includes('padna')) {
    return 'padna';
  }
  if (normalized.includes('photo')) {
    return 'photo';
  }
  return 'head_coach';
}

function buildProviderSettings(
  model?: string | null,
  temperature?: number | null,
  maxTokens?: number | null
): ChatProviderSettings | undefined {
  const payload: ChatProviderSettings = {};
  if (model) {
    payload.model = model;
  }
  if (typeof temperature === 'number' && Number.isFinite(temperature)) {
    payload.temperature = temperature;
  }
  if (typeof maxTokens === 'number' && Number.isFinite(maxTokens)) {
    payload.maxTokens = maxTokens;
  }
  return Object.keys(payload).length ? payload : undefined;
}

/**
 * Detects if a message is requesting a coach switch.
 * Returns the persona key if detected, null otherwise.
 */
function detectCoachSwitch(message: string): string | null {
  const normalized = message.toLowerCase().trim();

  // Photo Coach patterns
  if (
    normalized.match(/\b(speak|talk|switch|chat|go)\s+(to|with)\s+(the\s+)?photo\s+coach\b/) ||
    normalized.match(/\bi('d|'ll| would)\s+like\s+(to\s+)?(speak|talk|chat|switch)\s+(to|with)\s+(the\s+)?photo\s+coach\b/) ||
    normalized.match(/\bshow\s+me\s+(the\s+)?photo\s+coach\b/) ||
    normalized.match(/\bconnect\s+me\s+(to|with)\s+(the\s+)?photo\s+coach\b/)
  ) {
    return 'photo';
  }

  // Relationship Coach patterns
  if (
    normalized.match(/\b(speak|talk|switch|chat|go)\s+(to|with)\s+(the\s+)?(relationship|rc)\s+coach\b/) ||
    normalized.match(/\bi('d|'ll| would)\s+like\s+(to\s+)?(speak|talk|chat|switch)\s+(to|with)\s+(the\s+)?(relationship|rc)\s+coach\b/) ||
    normalized.match(/\bshow\s+me\s+(the\s+)?(relationship|rc)\s+coach\b/) ||
    normalized.match(/\bconnect\s+me\s+(to|with)\s+(the\s+)?(relationship|rc)\s+coach\b/)
  ) {
    return 'relationship_coach';
  }

  // PaDNA Coach patterns (also check for "rendering" as that's the normalized key)
  if (
    normalized.match(/\b(speak|talk|switch|chat|go)\s+(to|with)\s+(the\s+)?(padna|rendering)\s+coach\b/) ||
    normalized.match(/\bi('d|'ll| would)\s+like\s+(to\s+)?(speak|talk|chat|switch)\s+(to|with)\s+(the\s+)?(padna|rendering)\s+coach\b/) ||
    normalized.match(/\bshow\s+me\s+(the\s+)?(padna|rendering)\s+coach\b/) ||
    normalized.match(/\bconnect\s+me\s+(to|with)\s+(the\s+)?(padna|rendering)\s+coach\b/)
  ) {
    return 'padna';
  }

  // Head Coach patterns (back to default)
  if (
    normalized.match(/\b(speak|talk|switch|chat|go)\s+(to|with)\s+(the\s+)?head\s+coach\b/) ||
    normalized.match(/\bi('d|'ll| would)\s+like\s+(to\s+)?(speak|talk|chat|switch)\s+(to|with)\s+(the\s+)?head\s+coach\b/) ||
    normalized.match(/\bshow\s+me\s+(the\s+)?head\s+coach\b/) ||
    normalized.match(/\bconnect\s+me\s+(to|with)\s+(the\s+)?head\s+coach\b/) ||
    normalized.match(/\bgo\s+back\s+(to\s+)?(head\s+coach|main|home)\b/)
  ) {
    return 'head_coach';
  }

  return null;
}

export interface ChatComposerHandle {
  getText: () => string;
  setText: (text: string) => void;
  clearText: () => void;
}

export interface ChatComposerProps {
  id?: string;
  personaLabel: string;
  personaIcon: string;
  personaSendKey: string;
  activeUserId: string;
  disabled?: boolean;
  onProviderConfigError?: (message: string) => void;
  onPersonaChange?: (personaKey: string) => void;
  streamingPreference?: boolean;
  enterToSendPreference?: boolean;
  providerModel?: string | null;
  providerTemperature?: number | null;
  providerMaxTokens?: number | null;
  docked?: boolean; // When true, uses relative positioning instead of fixed
}

export const ChatComposer = forwardRef<ChatComposerHandle, ChatComposerProps>(function ChatComposer({
  id: providedId,
  personaLabel,
  personaIcon,
  personaSendKey,
  activeUserId,
  disabled: disabledProp,
  onProviderConfigError,
  onPersonaChange,
  streamingPreference,
  enterToSendPreference,
  providerModel,
  providerTemperature,
  providerMaxTokens,
  docked = false
}: ChatComposerProps, ref) {
  const generatedId = useId();
  const id = providedId ?? generatedId;
  const composerRegionId = `${id}-region`;
  const statusId = `${id}-status`;

  const { open } = useUploadDrawer();
  const { t } = useI18n();
  const { flags } = useFeatureFlags();

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastFailedSendRef = useRef<PendingSend | null>(null);
  const listeningResetTimerRef = useRef<number | null>(null);
  const speakingCooldownTimerRef = useRef<number | null>(null);
  const hasStreamedRef = useRef(false);

  const [message, setMessage] = useState('');
  const [sendError, setSendError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState('');
  const [liveAnnouncement, setLiveAnnouncement] = useState('');
  const [pendingSend, setPendingSend] = useState<PendingSend | null>(null);
  const [providerLockActive, setProviderLockActive] = useState(false);
  const [providerLockMessage, setProviderLockMessage] = useState<string | null>(null);
  const [providerLockSeconds, setProviderLockSeconds] = useState(0);
  const [avatarState, setAvatarState] = useState<CoachAvatarState>('idle');
  const [interactionStatus, setInteractionStatus] = useState<'thinking' | 'speaking' | null>(null);
  const lingeringTimerRef = useRef<number | null>(null);

  const disabled = Boolean(disabledProp);
  const streamingEnabled = Boolean(streamingPreference);
  const enterToSend = enterToSendPreference ?? true;
  const personaKey = personaKeyFromSendKey(personaSendKey);

  const showAvatar = flags.avatar && !disabled;

  // Expose methods to parent components
  useImperativeHandle(ref, () => ({
    getText: () => message,
    setText: (text: string) => setMessage(text),
    clearText: () => setMessage(''),
  }));

  const clearTimer = useCallback((ref: MutableRefObject<number | null>) => {
    if (ref.current) {
      window.clearTimeout(ref.current);
      ref.current = null;
    }
  }, []);

  const setAvatarIdle = useCallback(() => {
    clearTimer(listeningResetTimerRef);
    clearTimer(speakingCooldownTimerRef);
    clearTimer(lingeringTimerRef);
    setAvatarState('idle');
    setInteractionStatus(null);
  }, [clearTimer]);

  const setAvatarListening = useCallback(() => {
    let blocked = false;
    setAvatarState((current) => {
      if (current === 'speaking' || current === 'error') {
        blocked = true;
        return current;
      }
      return 'listening';
    });
    clearTimer(listeningResetTimerRef);
    if (blocked) {
      return;
    }
    listeningResetTimerRef.current = window.setTimeout(() => {
      setAvatarState((current) => (current === 'listening' ? 'idle' : current));
      listeningResetTimerRef.current = null;
    }, 1200);
  }, [clearTimer]);

  const markAvatarThinking = useCallback(() => {
    clearTimer(listeningResetTimerRef);
    setAvatarState('thinking');
  }, [clearTimer]);

  const markAvatarSpeaking = useCallback(() => {
    clearTimer(listeningResetTimerRef);
    setAvatarState('speaking');
  }, [clearTimer]);

  const scheduleAvatarSpeakingCooldown = useCallback(() => {
    clearTimer(speakingCooldownTimerRef);
    clearTimer(lingeringTimerRef);
    speakingCooldownTimerRef.current = window.setTimeout(() => {
      speakingCooldownTimerRef.current = null;
      lingeringTimerRef.current = window.setTimeout(() => {
        setAvatarState((current) => (current === 'speaking' ? 'idle' : current));
        setInteractionStatus((current) => (current === 'speaking' ? null : current));
        clearTimer(lingeringTimerRef);
      }, 600);
    }, 0);
  }, [clearTimer]);

  const setAvatarError = useCallback(() => {
    clearTimer(listeningResetTimerRef);
    clearTimer(speakingCooldownTimerRef);
    clearTimer(lingeringTimerRef);
    setAvatarState('error');
    setInteractionStatus(null);
    speakingCooldownTimerRef.current = window.setTimeout(() => {
      setAvatarState((current) => (current === 'error' ? 'idle' : current));
      speakingCooldownTimerRef.current = null;
    }, 2000);
  }, [clearTimer]);

  useEffect(() => {
    return () => {
      clearTimer(listeningResetTimerRef);
      clearTimer(speakingCooldownTimerRef);
      clearTimer(lingeringTimerRef);
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [clearTimer]);

  useEffect(() => {
    if (!providerLockActive) {
      return;
    }
    if (providerLockSeconds <= 0) {
      setProviderLockActive(false);
      setProviderLockMessage(null);
      return;
    }
    const timer = window.setInterval(() => {
      setProviderLockSeconds((value) => Math.max(0, value - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [providerLockActive, providerLockSeconds]);

  const dispatchLocalMessage = useCallback(
    (detail: LocalMessageDetail) => dispatchCustomEvent('hc-local-message', detail),
    []
  );

  const dispatchSuccess = useCallback(
    (detail: AssistantSuccessDetail) => dispatchCustomEvent('hc-chat-success', detail),
    []
  );

  const dispatchError = useCallback(
    (detail: AssistantErrorDetail) => dispatchCustomEvent('hc-chat-error', detail),
    []
  );

  const dispatchStream = useCallback(
    (detail: AssistantStreamDetail) => dispatchCustomEvent('hc-chat-stream', detail),
    []
  );

  const dispatchCancel = useCallback(
    (clientMessageId: string) =>
      dispatchCustomEvent('hc-chat-cancelled', { clientMessageId }),
    []
  );

  const attemptSend = useCallback(
    async (payload: PendingSend) => {
      const controller = new AbortController();
      abortControllerRef.current = controller;
      hasStreamedRef.current = false;

      const providerSettings = buildProviderSettings(
        providerModel,
        providerTemperature,
        providerMaxTokens
      );

      try {
        const response = await sendChat(
          {
            userId: payload.userId,
            persona: payload.personaSendKey,
            text: payload.text,
            clientTs: payload.clientTs,
            provider: providerSettings
          },
          {
            stream: streamingEnabled,
            signal: controller.signal,
            onDelta: (delta) => {
              if (!hasStreamedRef.current) {
                hasStreamedRef.current = true;
                setLiveAnnouncement(`${payload.personaLabel} is replying…`);
                setInteractionStatus('speaking');
              }
              markAvatarSpeaking();
              dispatchStream({
                clientMessageId: payload.clientMessageId,
                delta,
                personaLabel: payload.personaLabel
              });
            }
          }
        );

        if (!hasStreamedRef.current) {
          setInteractionStatus('speaking');
          markAvatarSpeaking();
        }

        dispatchSuccess({
          clientMessageId: payload.clientMessageId,
          apiMessageId: response.message_id,
          message: {
            text: response.text,
            ts: response.ts,
            personaLabel: response.persona || payload.personaLabel
          }
        });

        const recordPayload: RecordChatTurnParams = {
          userId: payload.userId,
          persona: payload.personaSendKey,
          personaLabel: payload.personaLabel,
          userText: payload.text,
          assistantText: response.text,
          clientMessageId: payload.clientMessageId,
          assistantMessageId: response.message_id,
          userTs: payload.clientTs,
          assistantTs: response.ts,
        };

        if (response.provider) {
          recordPayload.provider = response.provider;
        }
        if (response.provider_settings && typeof response.provider_settings === 'object') {
          const entries = Object.keys(response.provider_settings);
          if (entries.length > 0) {
            recordPayload.providerSettings = response.provider_settings;
          }
        }

        void recordChatTurn(recordPayload);

        // NORTHSTAR PHASE 2: Ingest user message to Core for fact extraction
        // This runs async in background - doesn't block UI
        void (async () => {
          try {
            const { ingestToCore } = await import('../lib/hcIngestor');
            const { refreshSnapshot } = await import('../lib/coreSnapshot');

            // Ingest user's message verbatim
            await ingestToCore(payload.userId, payload.text, 'chat');

            // Refresh snapshot to get any extracted facts
            await refreshSnapshot(payload.userId, { silent: true });
          } catch (error) {
            // Log but don't interrupt user experience
            console.warn('[Northstar] Background fact ingestion failed:', error);
          }
        })();

        setLiveAnnouncement('Assistant reply ready.');
        setPendingSend(null);
        setSendError(null);
        scheduleAvatarSpeakingCooldown();
        lastFailedSendRef.current = null;
      } catch (error) {
        abortControllerRef.current = null;
        if (isAbortError(error)) {
          dispatchCancel(payload.clientMessageId);
          setPendingSend(null);
          setAvatarIdle();
          return;
        }

        lastFailedSendRef.current = payload;

        let message = 'Assistant is unavailable right now.';
        if (isApiError(error)) {
          message = error.message || message;
          if (error.status === 412 || error.status === 503) {
            onProviderConfigError?.(message);
          }
          if (error.status === 429) {
            const retryAfter = Number(
              (error.payload && (error.payload as Record<string, unknown>).retry_after) ??
                (error.payload && (error.payload as Record<string, unknown>).retryAfter)
            );
            const seconds = Number.isFinite(retryAfter) ? Math.max(1, Math.round(retryAfter)) : 5;
            setProviderLockActive(true);
            setProviderLockSeconds(seconds);
            setProviderLockMessage(message);
          }
        } else if (error instanceof Error) {
          message = error.message;
        }

        setSendError(message);
        setStatusMessage(message);
        setLiveAnnouncement(message);
        setPendingSend(null);
        setAvatarError();
        dispatchError({ clientMessageId: payload.clientMessageId, error: message });
      } finally {
        abortControllerRef.current = null;
      }
    },
    [
      dispatchCancel,
      dispatchError,
      dispatchStream,
      dispatchSuccess,
      markAvatarSpeaking,
      onProviderConfigError,
      providerMaxTokens,
      providerModel,
      providerTemperature,
      markAvatarThinking,
      scheduleAvatarSpeakingCooldown,
      setAvatarError,
      setAvatarIdle,
      setLiveAnnouncement,
      streamingEnabled
    ]
  );

  const handleRetry = useCallback(() => {
    if (pendingSend || !lastFailedSendRef.current) {
      return;
    }
    setSendError(null);
    setStatusMessage('Retrying message…');
    const payload = lastFailedSendRef.current;
    setPendingSend(payload);
    markAvatarThinking();
    setInteractionStatus('thinking');
    void attemptSend(payload);
  }, [attemptSend, markAvatarThinking, pendingSend]);

  const sendDisabled =
    disabled || providerLockActive || pendingSend !== null || !message.trim();

  const handleSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (sendDisabled) {
        if (providerLockActive && providerLockMessage) {
          setStatusMessage(providerLockMessage);
          setLiveAnnouncement(providerLockMessage);
        }
        return;
      }

      const trimmed = message.trim();
      if (!trimmed) {
        setStatusMessage('Message empty — nothing sent.');
        return;
      }

      // Check for coach switching commands
      const switchToPersona = detectCoachSwitch(trimmed);
      if (switchToPersona && onPersonaChange) {
        onPersonaChange(switchToPersona);
        setMessage('');
        const personaNames: Record<string, string> = {
          photo: 'Photo Coach',
          relationship_coach: 'Relationship Coach',
          padna: 'PaDNA Coach',
          head_coach: 'Northstar'
        };
        const targetName = personaNames[switchToPersona] || 'coach';
        setStatusMessage(`Switching to ${targetName}...`);
        setLiveAnnouncement(`Switched to ${targetName}`);
        return;
      }

      const targetUser = activeUserId.trim();
      if (!targetUser) {
        const notice = 'Pick a user before chatting.';
        setStatusMessage(notice);
        setLiveAnnouncement(notice);
        return;
      }

      const clientMessageId =
        typeof crypto !== 'undefined' && crypto.randomUUID
          ? crypto.randomUUID()
          : `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`;

      const entry: TranscriptEntry = {
        role: 'member',
        text: trimmed,
        ts: Date.now(),
        clientMessageId,
        source: 'client-cache'
      };

      dispatchLocalMessage({
        entry,
        clientMessageId,
        personaLabel,
        streaming: streamingEnabled
      });

      setMessage('');
      setStatusMessage('Message sent to Northstar.');
      setLiveAnnouncement('Message sent to Northstar.');
      setSendError(null);
      textareaRef.current?.focus();

      const payload: PendingSend = {
        clientMessageId,
        userId: targetUser,
        personaSendKey,
        personaLabel,
        text: trimmed,
        clientTs: Date.now()
      };
      setPendingSend(payload);
      markAvatarThinking();
      setInteractionStatus('thinking');
      void attemptSend(payload);
    },
    [
      activeUserId,
      attemptSend,
      dispatchLocalMessage,
      message,
      onPersonaChange,
      personaLabel,
      personaSendKey,
      providerLockActive,
      providerLockMessage,
      markAvatarThinking,
      sendDisabled,
      streamingEnabled
    ]
  );

  const handleMessageChange = useCallback(
    (event: ChangeEvent<HTMLTextAreaElement>) => {
      setMessage(event.target.value);
      setAvatarListening();
    },
    [setAvatarListening]
  );

  const handleTextareaFocus = useCallback(() => {
    setAvatarListening();
  }, [setAvatarListening]);

  const handleTextareaBlur = useCallback(() => {
    clearTimer(listeningResetTimerRef);
    if (!message.trim() && pendingSend == null) {
      setAvatarIdle();
    }
  }, [clearTimer, message, pendingSend, setAvatarIdle]);

  const handleTextareaKeyDown = useCallback(
    (event: KeyboardEvent<HTMLTextAreaElement>) => {
      setAvatarListening();
      if (enterToSend) {
        if (event.key === 'Enter' && !event.shiftKey) {
          event.preventDefault();
          event.currentTarget.form?.dispatchEvent(
            new Event('submit', { cancelable: true, bubbles: true })
          );
        }
        return;
      }
      const modifierPressed = event.ctrlKey || event.metaKey;
      if (event.key === 'Enter' && modifierPressed) {
        event.preventDefault();
        event.currentTarget.form?.dispatchEvent(
          new Event('submit', { cancelable: true, bubbles: true })
        );
      }
    },
    [enterToSend, setAvatarListening]
  );

  const sendLabel = 'Send';

  // Use different positioning based on docked prop
  const outerContainerClassName = docked
    ? 'w-full flex justify-center bg-hc-background'
    : 'pointer-events-none fixed inset-x-0 bottom-0 z-50 flex justify-center bg-gradient-to-t from-hc-background via-hc-background/70 to-transparent pt-16';

  return (
    <div
      className={outerContainerClassName}
      data-testid="hc-composer"
    >
      <div
        id={id}
        className={`${docked ? '' : 'pointer-events-auto'} w-full max-w-3xl px-4 pb-6 sm:px-6 [padding-bottom:calc(1.5rem+env(safe-area-inset-bottom,0px))]`}
      >
        {sendError ? <PanelError message={sendError} onRetry={handleRetry} /> : null}
        {providerLockActive && providerLockMessage ? (
          <div
            className="mb-3 rounded-2xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-100"
            role="status"
            aria-live="polite"
          >
            {providerLockMessage}
            {providerLockSeconds > 0 ? ` (retry in ${providerLockSeconds}s…)` : ''}
          </div>
        ) : null}
        <div className="flex items-start gap-4">
          {showAvatar ? (
            <div className="hidden shrink-0 sm:flex sm:pt-1">
              <CoachAvatar
                personaKey={personaKey}
                state={avatarState}
                ariaLabel={`${personaLabel} avatar: ${avatarState}`}
              />
            </div>
          ) : null}
          <form className="flex w-full flex-col gap-3" onSubmit={handleSubmit}>
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span className="rounded bg-slate-800 px-2 py-1 font-medium text-slate-200">
                {personaIcon} {personaLabel}
              </span>
              <span>{t('composer.pinnedInfo')}</span>
            </div>
            {interactionStatus ? (
              <div className="flex items-center gap-2 text-xs text-cyan-200" aria-live="polite">
                {interactionStatus === 'thinking' ? (
                  <>
                    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    <span>Thinking…</span>
                  </>
                ) : (
                  <>
                    <svg className="h-4 w-4 animate-pulse" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
                    </svg>
                    <span>Speaking…</span>
                  </>
                )}
              </div>
            ) : null}
            <textarea
              ref={textareaRef}
              value={message}
              onChange={handleMessageChange}
              onFocus={handleTextareaFocus}
              onBlur={handleTextareaBlur}
              onKeyDown={handleTextareaKeyDown}
              placeholder={
                enterToSend
                  ? 'Type here. Press Enter to send, Shift+Enter for newline.'
                  : 'Type here. Press Ctrl+Enter (or Cmd+Enter) to send. Enter makes a newline.'
              }
              rows={1}
              className="w-full resize-y rounded-2xl border border-slate-700 bg-slate-950/70 p-4 text-sm text-slate-100 outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/40"
              disabled={disabled}
              aria-label="Compose message for Northstar"
              aria-describedby={statusMessage ? statusId : undefined}
            />
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => open()}
                  className="rounded-full border border-slate-700 px-3 py-1 text-sm text-slate-300 hover:border-cyan-400 hover:text-cyan-200 disabled:opacity-40"
                  disabled={disabled}
                  aria-haspopup="dialog"
                  aria-controls="hc-upload-drawer"
                >
                  Upload
                </button>
              </div>
              <button
                type="submit"
                className="inline-flex items-center gap-2 rounded-full bg-cyan-500 px-5 py-2 text-sm font-semibold text-slate-950 shadow hover:bg-cyan-400 disabled:opacity-40"
                disabled={sendDisabled}
                aria-label={providerLockActive ? 'Assistant temporarily unavailable' : 'Send message'}
              >
                {sendLabel}
              </button>
            </div>
            <div id={composerRegionId} className="sr-only" aria-live="polite">
              Composer dock ready.
            </div>
            {statusMessage ? (
              <div id={statusId} className="sr-only" aria-live="assertive">
                {statusMessage}
              </div>
            ) : null}
          </form>
        </div>
        <div id="composer-status-live" className="sr-only" aria-live="polite" aria-atomic="true">
          {liveAnnouncement}
        </div>
      </div>
    </div>
  );
});
