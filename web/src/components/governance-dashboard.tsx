"use client";

import React, { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Download,
  FileArchive,
  Shield,
  TrendingUp,
  Clock,
  AlertCircle,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Governance Dashboard - Phase 6 UI
 *
 * Comprehensive governance and compliance view.
 *
 * Features:
 * - Consent timeline visualization
 * - Active capabilities summary
 * - Privacy access metrics
 * - Audit bundle export
 * - Compliance reports
 */

interface GovernanceSummary {
  user_id: string;
  consent_summary: {
    total_events: number;
    active_capabilities: number;
    revoked_capabilities: number;
    total_uses: number;
  };
  privacy_summary: {
    public_access: number;
    sensitive_access: number;
    highly_sensitive_access: number;
  };
  last_audit_export?: string;
}

interface TimelineEvent {
  event_id: string;
  timestamp: string;
  event_type: "grant" | "revoke" | "use" | "expire" | "deny";
  cap_id?: string;
  grantee_id?: string;
  purpose?: string;
  scopes?: string[];
  reason?: string;
}

interface PrivacyIndicator {
  namespace: string;
  color: string;
  label: string;
  icon: string;
  requires_consent: boolean;
}

interface GovernanceDashboardProps {
  userId: string;
  className?: string;
}

export function GovernanceDashboard({ userId, className }: GovernanceDashboardProps) {
  const [summary, setSummary] = useState<GovernanceSummary | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [privacyIndicators, setPrivacyIndicators] = useState<Record<string, PrivacyIndicator>>({});
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    loadGovernanceData();
  }, [userId]);

  const loadGovernanceData = async () => {
    setLoading(true);
    try {
      // Fetch governance summary
      const summaryRes = await fetchWithRetry(`/api/governance/${userId}/summary`);
      const summaryData = await summaryRes.json();
      setSummary(summaryData);

      // Fetch consent timeline
      const timelineRes = await fetchWithRetry(`/api/governance/${userId}/consent/timeline?format=json`);
      const timelineData = await timelineRes.json();
      setTimeline(timelineData.events || []);

      // Fetch privacy indicators
      const indicatorsRes = await fetchWithRetry(`/api/governance/${userId}/privacy/indicators`);
      const indicatorsData = await indicatorsRes.json();
      setPrivacyIndicators(indicatorsData.indicators || {});
    } catch (error) {
      console.error("Failed to load governance data:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleExportAuditBundle = async () => {
    setExporting(true);
    try {
      const res = await fetchWithRetry(`/api/governance/${userId}/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          requester: "user",
          purpose: "gdpr_export",
        }),
      });

      const data = await res.json();

      if (data.ok) {
        // Download the bundle
        window.location.href = data.download_url;
      }
    } catch (error) {
      console.error("Failed to export audit bundle:", error);
    } finally {
      setExporting(false);
    }
  };

  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case "grant":
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case "revoke":
        return <XCircle className="h-4 w-4 text-red-500" />;
      case "use":
        return <Clock className="h-4 w-4 text-blue-500" />;
      case "expire":
        return <AlertCircle className="h-4 w-4 text-orange-500" />;
      case "deny":
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return <Shield className="h-4 w-4" />;
    }
  };

  const getEventColor = (eventType: string) => {
    switch (eventType) {
      case "grant":
        return "bg-green-100 border-green-300";
      case "revoke":
      case "deny":
        return "bg-red-100 border-red-300";
      case "use":
        return "bg-blue-100 border-blue-300";
      case "expire":
        return "bg-orange-100 border-orange-300";
      default:
        return "bg-gray-100 border-gray-300";
    }
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  if (loading) {
    return (
      <Card className={cn("w-full", className)}>
        <CardHeader>
          <CardTitle>Governance Dashboard</CardTitle>
          <CardDescription>Loading governance data...</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Shield className="h-6 w-6 animate-pulse text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className={cn("space-y-6", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Governance & Compliance</h1>
          <p className="text-muted-foreground">
            Comprehensive consent, privacy, and audit controls
          </p>
        </div>
        <Button onClick={handleExportAuditBundle} disabled={exporting}>
          <Download className="h-4 w-4 mr-2" />
          {exporting ? "Exporting..." : "Export Audit Bundle"}
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Events
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {summary?.consent_summary.total_events || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Lifetime consent events
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Active Capabilities
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {summary?.consent_summary.active_capabilities || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Currently granted
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Uses
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {summary?.consent_summary.total_uses || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Capability invocations
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Revoked
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {summary?.consent_summary.revoked_capabilities || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Terminated access
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="timeline" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="timeline">Consent Timeline</TabsTrigger>
          <TabsTrigger value="privacy">Privacy Levels</TabsTrigger>
          <TabsTrigger value="audit">Audit & Export</TabsTrigger>
        </TabsList>

        {/* Timeline Tab */}
        <TabsContent value="timeline" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Consent Event Timeline</CardTitle>
              <CardDescription>
                Chronological history of all consent-related events
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[500px] pr-4">
                {timeline.length === 0 ? (
                  <div className="text-center py-12 text-muted-foreground">
                    <Clock className="h-12 w-12 mx-auto mb-4 opacity-20" />
                    <p>No consent events recorded yet</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {timeline.map((event) => (
                      <div
                        key={event.event_id}
                        className={cn(
                          "p-4 rounded-lg border-2",
                          getEventColor(event.event_type)
                        )}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            {getEventIcon(event.event_type)}
                            <Badge variant="outline" className="uppercase">
                              {event.event_type}
                            </Badge>
                            {event.grantee_id && (
                              <span className="text-sm font-medium">
                                {event.grantee_id}
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-muted-foreground">
                            {formatTimestamp(event.timestamp)}
                          </span>
                        </div>

                        {event.purpose && (
                          <p className="text-sm mb-2">{event.purpose}</p>
                        )}

                        {event.scopes && event.scopes.length > 0 && (
                          <div className="flex flex-wrap gap-1 mb-2">
                            {event.scopes.map((scope) => (
                              <Badge key={scope} variant="secondary" className="text-xs">
                                {scope}
                              </Badge>
                            ))}
                          </div>
                        )}

                        {event.reason && (
                          <p className="text-xs text-muted-foreground">
                            Reason: {event.reason}
                          </p>
                        )}

                        {event.cap_id && (
                          <p className="text-xs text-muted-foreground mt-1">
                            Capability ID: {event.cap_id}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Privacy Tab */}
        <TabsContent value="privacy" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Privacy Levels by Namespace</CardTitle>
              <CardDescription>
                Data sensitivity classification for each DNA namespace
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(privacyIndicators).map(([namespace, indicator]) => (
                  <Card key={namespace} className="border-2">
                    <CardContent className="pt-6">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <div
                            className="h-8 w-8 rounded-full flex items-center justify-center text-xl"
                            style={{ backgroundColor: `${indicator.color}20` }}
                          >
                            {indicator.icon}
                          </div>
                          <div>
                            <h3 className="font-semibold">{namespace}</h3>
                            <p className="text-sm text-muted-foreground">
                              {indicator.label}
                            </p>
                          </div>
                        </div>
                        {indicator.requires_consent && (
                          <Badge variant="outline">
                            <Shield className="h-3 w-3 mr-1" />
                            Consent Required
                          </Badge>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Privacy Access Summary */}
              <div className="mt-6 p-4 bg-muted rounded-lg">
                <h4 className="font-medium mb-3">Access by Privacy Level</h4>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <div className="h-3 w-3 rounded-full bg-green-500" />
                      <span className="text-sm font-medium">Public</span>
                    </div>
                    <p className="text-2xl font-bold">
                      {summary?.privacy_summary.public_access || 0}
                    </p>
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <div className="h-3 w-3 rounded-full bg-yellow-500" />
                      <span className="text-sm font-medium">Sensitive</span>
                    </div>
                    <p className="text-2xl font-bold">
                      {summary?.privacy_summary.sensitive_access || 0}
                    </p>
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <div className="h-3 w-3 rounded-full bg-red-500" />
                      <span className="text-sm font-medium">Highly Sensitive</span>
                    </div>
                    <p className="text-2xl font-bold">
                      {summary?.privacy_summary.highly_sensitive_access || 0}
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Audit Tab */}
        <TabsContent value="audit" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Audit & Compliance</CardTitle>
              <CardDescription>
                Export complete data bundles for GDPR compliance
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="p-6 bg-blue-50 border-2 border-blue-200 rounded-lg">
                <div className="flex items-start gap-4">
                  <FileArchive className="h-8 w-8 text-blue-600 flex-shrink-0 mt-1" />
                  <div className="flex-1">
                    <h3 className="font-semibold text-lg mb-2">
                      GDPR Data Export
                    </h3>
                    <p className="text-sm text-muted-foreground mb-4">
                      Generate a comprehensive ZIP bundle containing all user data,
                      consent timeline, capabilities, and provenance metadata.
                      Complies with GDPR Article 15 (Right to Access) and Article 20
                      (Data Portability).
                    </p>
                    <Button onClick={handleExportAuditBundle} disabled={exporting}>
                      <Download className="h-4 w-4 mr-2" />
                      {exporting ? "Creating Bundle..." : "Export Audit Bundle"}
                    </Button>
                  </div>
                </div>
              </div>

              {summary?.last_audit_export && (
                <div className="p-4 bg-muted rounded-lg">
                  <p className="text-sm text-muted-foreground">
                    Last export:{" "}
                    <span className="font-medium text-foreground">
                      {formatTimestamp(summary.last_audit_export)}
                    </span>
                  </p>
                </div>
              )}

              <div className="space-y-2">
                <h4 className="font-medium">Bundle Contents</h4>
                <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                  <li>User profile and preferences</li>
                  <li>All DNA containers (SkillDNA, PsyDNA, etc.)</li>
                  <li>Complete consent timeline</li>
                  <li>Active and revoked capabilities</li>
                  <li>Agent activity logs</li>
                  <li>Telemetry data</li>
                  <li>Provenance and data lineage metadata</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
