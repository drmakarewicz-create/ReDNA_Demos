/**
 * RSC (Remote Sentient Collaboration) API Client
 *
 * Client for agent-to-agent messaging endpoints.
 */

import { authorizedFetch } from './capabilityClient'

export type MessageType = 'rsc_invite' | 'rsc_accept' | 'rsc_decline' | 'rsc_brief' | 'rsc_close'

export interface RSCMessage {
  id: string
  type: MessageType
  from: string
  to: string
  timestamp: string
  ttl_seconds: number
  topic?: string
  constraints?: Record<string, any>
  policy?: Record<string, any>
  payload?: Record<string, any>
  metadata?: Record<string, any>
  thread_id?: string
  in_reply_to?: string
}

export interface SendMessagePayload {
  from_user: string
  to_user: string
  type: MessageType
  topic?: string
  constraints?: Record<string, any>
  policy?: Record<string, any>
  payload?: Record<string, any>
  ttl_seconds?: number
  thread_id?: string
  in_reply_to?: string
}

export interface InboxResponse {
  inbox: RSCMessage[]
  count: number
}

export interface SentResponse {
  sent: RSCMessage[]
  count: number
}

export interface ActOnMessagePayload {
  message_id: string
  action: 'accept' | 'decline' | 'close'
  payload?: Record<string, any>
}

export interface SendMessageResponse {
  ok: boolean
  message: RSCMessage
}

export interface ActOnMessageResponse {
  ok: boolean
  action: string
  response: RSCMessage
}

const API_BASE = import.meta.env.VITE_DEVX_BACKEND_URL || 'http://localhost:8100'

class RSCApiError extends Error {
  constructor(
    message: string,
    public status?: number,
    public response?: any
  ) {
    super(message)
    this.name = 'RSCApiError'
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new RSCApiError(
      error.detail || `Request failed: ${response.statusText}`,
      response.status,
      error
    )
  }
  return response.json()
}

/**
 * Send an RSC message between agents
 */
export async function sendRSCMessage(payload: SendMessagePayload): Promise<SendMessageResponse> {
  const response = await authorizedFetch(
    payload.from_user,
    'agents.rsc.send',
    `${API_BASE}/devx/api/agents/rsc/send`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    }
  )
  return handleResponse<SendMessageResponse>(response)
}

/**
 * Get RSC inbox for a user
 */
export async function getInbox(
  userId: string,
  options?: {
    limit?: number
    message_type?: MessageType
    thread_id?: string
  }
): Promise<InboxResponse> {
  const params = new URLSearchParams()
  if (options?.limit) params.append('limit', options.limit.toString())
  if (options?.message_type) params.append('message_type', options.message_type)
  if (options?.thread_id) params.append('thread_id', options.thread_id)

  const query = params.toString()
  const url = `${API_BASE}/devx/api/agents/rsc/${encodeURIComponent(userId)}/inbox${query ? `?${query}` : ''}`

  const response = await authorizedFetch(userId, 'agents.rsc.read', url)
  return handleResponse<InboxResponse>(response)
}

/**
 * Get RSC sent messages for a user
 */
export async function getSent(
  userId: string,
  options?: {
    limit?: number
    message_type?: MessageType
    thread_id?: string
  }
): Promise<SentResponse> {
  const params = new URLSearchParams()
  if (options?.limit) params.append('limit', options.limit.toString())
  if (options?.message_type) params.append('message_type', options.message_type)
  if (options?.thread_id) params.append('thread_id', options.thread_id)

  const query = params.toString()
  const url = `${API_BASE}/devx/api/agents/rsc/${encodeURIComponent(userId)}/sent${query ? `?${query}` : ''}`

  const response = await authorizedFetch(userId, 'agents.rsc.read', url)
  return handleResponse<SentResponse>(response)
}

/**
 * Act on an RSC message (accept, decline, close)
 */
export async function actOnMessage(
  userId: string,
  payload: ActOnMessagePayload
): Promise<ActOnMessageResponse> {
  const response = await authorizedFetch(
    userId,
    'agents.rsc.send',
    `${API_BASE}/devx/api/agents/rsc/${encodeURIComponent(userId)}/act`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    }
  )
  return handleResponse<ActOnMessageResponse>(response)
}

/**
 * Format timestamp to human-readable string
 */
export function formatTimestamp(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Calculate expiry timestamp
 */
export function getExpiry(message: RSCMessage): Date | null {
  try {
    const ts = new Date(message.timestamp)
    return new Date(ts.getTime() + message.ttl_seconds * 1000)
  } catch {
    return null
  }
}

/**
 * Check if message is expired
 */
export function isExpired(message: RSCMessage): boolean {
  const expiry = getExpiry(message)
  return expiry ? expiry < new Date() : false
}

/**
 * Get message type label
 */
export function getMessageTypeLabel(type: MessageType): string {
  const labels: Record<MessageType, string> = {
    rsc_invite: 'Invite',
    rsc_accept: 'Accept',
    rsc_decline: 'Decline',
    rsc_brief: 'Brief',
    rsc_close: 'Close',
  }
  return labels[type] || type
}

/**
 * Get message type color class
 */
export function getMessageTypeColor(type: MessageType): string {
  const colors: Record<MessageType, string> = {
    rsc_invite: 'bg-blue-50 text-blue-700',
    rsc_accept: 'bg-green-50 text-green-700',
    rsc_decline: 'bg-red-50 text-red-700',
    rsc_brief: 'bg-purple-50 text-purple-700',
    rsc_close: 'bg-gray-50 text-gray-700',
  }
  return colors[type] || 'bg-gray-50 text-gray-700'
}
