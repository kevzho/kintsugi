"use client";

import * as React from "react";
import { Activity, MousePointerClick, Upload, Users } from "lucide-react";
import { getUsageStats, trackPageView, type UsageStatsPayload } from "@/lib/api";

const emptyStats: UsageStatsPayload = {
  uniqueVisitors: 0,
  uniqueUsers: 0,
  pageViews: 0,
  submissions: 0,
  conversionRate: 0,
  storage: "memory",
};

function formatCount(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
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

  const items = [
    { label: "Unique visitors", value: stats.uniqueVisitors, icon: Users },
    { label: "Tool users", value: stats.uniqueUsers, icon: MousePointerClick },
    { label: "Analyses run", value: stats.submissions, icon: Upload },
    { label: "Conversion", value: `${stats.conversionRate}%`, icon: Activity },
  ];

  return (
    <div className="mx-auto grid max-w-4xl gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <div key={item.label} className="rounded-lg border bg-card p-4 text-left shadow-sm">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border bg-background text-primary">
                <Icon className="h-4 w-4" />
              </div>
              <div>
                <p className="text-lg font-semibold tabular-nums text-foreground">
                  {typeof item.value === "number" ? formatCount(item.value) : item.value}
                </p>
                <p className="text-xs text-muted-foreground">{item.label}</p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
