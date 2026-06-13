"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

const MESSAGES = [
  "Reading columns and types...",
  "Checking missing values and duplicates...",
  "Checking leakage risk...",
  "Measuring outliers and class balance...",
  "Preparing the report...",
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
            {coldStart ? "Starting the backend..." : MESSAGES[idx]}
          </p>
        </div>
        {coldStart && (
          <p className="-mt-3 pl-8 text-xs text-muted-foreground">
            First requests can take about 30 seconds on a sleeping backend.
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
