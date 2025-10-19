'use client';

import { useState, useEffect } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import { Badge } from '../ui/badge';
import {
  fetchBacklog,
  getCategoryLabel,
  getRiskColor,
  formatPercent,
  formatDate,
  type BacklogCase,
} from '../../lib/llmBenchApi';

interface BacklogTableProps {
  userId?: string;
  onCaseSelect?: (caseId: string) => void;
  onWhy?: (payload: { traitId: string; traitLabel: string; value?: string | null }) => void;
}

export function BacklogTable({ onCaseSelect, onWhy, userId }: BacklogTableProps) {
  const [cases, setCases] = useState<BacklogCase[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [category, setCategory] = useState<string>('');
  const [risk, setRisk] = useState<string>('');

  // Pagination
  const [limit] = useState(20);
  const [offset, setOffset] = useState(0);

  // Load backlog data
  useEffect(() => {
    async function loadBacklog() {
      try {
        setLoading(true);
        setError(null);
        const response = await fetchBacklog({
          category: category || undefined,
          risk: risk || undefined,
          limit,
          offset,
        });
        setCases(response.cases);
        setTotal(response.total);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load backlog');
      } finally {
        setLoading(false);
      }
    }

    loadBacklog();
  }, [category, risk, limit, offset]);

  // Reset offset when filters change
  useEffect(() => {
    setOffset(0);
  }, [category, risk]);

  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(total / limit);

  const handlePrevPage = () => {
    if (offset >= limit) {
      setOffset(offset - limit);
    }
  };

  const handleNextPage = () => {
    if (offset + limit < total) {
      setOffset(offset + limit);
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-center">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent"></div>
        <p className="mt-2 text-sm text-gray-500">Loading backlog...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center">
        <div className="rounded-lg bg-red-50 p-4 text-red-800">
          <p className="font-semibold">Error loading backlog</p>
          <p className="mt-1 text-sm">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex gap-4">
        <div className="flex-1">
          <label htmlFor="category-filter" className="block text-sm font-medium text-gray-700 mb-1">
            Category
          </label>
          <select
            id="category-filter"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">All Categories</option>
            <option value="direct_fact">Direct Fact</option>
            <option value="behavior">Behavior</option>
            <option value="indirect_signal">Indirect Signal</option>
            <option value="edge_case">Edge Case</option>
            <option value="conversational">Conversational</option>
            <option value="ambiguous">Ambiguous</option>
            <option value="correction">Correction</option>
          </select>
        </div>
        <div className="flex-1">
          <label htmlFor="risk-filter" className="block text-sm font-medium text-gray-700 mb-1">
            Risk Level
          </label>
          <select
            id="risk-filter"
            value={risk}
            onChange={(e) => setRisk(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">All Risk Levels</option>
            <option value="low">Low</option>
            <option value="med">Medium</option>
            <option value="high">High</option>
          </select>
        </div>
      </div>

      {/* Results summary */}
      <div className="text-sm text-gray-600">
        Showing {cases.length} of {total} test cases
        {(category || risk) && (
          <button
            onClick={() => {
              setCategory('');
              setRisk('');
            }}
            className="ml-2 text-blue-600 hover:text-blue-800 underline"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      <div className="rounded-lg border border-gray-200">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Category</TableHead>
              <TableHead className="min-w-[300px]">User Message</TableHead>
              <TableHead>Expected Traits</TableHead>
              <TableHead>Risk</TableHead>
              <TableHead>Last P / R</TableHead>
              <TableHead>Last Run</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {cases.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8 text-gray-500">
                  No test cases found
                </TableCell>
              </TableRow>
            ) : (
              cases.map((testCase) => (
                <TableRow
                  key={testCase.id}
                  onClick={() => onCaseSelect?.(testCase.id)}
                  className="cursor-pointer"
                >
                  <TableCell className="font-mono text-xs">{testCase.id}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-xs">
                      {getCategoryLabel(testCase.category)}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div
                      className="text-sm truncate max-w-md"
                      title={testCase.user_message}
                    >
                      {testCase.user_message}
                    </div>
                    {testCase.notes && (
                      <div className="text-xs text-gray-500 mt-1">{testCase.notes}</div>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="text-xs space-y-2">
                      {testCase.expected_trait_ids.map((traitId, idx) => {
                        const value = testCase.expected_values?.[idx] ?? null;
                        const traitLabel = traitDisplayName(traitId);
                        const disabled = !userId;
                        return (
                          <div key={idx} className="rounded-md border border-gray-200 bg-gray-50 p-2">
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-mono text-gray-700" title={traitId}>
                                {traitLabel}
                              </span>
                              <button
                                type="button"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  if (disabled) {
                                    return;
                                  }
                                  onWhy?.({
                                    traitId,
                                    traitLabel,
                                    value,
                                  });
                                }}
                                disabled={disabled}
                                className="rounded border border-emerald-500 px-2 py-1 text-[11px] font-medium text-emerald-600 transition-colors hover:bg-emerald-50 disabled:cursor-not-allowed disabled:border-gray-300 disabled:text-gray-400"
                                title={
                                  disabled
                                    ? 'Set a user id above to view the Why-Card'
                                    : 'View Why-Card'
                                }
                              >
                                Why?
                              </button>
                            </div>
                            {value ? (
                              <div className="mt-1 text-[11px] text-gray-500">
                                Expected value: <span className="font-medium text-gray-700">{value}</span>
                              </div>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge className={getRiskColor(testCase.risk)}>
                      {testCase.risk.toUpperCase()}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-gray-600">
                    {formatPercent(testCase.last_precision)} / {formatPercent(testCase.last_recall)}
                  </TableCell>
                  <TableCell className="text-xs text-gray-500">
                    {formatDate(testCase.last_run_utc)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-600">
            Page {currentPage} of {totalPages}
          </div>
          <div className="flex gap-2">
            <button
              onClick={handlePrevPage}
              disabled={offset === 0}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              onClick={handleNextPage}
              disabled={offset + limit >= total}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function traitDisplayName(traitId: string): string {
  const parts = traitId.split('.');
  const last = parts[parts.length - 1] || traitId;
  return last.replace(/_/g, ' ');
}
