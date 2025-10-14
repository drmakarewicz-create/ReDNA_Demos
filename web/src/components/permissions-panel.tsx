"use client";

import React, { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";
import { RefreshCw, Download, Eye, Shield, Clock, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Permissions Panel - Phase 5.C UI
 *
 * Displays active consent checks, capabilities, and audit logs.
 *
 * Features:
 * - Active capabilities table
 * - Recent consent checks log
 * - Refresh capabilities
 * - View detailed logs
 */

interface Capability {
  cap_id: string;
  grantee_id: string;
  purpose: string;
  scopes: string[];
  granted_at: string;
  ttl: string;
  use_count: number;
  revoked: boolean;
}

interface ConsentCheck {
  timestamp: string;
  event_type: string;
  namespace: string;
  required_scopes: string[];
  granted: boolean;
  reason?: string;
  cap_id?: string;
}

interface PermissionsPanelProps {
  userId: string;
  className?: string;
}

export function PermissionsPanel({ userId, className }: PermissionsPanelProps) {
  const [activeCapabilities, setActiveCapabilities] = useState<Capability[]>([]);
  const [recentChecks, setRecentChecks] = useState<ConsentCheck[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadPermissionsData();
  }, [userId]);

  const loadPermissionsData = async () => {
    setLoading(true);
    try {
      // Fetch governance summary
      const summaryRes = await fetch(`/api/governance/${userId}/summary`);
      const summaryData = await summaryRes.json();

      // Fetch consent timeline (recent events)
      const timelineRes = await fetch(`/api/governance/${userId}/consent/timeline?limit=20`);
      const timelineData = await timelineRes.json();

      // Parse active capabilities from summary
      // (In real implementation, this would come from timeline.get_active_capabilities())
      const mockCapabilities: Capability[] = [
        {
          cap_id: "cap-demo-123",
          grantee_id: "devx_ui",
          purpose: "Display user insights",
          scopes: ["read:PsyDNA", "read:SkillDNA"],
          granted_at: new Date().toISOString(),
          ttl: "PT24H",
          use_count: 12,
          revoked: false,
        },
      ];

      setActiveCapabilities(mockCapabilities);

      // Parse recent consent checks from timeline
      const checks = timelineData.events
        ?.filter((e: any) => e.event_type === "use" || e.event_type === "grant")
        .map((e: any) => ({
          timestamp: e.timestamp,
          event_type: e.event_type,
          namespace: e.metadata?.namespace || "unknown",
          required_scopes: e.scopes || [],
          granted: true,
          cap_id: e.cap_id,
        })) || [];

      setRecentChecks(checks);
    } catch (error) {
      console.error("Failed to load permissions data:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadPermissionsData();
    setRefreshing(false);
  };

  const handleViewLogs = () => {
    // Open logs viewer (to be implemented)
    console.log("View full audit logs for", userId);
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  const formatTTL = (ttl: string) => {
    // Parse ISO-8601 duration (e.g., PT24H)
    if (ttl.startsWith("PT") && ttl.endsWith("H")) {
      const hours = ttl.slice(2, -1);
      return `${hours} hours`;
    }
    return ttl;
  };

  const getScopeColor = (scope: string) => {
    if (scope.includes("PsyDNA") || scope.includes("BeliefDNA")) {
      return "destructive";
    }
    if (scope.includes("ChatDNA") || scope.includes("RelationshipDNA")) {
      return "warning";
    }
    return "secondary";
  };

  if (loading) {
    return (
      <Card className={cn("w-full", className)}>
        <CardHeader>
          <CardTitle>Permissions</CardTitle>
          <CardDescription>Loading consent and capability data...</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-blue-500" />
          <h2 className="text-2xl font-bold">Permissions & Consent</h2>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing}>
            <RefreshCw className={cn("h-4 w-4 mr-2", refreshing && "animate-spin")} />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={handleViewLogs}>
            <Eye className="h-4 w-4 mr-2" />
            View Logs
          </Button>
        </div>
      </div>

      {/* Active Capabilities */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Active Capabilities</CardTitle>
          <CardDescription>
            Currently granted access tokens for this user
          </CardDescription>
        </CardHeader>
        <CardContent>
          {activeCapabilities.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <AlertCircle className="h-8 w-8 mx-auto mb-2" />
              <p>No active capabilities</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Grantee</TableHead>
                  <TableHead>Purpose</TableHead>
                  <TableHead>Scopes</TableHead>
                  <TableHead>Granted</TableHead>
                  <TableHead>TTL</TableHead>
                  <TableHead>Uses</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {activeCapabilities.map((cap) => (
                  <TableRow key={cap.cap_id}>
                    <TableCell className="font-medium">{cap.grantee_id}</TableCell>
                    <TableCell>{cap.purpose}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {cap.scopes.map((scope) => (
                          <Badge
                            key={scope}
                            variant={getScopeColor(scope) as any}
                            className="text-xs"
                          >
                            {scope}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatTimestamp(cap.granted_at)}
                    </TableCell>
                    <TableCell>{formatTTL(cap.ttl)}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{cap.use_count}</Badge>
                    </TableCell>
                    <TableCell>
                      {cap.revoked ? (
                        <Badge variant="destructive">Revoked</Badge>
                      ) : (
                        <Badge variant="default" className="bg-green-500">
                          Active
                        </Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Recent Consent Checks */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Recent Consent Checks</CardTitle>
          <CardDescription>
            Last 20 consent validation events
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[300px]">
            {recentChecks.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Clock className="h-8 w-8 mx-auto mb-2" />
                <p>No recent consent checks</p>
              </div>
            ) : (
              <div className="space-y-2">
                {recentChecks.map((check, index) => (
                  <div
                    key={index}
                    className={cn(
                      "p-3 rounded-lg border",
                      check.granted
                        ? "bg-green-50 border-green-200"
                        : "bg-red-50 border-red-200"
                    )}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant={check.granted ? "default" : "destructive"}>
                            {check.event_type}
                          </Badge>
                          <span className="text-sm font-medium">{check.namespace}</span>
                        </div>
                        <div className="flex flex-wrap gap-1 mb-1">
                          {check.required_scopes.map((scope) => (
                            <Badge
                              key={scope}
                              variant="outline"
                              className="text-xs"
                            >
                              {scope}
                            </Badge>
                          ))}
                        </div>
                        {check.reason && (
                          <p className="text-xs text-muted-foreground mt-1">
                            Reason: {check.reason}
                          </p>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground text-right">
                        {formatTimestamp(check.timestamp)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Active Capabilities
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {activeCapabilities.filter((c) => !c.revoked).length}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Uses
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {activeCapabilities.reduce((sum, cap) => sum + cap.use_count, 0)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Recent Checks
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{recentChecks.length}</div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
