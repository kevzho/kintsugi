"use client";

import * as React from "react";
import { useDropzone } from "react-dropzone";
import { FileUp, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { DemoInfo } from "@/lib/types";

interface UploadZoneProps {
  onAnalyzeFile: (file: File, target: string) => void;
  onAnalyzeDemo: (demo: DemoInfo, target: string) => void;
  demos: DemoInfo[];
  busy: boolean;
}

export function UploadZone({ onAnalyzeFile, onAnalyzeDemo, demos, busy }: UploadZoneProps) {
  const [file, setFile] = React.useState<File | null>(null);
  const [target, setTarget] = React.useState("");

  const onDrop = React.useCallback((accepted: File[]) => {
    if (accepted[0]) setFile(accepted[0]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/csv": [".csv"] },
    maxFiles: 1,
    disabled: busy,
  });

  return (
    <div className="space-y-5">
      <div
        {...getRootProps()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 text-center transition",
          isDragActive ? "border-foreground/40 bg-accent" : "border-border hover:border-foreground/30 hover:bg-accent/50",
          busy && "pointer-events-none opacity-60",
        )}
      >
        <input {...getInputProps()} />
        <div className="flex h-12 w-12 items-center justify-center rounded-lg border bg-background text-foreground shadow-sm">
          <FileUp className="h-6 w-6" />
        </div>
        <p className="mt-3 font-medium text-foreground">
          {file ? file.name : isDragActive ? "Drop the CSV here" : "Drag in a CSV or browse"}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">Up to 10 MB. Processed in memory.</p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label htmlFor="target" className="mb-1.5 block text-sm font-medium text-foreground">
            Target column <span className="font-normal text-muted-foreground">(optional)</span>
          </label>
          <input
            id="target"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="e.g. churned"
            disabled={busy}
            className="h-10 w-full rounded-lg border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>
        <Button
          size="lg"
          disabled={!file || busy}
          onClick={() => file && onAnalyzeFile(file, target)}
          className="sm:w-auto"
        >
          <Sparkles className="h-4 w-4" />
          Analyze
        </Button>
      </div>

      <div className="rounded-lg bg-muted/50 p-4">
        <p className="mb-3 text-sm font-medium text-muted-foreground">Samples</p>
        <div className="grid gap-2 sm:grid-cols-3">
          {demos.map((d) => (
            <button
              key={d.id}
              type="button"
              disabled={busy}
              onClick={() => onAnalyzeDemo(d, target)}
              className="group rounded-lg border bg-card p-3 text-left transition hover:border-foreground/30 hover:bg-accent/40 disabled:opacity-60"
            >
              <p className="font-medium capitalize text-foreground">{d.id}</p>
              <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{d.description}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
