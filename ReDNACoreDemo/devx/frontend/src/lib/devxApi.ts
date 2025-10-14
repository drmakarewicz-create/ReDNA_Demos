/**
 * DevX API Client
 * ================
 *
 * TypeScript client for DevX backend API.
 */

import { DEVX_API_BASE } from './env';

const API_BASE = DEVX_API_BASE;

export interface TraitSummary {
  path: string;
  namespace: string;
  name: string;
  version: string;
  status: string;
  has_value_model: boolean;
  has_trait_semantics: boolean;
}

export interface TraitDefinition {
  path: string;
  container: Record<string, any>;
  value_model?: Record<string, any>;
  trait_semantics?: Record<string, any>;
}

export interface ChangeRequestCreate {
  trait_path: string;
  change_type: string;
  value_model?: Record<string, any>;
  trait_semantics?: Record<string, any>;
  reason: string;
  author?: string;
}

export interface ChangeRequest {
  cr_id: string;
  trait_path: string;
  change_type: string;
  value_model?: Record<string, any>;
  trait_semantics?: Record<string, any>;
  reason: string;
  author: string;
  created_at: string;
  status: string;
  risk_level?: string;
  validation_errors: string[];
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  risk_level: string;
  impact_summary: string;
}

class DevXClient {
  /**
   * List all traits.
   */
  async listTraits(filters?: {
    namespace?: string;
    status?: string;
    has_value_model?: boolean;
  }): Promise<TraitSummary[]> {
    const params = new URLSearchParams();
    if (filters?.namespace) params.append('namespace', filters.namespace);
    if (filters?.status) params.append('status', filters.status);
    if (filters?.has_value_model !== undefined) {
      params.append('has_value_model', filters.has_value_model.toString());
    }

    const response = await fetch(`${API_BASE}/traits/list?${params}`);
    if (!response.ok) throw new Error(`Failed to list traits: ${response.statusText}`);
    return response.json();
  }

  /**
   * Get trait definition.
   */
  async getTraitDefinition(path: string): Promise<TraitDefinition> {
    const response = await fetch(`${API_BASE}/traits/definition?path=${encodeURIComponent(path)}`);
    if (!response.ok) throw new Error(`Failed to get trait definition: ${response.statusText}`);
    return response.json();
  }

  /**
   * Assert trait value model (direct update).
   */
  async assertTraitValue(traitPath: string, valueModel: Record<string, any>): Promise<any> {
    const response = await fetch(`${API_BASE}/traits/assert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trait_path: traitPath, value_model: valueModel }),
    });
    if (!response.ok) throw new Error(`Failed to assert trait value: ${response.statusText}`);
    return response.json();
  }

  /**
   * Propose a change request.
   */
  async proposeChange(cr: ChangeRequestCreate): Promise<ChangeRequest> {
    const response = await fetch(`${API_BASE}/traits/propose-change`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cr),
    });
    if (!response.ok) throw new Error(`Failed to propose change: ${response.statusText}`);
    return response.json();
  }

  /**
   * Validate a change request.
   */
  async validateChangeRequest(crId: string): Promise<ValidationResult> {
    const response = await fetch(`${API_BASE}/traits/validate?cr_id=${encodeURIComponent(crId)}`);
    if (!response.ok) throw new Error(`Failed to validate CR: ${response.statusText}`);
    return response.json();
  }

  /**
   * Apply a change request.
   */
  async applyChange(crId: string): Promise<any> {
    const response = await fetch(`${API_BASE}/traits/apply-change`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cr_id: crId }),
    });
    if (!response.ok) throw new Error(`Failed to apply change: ${response.statusText}`);
    return response.json();
  }

  /**
   * Rollback a change request.
   */
  async rollbackChange(crId: string): Promise<any> {
    const response = await fetch(`${API_BASE}/traits/rollback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cr_id: crId }),
    });
    if (!response.ok) throw new Error(`Failed to rollback change: ${response.statusText}`);
    return response.json();
  }

  async listConflicts(filters: { status?: string; kind?: string; user_id?: string } = {}): Promise<any> {
    const params = new URLSearchParams();
    if (filters.status) params.append('status', filters.status);
    if (filters.kind) params.append('kind', filters.kind);
    if (filters.user_id) params.append('user_id', filters.user_id);
    const response = await fetch(`${API_BASE}/conflicts/list?${params.toString()}`);
    if (!response.ok) throw new Error(`Failed to list conflicts: ${response.statusText}`);
    return response.json();
  }

  async getConflictDetail(conflictId: string): Promise<any> {
    const response = await fetch(`${API_BASE}/conflicts/detail?conflict_id=${encodeURIComponent(conflictId)}`);
    if (!response.ok) throw new Error(`Failed to load conflict detail: ${response.statusText}`);
    return response.json();
  }

  async simulateConflict(payload: Record<string, any>): Promise<any> {
    const response = await fetch(`${API_BASE}/conflicts/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`Failed to simulate conflict: ${response.statusText}`);
    return response.json();
  }

  async seedConflict(): Promise<any> {
    const response = await fetch(`${API_BASE}/conflicts/seed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) throw new Error(`Failed to seed conflict: ${response.statusText}`);
    return response.json();
  }

  async resolveConflict(payload: Record<string, any>): Promise<any> {
    const response = await fetch(`${API_BASE}/conflicts/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`Failed to resolve conflict: ${response.statusText}`);
    return response.json();
  }

  async getConflictLearningStats(): Promise<any> {
    const response = await fetch(`${API_BASE}/conflicts/learning-stats`);
    if (!response.ok) throw new Error(`Failed to fetch conflict learning stats: ${response.statusText}`);
    return response.json();
  }

  async getConflictStats(): Promise<any> {
    const response = await fetch(`${API_BASE}/conflicts/stats`);
    if (!response.ok) throw new Error(`Failed to fetch conflict stats: ${response.statusText}`);
    return response.json();
  }

  async exportConflictLog(userId: string): Promise<Blob> {
    const params = new URLSearchParams({ user_id: userId });
    const response = await fetch(`${API_BASE}/conflicts/export?${params.toString()}`);
    if (!response.ok) throw new Error(`Failed to export conflict log: ${response.statusText}`);
    return response.blob();
  }
}

export const devxApi = new DevXClient();
