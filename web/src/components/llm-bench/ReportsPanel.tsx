'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { ScrollArea } from '../ui/scroll-area';
import { MarkdownViewer } from './MarkdownViewer';
import {
  fetchReports,
  fetchReportContent,
  getProviderColor,
  type ReportMeta,
} from '../../lib/llmBenchApi';

interface ReportsPanelProps {
  refreshToken?: number;
}

export function ReportsPanel({ refreshToken }: ReportsPanelProps) {
  const [reports, setReports] = useState<ReportMeta[]>([]);
  const [selectedReport, setSelectedReport] = useState<string | null>(null);
  const [reportContent, setReportContent] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [loadingContent, setLoadingContent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchReports({ limit: 100 });
      setReports(data);

      if (selectedReport && !data.some((item) => item.filename === selectedReport)) {
        setSelectedReport(null);
        setReportContent('');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load reports');
    } finally {
      setLoading(false);
    }
  }, [selectedReport]);

  useEffect(() => {
    refresh();
  }, [refresh, refreshToken]);

  useEffect(() => {
    if (!selectedReport) {
      setReportContent('');
      return;
    }

    let cancelled = false;

    async function loadContent(reportFilename: string) {
      try {
        setLoadingContent(true);
        const content = await fetchReportContent(reportFilename);
        if (!cancelled) {
          setReportContent(content);
        }
      } catch (err) {
        if (!cancelled) {
          setReportContent(`Error loading report: ${err instanceof Error ? err.message : 'Unknown error'}`);
        }
      } finally {
        if (!cancelled) {
          setLoadingContent(false);
        }
      }
    }

    loadContent(selectedReport);

    return () => {
      cancelled = true;
    };
  }, [selectedReport]);

  const formatModified = (isoString: string) => {
    if (!isoString) {
      return 'Unknown';
    }
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) {
      return isoString;
    }
    return date.toLocaleString();
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex items-center justify-between space-y-0">
          <span className="text-sm font-semibold text-gray-900">Reports</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={refresh}
            disabled={loading}
          >
            {loading ? 'Refreshing...' : 'Refresh'}
          </Button>
        </CardHeader>
        <CardContent className="pt-0">
          {error && (
            <div className="rounded-lg bg-red-50 p-3 text-sm text-red-800">
              <p className="font-semibold">Error loading reports</p>
              <p className="mt-1">{error}</p>
            </div>
          )}

          {!error && reports.length === 0 && !loading && (
            <div className="py-8 text-center text-sm text-gray-500">
              <p className="font-medium text-gray-900 mb-1">No reports found</p>
              <p className="max-w-xs mx-auto">
                Run a benchmark to generate the first report, or click Refresh if you just completed a run.
              </p>
            </div>
          )}

          {!error && reports.length > 0 && (
            <ScrollArea className="h-[300px]">
              <div className="space-y-2 p-2">
                {reports.map((report) => (
                  <button
                    key={report.filename}
                    onClick={() => setSelectedReport(report.filename)}
                    className={`w-full text-left rounded-lg border p-3 transition-colors ${
                      selectedReport === report.filename
                        ? 'border-blue-300 bg-blue-50'
                        : 'border-gray-200 bg-white hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <Badge className={getProviderColor(report.provider)}>
                        {report.provider ?? 'n/a'}
                      </Badge>
                      <span className="text-xs text-gray-500">
                        {formatModified(report.modified)}
                      </span>
                    </div>
                    <div className="mt-2 text-sm font-medium text-gray-900 break-all">
                      {report.filename}
                    </div>
                  </button>
                ))}
              </div>
            </ScrollArea>
          )}

          {loading && reports.length === 0 && !error && (
            <div className="py-8 text-center text-sm text-gray-500">
              <div className="mx-auto mb-2 h-6 w-6 animate-spin rounded-full border-4 border-solid border-current border-r-transparent" />
              Loading reports...
            </div>
          )}
        </CardContent>
      </Card>

      {selectedReport && (
        <Card>
          <CardHeader className="flex items-center justify-between space-y-0">
            <span className="text-sm font-semibold text-gray-900">Report: {selectedReport}</span>
            <Button variant="ghost" size="sm" onClick={() => setSelectedReport(null)}>
              Close
            </Button>
          </CardHeader>
          <CardContent className="pt-0">
            {loadingContent ? (
              <div className="flex h-[400px] items-center justify-center text-sm text-gray-500">
                <div className="mr-2 h-6 w-6 animate-spin rounded-full border-4 border-solid border-current border-r-transparent" />
                Loading content...
              </div>
            ) : (
              <div className="h-[400px]">
                <MarkdownViewer content={reportContent} />
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
