"use client";

import * as React from "react";
import { AlertCircle, Github, Radar, ShieldCheck } from "lucide-react";
import { analyze, analyzeDemo, getDemos } from "@/lib/api";
import type { DemoInfo, Report } from "@/lib/types";
import { UploadZone } from "@/components/UploadZone";
import { LoadingState } from "@/components/LoadingState";
import { Results } from "@/components/Results";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

const GITHUB_URL = "https://github.com/your-org/dataquality-iq";

export default function Home() {
  const [demos, setDemos] = React.useState<DemoInfo[]>([]);
  const [report, setReport] = React.useState<Report | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [coldStart, setColdStart] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    getDemos()
      .then(setDemos)
      .catch(() => {
        // fall back to static demo metadata if the backend is asleep
        setDemos([
          { id: "clean", name: "Clean", description: "A well-behaved dataset that should score an A/B.", suggested_target: "churned" },
          { id: "messy", name: "Messy", description: "Missingness, duplicates, outliers, and class imbalance.", suggested_target: "converted" },
          { id: "leaky", name: "Leaky", description: "Contains an obvious target-leakage column — should score an F.", suggested_target: "defaulted" },
        ]);
      });
  }, []);

  const run = React.useCallback(async (fn: () => Promise<Report>) => {
    setBusy(true);
    setError(null);
    setReport(null);
    const coldTimer = setTimeout(() => setColdStart(true), 3000);
    try {
      const r = await fn();
      setReport(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Please try again.");
    } finally {
      clearTimeout(coldTimer);
      setColdStart(false);
      setBusy(false);
    }
  }, []);

  const onAnalyzeFile = (file: File, target: string) => run(() => analyze(file, target));
  const onAnalyzeDemo = (demo: DemoInfo, target: string) =>
    run(() => analyzeDemo(demo.id, target || demo.suggested_target));

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-20 border-b bg-background/80 backdrop-blur">
        <div className="container flex h-16 items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <Radar className="h-5 w-5" />
            </div>
            <span className="text-lg font-bold tracking-tight">
              DataQuality<span className="text-primary"> IQ</span>
            </span>
          </div>
          <nav className="flex items-center gap-2">
            <a href="#how-it-works">
              <Button variant="ghost" size="sm">How it works</Button>
            </a>
            <a href={GITHUB_URL} target="_blank" rel="noreferrer">
              <Button variant="outline" size="sm">
                <Github className="h-4 w-4" /> GitHub
              </Button>
            </a>
          </nav>
        </div>
      </header>

      <main className="container space-y-12 py-10">
        {/* Hero */}
        <section className="mx-auto max-w-3xl text-center">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-accent px-3 py-1 text-xs font-medium text-accent-foreground">
            <ShieldCheck className="h-3.5 w-3.5" /> Catches target leakage before it costs you a week
          </div>
          <h1 className="text-balance text-4xl font-extrabold tracking-tight sm:text-5xl">
            Know what&apos;s wrong with your dataset before you waste a week training on it.
          </h1>
          <p className="mt-4 text-pretty text-lg text-muted-foreground">
            Upload a CSV and get a 0–100 health score, leakage &amp; imbalance detection, and a
            paste-ready executive summary — in seconds. Your data is processed in memory and never stored.
          </p>
        </section>

        {/* Upload */}
        <section className="mx-auto max-w-3xl">
          <div className="rounded-2xl border bg-card p-6 shadow-sm">
            <UploadZone
              demos={demos}
              busy={busy}
              onAnalyzeFile={onAnalyzeFile}
              onAnalyzeDemo={onAnalyzeDemo}
            />
          </div>
        </section>

        {/* States */}
        <section className="mx-auto max-w-6xl">
          {error && (
            <Alert variant="destructive" className="mb-6">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Analysis failed</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {busy && <LoadingState coldStart={coldStart} />}

          {!busy && report && <Results report={report} />}

          {!busy && !report && !error && (
            <div id="how-it-works" className="mx-auto mt-4 grid max-w-4xl gap-4 sm:grid-cols-3">
              {[
                {
                  title: "1. Upload",
                  body: "Drop a CSV (or pick a demo). Optionally name the target column to unlock leakage and imbalance checks.",
                },
                {
                  title: "2. Analyze",
                  body: "Deterministic engines profile types, missingness, duplicates, outliers, correlations, feature quality, and target leakage.",
                },
                {
                  title: "3. Act",
                  body: "Get a health score, an executive summary, and copy-pasteable pandas fixes — only diagnostics are sent to the LLM, never your data.",
                },
              ].map((s) => (
                <div key={s.title} className="rounded-2xl border bg-card p-5">
                  <p className="font-semibold text-primary">{s.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{s.body}</p>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>

      <footer className="border-t py-8">
        <div className="container text-center text-sm text-muted-foreground">
          Built with FastAPI, scikit-learn, Next.js &amp; Groq. Data processed in memory — never stored.
        </div>
      </footer>
    </div>
  );
}
