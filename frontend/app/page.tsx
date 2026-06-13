"use client";

import * as React from "react";
import { AlertCircle, BarChart3, FileUp, Github, Radar, ShieldCheck } from "lucide-react";
import { analyze, analyzeDemo, getDemos } from "@/lib/api";
import type { DemoInfo, Report } from "@/lib/types";
import { UploadZone } from "@/components/UploadZone";
import { LoadingState } from "@/components/LoadingState";
import { Results } from "@/components/Results";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Menubar,
  MenubarContent,
  MenubarItem,
  MenubarMenu,
  MenubarSeparator,
  MenubarShortcut,
  MenubarTrigger,
} from "@/components/ui/menubar";

const GITHUB_URL = "https://github.com/your-org/kintsugi";

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
          { id: "clean", name: "Clean", description: "Low-risk sample with ordinary customer fields.", suggested_target: "churned" },
          { id: "messy", name: "Messy", description: "A file with missing values, duplicates, and outliers.", suggested_target: "converted" },
          { id: "leaky", name: "Leaky", description: "A sample with a column that gives the target away.", suggested_target: "defaulted" },
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
      <header className="sticky top-0 z-20 border-b bg-background/90 backdrop-blur">
        <div className="container flex min-h-16 flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between sm:py-0">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-md border bg-background text-foreground shadow-sm">
              <Radar className="h-5 w-5" />
            </div>
            <span className="text-lg font-bold tracking-tight">
              Kintsugi
            </span>
          </div>
          <div className="flex w-full items-center gap-2 sm:w-auto">
            <Menubar className="min-w-0 flex-1 justify-start sm:flex-none">
              <MenubarMenu>
                <MenubarTrigger>Dataset</MenubarTrigger>
                <MenubarContent>
                  <MenubarItem onSelect={() => document.getElementById("upload")?.scrollIntoView({ behavior: "smooth" })}>
                    Upload CSV
                    <MenubarShortcut><FileUp className="h-3.5 w-3.5" /></MenubarShortcut>
                  </MenubarItem>
                  <MenubarItem onSelect={() => document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" })}>
                    View workflow
                    <MenubarShortcut><BarChart3 className="h-3.5 w-3.5" /></MenubarShortcut>
                  </MenubarItem>
                </MenubarContent>
              </MenubarMenu>
              <MenubarMenu>
                <MenubarTrigger>Reports</MenubarTrigger>
                <MenubarContent>
                  <MenubarItem
                    disabled={!report}
                    onSelect={() => document.getElementById("results")?.scrollIntoView({ behavior: "smooth" })}
                  >
                    Current analysis
                  </MenubarItem>
                  <MenubarSeparator />
                  <MenubarItem disabled={!report}>
                    Findings
                    <MenubarShortcut>{report?.findings.length ?? 0}</MenubarShortcut>
                  </MenubarItem>
                </MenubarContent>
              </MenubarMenu>
              <MenubarMenu>
                <MenubarTrigger>Project</MenubarTrigger>
                <MenubarContent align="end">
                  <MenubarItem onSelect={() => window.open(GITHUB_URL, "_blank", "noreferrer")}>
                    GitHub
                    <MenubarShortcut><Github className="h-3.5 w-3.5" /></MenubarShortcut>
                  </MenubarItem>
                </MenubarContent>
              </MenubarMenu>
            </Menubar>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="container space-y-10 py-10">
        {/* Hero */}
        <section className="mx-auto max-w-3xl text-center">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1 text-xs font-medium text-muted-foreground shadow-sm">
            <ShieldCheck className="h-3.5 w-3.5" /> Checks leakage, missingness, balance, and drift signals
          </div>
          <h1 className="text-balance text-4xl font-extrabold tracking-tight sm:text-5xl">
            A quick read on whether a CSV is ready for modeling.
          </h1>
          <p className="mt-4 text-pretty text-lg text-muted-foreground">
            Upload a file, choose a target column if you have one, and review the issues that usually slow down model work.
            Rows are analyzed in memory and are not stored.
          </p>
        </section>

        {/* Upload */}
        <section id="upload" className="mx-auto max-w-3xl scroll-mt-24">
          <div className="rounded-lg border bg-card p-6 shadow-sm">
            <UploadZone
              demos={demos}
              busy={busy}
              onAnalyzeFile={onAnalyzeFile}
              onAnalyzeDemo={onAnalyzeDemo}
            />
          </div>
        </section>

        {/* States */}
        <section id="results" className="mx-auto max-w-6xl scroll-mt-24">
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
            <div id="how-it-works" className="mx-auto mt-4 grid max-w-4xl scroll-mt-24 gap-4 sm:grid-cols-3">
              {[
                {
                  title: "1. Upload",
                  body: "Drop a CSV or open a sample. Add the target column when the file has one.",
                },
                {
                  title: "2. Review",
                  body: "The app checks schema shape, missing values, duplicates, outliers, correlations, balance, and leakage risk.",
                },
                {
                  title: "3. Fix",
                  body: "Use the score, findings, and suggested fixes to decide what needs cleanup before training.",
                },
              ].map((s) => (
                <div key={s.title} className="rounded-lg border bg-card p-5">
                  <p className="font-semibold text-foreground">{s.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{s.body}</p>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>

      <footer className="border-t py-8">
        <div className="container text-center text-sm text-muted-foreground">
          FastAPI, scikit-learn, and Next.js. Uploaded rows stay in memory.
        </div>
      </footer>
    </div>
  );
}
