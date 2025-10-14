import { DEVX_API_BASE } from './env';

const API_BASE = `${DEVX_API_BASE}/agents`;
const ADMIN_HEADER = 'x-devx-auth';
const CAPABILITY_HEADER = 'x-agent-capability';

export type AutonomyLevel = 'manual' | 'propose' | 'semi' | 'auto';
export type ConfigurableAutonomy = Exclude<AutonomyLevel, 'manual'>;

export interface AgentSummary {
  user_id: string;
  agent_id: string;
  status: string;
  autonomy: AutonomyLevel;
  quotas: Record<string, number>;
  permissions: {
    namespaces: string[];
    sensitive: string[];
  };
  metadata?: Record<string, any>;
  last_run?: string | null;
  next_run?: string | null;
  pending_jobs: number;
  errors: number;
  executed_today: number;
  quota_remaining: number;
}

export interface MailboxEntry {
  job_id?: string;
  status?: string;
  kind?: string;
  source?: string;
  queued_at?: string;
  emitted_at?: string;
  [key: string]: any;
}

export interface MailboxSnapshot {
  inbox_count: number;
  outbox_count: number;
  inbox: MailboxEntry[];
  outbox: MailboxEntry[];
}

export interface AgentDetail {
  record: AgentSummary;
  policy: {
    autonomy: AutonomyLevel | null;
    quotas: Record<string, number>;
    permissions: {
      namespaces: string[];
      sensitive: string[];
    };
    escalation: Record<string, any>;
    features?: Record<string, any>;
  };
  state: {
    status: string;
    last_run?: string | null;
    next_run?: string | null;
    pending_jobs: any[];
    errors: any[];
    run_count: number;
  };
  mailbox: MailboxSnapshot;
}

export interface CapabilityResponse {
  token: string;
  payload: {
    agent: string;
    scope: string;
    exp: string;
    issued_at: string;
    user_id: string;
  };
}

function devxAdminToken(): string {
  const metaEnv: Record<string, string> | undefined = (import.meta as any)?.env;
  const envToken = metaEnv?.VITE_DEVX_AGENT_ADMIN_TOKEN || '';
  if (envToken.trim()) return envToken;
  return 'devx-local';
}

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Agent API request failed (${response.status})`);
  }
  return response.json();
}

class AgentClient {
  async listAgents(): Promise<AgentSummary[]> {
    const response = await fetch(API_BASE);
    const payload = await handle<{ agents: AgentSummary[] }>(response);
    return payload.agents;
  }

  async getAgent(userId: string): Promise<AgentDetail> {
    const response = await fetch(`${API_BASE}/${encodeURIComponent(userId)}`);
    return handle<AgentDetail>(response);
  }

  async getMailbox(userId: string, limit = 20): Promise<MailboxSnapshot> {
    const params = new URLSearchParams({ limit: limit.toString() });
    const response = await fetch(`${API_BASE}/${encodeURIComponent(userId)}/mailbox?${params.toString()}`);
    return handle<MailboxSnapshot>(response);
  }

  async runAgent(userId: string, capability: string): Promise<any> {
    const response = await fetch(`${API_BASE}/${encodeURIComponent(userId)}/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        [CAPABILITY_HEADER]: capability,
      },
      body: JSON.stringify({}),
    });
    return handle(response);
  }

  async updateAutonomy(userId: string, autonomy: ConfigurableAutonomy, capability: string): Promise<any> {
    const response = await fetch(`${API_BASE}/${encodeURIComponent(userId)}/autonomy`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        [CAPABILITY_HEADER]: capability,
      },
      body: JSON.stringify({ autonomy }),
    });
    return handle(response);
  }

  async setStatus(userId: string, status: 'enabled' | 'disabled', capability: string): Promise<any> {
    const response = await fetch(`${API_BASE}/${encodeURIComponent(userId)}/status`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        [CAPABILITY_HEADER]: capability,
      },
      body: JSON.stringify({ status }),
    });
    return handle(response);
  }

  async issueCapability(userId: string, scope: string, ttlSeconds = 900, adminToken?: string): Promise<CapabilityResponse> {
    const response = await fetch(`${API_BASE}/${encodeURIComponent(userId)}/capability`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        [ADMIN_HEADER]: adminToken || devxAdminToken(),
      },
      body: JSON.stringify({ scope, ttl_seconds: ttlSeconds }),
    });
    return handle<CapabilityResponse>(response);
  }
}

export const agentApi = new AgentClient();
