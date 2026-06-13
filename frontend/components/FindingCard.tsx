"use client";

import * as React from "react";
import { Check, ChevronDown, Copy, Wand2 } from "lucide-react";
import type { Finding } from "@/lib/types";
import { SEVERITY_COLORS } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function FindingCard({ finding, defaultOpen = false }: { finding: Finding; defaultOpen?: boolean }) {
  const [open, setOpen] = React.useState(defaultOpen);
  const [copied, setCopied] = React.useState(false);
  const colors = SEVERITY_COLORS[finding.severity];

  const copy = async () => {
    if (!finding.fix_snippet) return;
    try {
      await navigator.clipboard.writeText(finding.fix_snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className={cn("rounded-lg border bg-card shadow-sm ring-1 ring-transparent transition", open && colors.ring)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 p-4 text-left"
      >
        <span className={cn("mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full", colors.dot)} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className={colors.badge}>{finding.severity.toUpperCase()}</Badge>
            {finding.column && (
              <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                {finding.column}
              </span>
            )}
            <span className="text-xs text-muted-foreground">{finding.engine}</span>
          </div>
          <p className="mt-1 truncate font-medium text-foreground">{finding.title}</p>
        </div>
        <ChevronDown className={cn("h-5 w-5 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="space-y-4 px-4 pb-4 pl-9">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Detail</p>
            <p className="mt-1 text-sm text-foreground/90">{finding.detail}</p>
          </div>
          <div className="rounded-lg border bg-muted/40 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Impact</p>
            <p className="mt-1 text-sm text-foreground/90">{finding.impact}</p>
          </div>
          {finding.fix_snippet && (
            <div className="flex flex-col gap-3 rounded-lg border bg-background p-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-3">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border bg-background text-foreground">
                  <Wand2 className="h-4 w-4" />
                </span>
                <div>
                  <p className="text-sm font-medium text-foreground">Fix available</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Copy the fix when you are ready to apply it.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={copy}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-md border bg-card px-3 text-sm font-medium text-foreground shadow-sm transition hover:bg-accent hover:text-accent-foreground"
              >
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                {copied ? "Copied" : "Copy fix"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
