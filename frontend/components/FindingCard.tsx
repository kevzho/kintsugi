"use client";

import * as React from "react";
import { Check, ChevronDown, Copy } from "lucide-react";
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
    <div className={cn("rounded-2xl border bg-card shadow-sm ring-1 ring-transparent transition", open && colors.ring)}>
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
              <span className="rounded-md bg-muted px-2 py-0.5 font-mono text-xs text-muted-foreground">
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
          <div className={cn("rounded-xl border-l-4 bg-muted/50 p-3", colors.text.replace("text", "border"))}>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Why it matters</p>
            <p className="mt-1 text-sm text-foreground/90">{finding.impact}</p>
          </div>
          {finding.fix_snippet && (
            <div className="relative">
              <div className="flex items-center justify-between rounded-t-xl bg-slate-900 px-3 py-1.5">
                <span className="text-xs font-medium text-slate-300">fix</span>
                <button
                  type="button"
                  onClick={copy}
                  className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-slate-300 hover:bg-slate-800"
                >
                  {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
              <pre className="overflow-x-auto rounded-b-xl bg-slate-950 p-3 text-xs leading-relaxed text-slate-100">
                <code>{finding.fix_snippet}</code>
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
