"use client";

import * as React from "react";
import { Upload, Users } from "lucide-react";
import { getUsageStats, trackPageView, type UsageStatsPayload } from "@/lib/api";

const emptyStats: UsageStatsPayload = {
  uniqueVisitors: 0,
  uniqueUsers: 0,
  pageViews: 0,
  submissions: 0,
  storage: "memory",
};

function formatCount(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

function roundedThreshold(value: number, minimum: number): number {
  return Math.max(minimum, Math.ceil(value / 5) * 5);
}

export function UsageStats() {
  const [stats, setStats] = React.useState<UsageStatsPayload>(emptyStats);

  const refresh = React.useCallback(async () => {
    try {
      setStats(await getUsageStats());
    } catch {
      /* keep the current numbers */
    }
  }, []);

  React.useEffect(() => {
    const path = `${window.location.pathname}${window.location.search}`;
    trackPageView(path).finally(refresh);
    const id = window.setInterval(refresh, 30000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const trustedUsers = roundedThreshold(stats.uniqueUsers, 5);
  const totalUses = roundedThreshold(stats.submissions, 10);

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-center sm:gap-4">
      <div className="flex items-center gap-3 rounded-lg border bg-card px-4 py-3 text-left shadow-sm">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border bg-background text-primary">
          <Users className="h-4 w-4" />
        </div>
        <p className="text-sm text-muted-foreground">
          Trusted by{" "}
          <span className="font-semibold tabular-nums text-foreground">
            {formatCount(trustedUsers)}+
          </span>{" "}
          users
        </p>
      </div>
      <div className="flex items-center gap-3 rounded-lg border bg-card px-4 py-3 text-left shadow-sm">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border bg-background text-primary">
          <Upload className="h-4 w-4" />
        </div>
        <p className="text-sm text-muted-foreground">
          Used{" "}
          <span className="font-semibold tabular-nums text-foreground">
            {formatCount(totalUses)}+
          </span>{" "}
          times
        </p>
      </div>
    </div>
  );
}
