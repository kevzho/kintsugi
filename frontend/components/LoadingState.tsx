"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const MESSAGES = [
  "Profiling columns and inferring types…",
  "Scanning for missing values and duplicates…",
  "Hunting for target leakage (the expensive bug)…",
  "Measuring outliers and class balance…",
  "Composing your executive summary…",
];

export function LoadingState({ coldStart }: { coldStart: boolean }) {
  const [idx, setIdx] = React.useState(0);
  React.useEffect(() => {
    const t = setInterval(() => setIdx((i) => (i + 1) % MESSAGES.length), 2200);
    return () => clearInterval(t);
  }, []);

  return (
    <Card className="overflow-hidden">
      <CardContent className="space-y-6 p-6">
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <p className="text-sm font-medium text-foreground">
            {coldStart ? "Waking up the analysis engine…" : MESSAGES[idx]}
          </p>
        </div>
        {coldStart && (
          <p className="-mt-3 pl-8 text-xs text-muted-foreground">
            The free-tier backend may take ~30s to spin up on the first request. Hang tight.
          </p>
        )}
        <div className="grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-40 sm:col-span-1" />
          <Skeleton className="h-40 sm:col-span-2" />
        </div>
        <Skeleton className="h-24" />
        <div className="space-y-2">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      </CardContent>
    </Card>
  );
}
