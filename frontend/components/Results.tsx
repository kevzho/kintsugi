"use client";

import {
  AlertTriangle,
  ClipboardList,
  Columns3,
  Download,
  Info,
  Rows3,
  Sparkles,
  Zap,
} from "lucide-react";
import type { Report, Severity } from "@/lib/types";
import { SEVERITY_COLORS, SEVERITY_ORDER } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScoreGauge } from "./ScoreGauge";
import { FindingCard } from "./FindingCard";
import {
  CorrelationHeatmap,
  ImbalanceChart,
  MissingnessChart,
  OutliersChart,
} from "./Charts";
import { downloadMarkdown } from "@/lib/markdown";

function StatTile({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-center gap-3 rounded-lg border bg-card p-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border bg-background text-foreground">{icon}</div>
      <div className="min-w-0">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="truncate font-semibold tabular-nums text-foreground">{value}</p>
      </div>
    </div>
  );
}

function ScoreTile({
  title,
  score,
  grade,
  confidence,
  reason,
}: {
  title: string;
  score: number;
  grade: string;
  confidence: string;
  reason: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-end gap-2">
          <span className="text-4xl font-semibold tabular-nums">{Math.round(score)}</span>
          <span className="pb-1 text-sm text-muted-foreground">/100</span>
          <Badge className="mb-1 ml-auto border-border bg-muted text-foreground">{grade}</Badge>
        </div>
        <p className="mt-3 text-xs capitalize text-muted-foreground">Confidence: {confidence}</p>
        <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{reason}</p>
      </CardContent>
    </Card>
  );
}

export function Results({ report }: { report: Report }) {
  const sortFindings = (items: typeof report.findings) => [...items].sort(
    (a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity),
  );
  const integrityIssues = sortFindings(report.findings.filter((f) => f.category !== "modeling_warning" && f.severity !== "info"));
  const modelingWarnings = sortFindings(report.modeling_warnings.length ? report.modeling_warnings : report.findings.filter((f) => f.category === "modeling_warning"));
  const infoDiagnostics = sortFindings(report.findings.filter((f) => f.severity === "info" && f.category !== "modeling_warning"));
  const counts = report.severity_counts;

  return (
    <div className="space-y-6">
      {/* Score + stats */}
      <div className="grid gap-4 lg:grid-cols-3">
        <ScoreTile
          title="Data Integrity"
          score={report.integrity_score}
          grade={report.integrity_grade}
          confidence={report.integrity_confidence}
          reason={report.integrity_confidence_reason}
        />
        <ScoreTile
          title="Model Readiness"
          score={report.readiness_score}
          grade={report.readiness_grade}
          confidence={report.readiness_confidence}
          reason={report.readiness_confidence_reason}
        />
        <ScoreTile
          title="Overall"
          score={report.overall_score}
          grade={report.overall_grade}
          confidence={report.overall_confidence}
          reason={report.overall_confidence_reason}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex flex-col gap-3 text-base text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
              <span className="min-w-0 truncate">{report.dataset_name}</span>
              <Button variant="outline" size="sm" onClick={() => downloadMarkdown(report)}>
                <Download className="h-4 w-4" /> Download
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <StatTile icon={<Rows3 className="h-4 w-4" />} label="Rows" value={report.n_rows.toLocaleString()} />
              <StatTile icon={<Columns3 className="h-4 w-4" />} label="Columns" value={String(report.n_cols)} />
              <StatTile icon={<Zap className="h-4 w-4" />} label="Dataset" value={report.dataset_type} />
              <StatTile
                icon={<Info className="h-4 w-4" />}
                label="Target"
                value={report.target_column ?? "—"}
              />
            </div>
            <div className="flex flex-wrap gap-2">
              {SEVERITY_ORDER.map((s) => {
                const n = counts[s] ?? 0;
                if (!n) return null;
                return (
                  <Badge key={s} className={SEVERITY_COLORS[s as Severity].badge}>
                    {n} {s}
                  </Badge>
                );
              })}
              {report.findings.length === 0 && (
                <Badge className={SEVERITY_COLORS.info.badge}>No issues found</Badge>
              )}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Verdict</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center pb-6">
            <ScoreGauge score={report.overall_score} grade={report.overall_grade} />
            <p className="mt-1 max-w-44 text-center text-xs leading-5 text-muted-foreground">{report.verdict}</p>
            {report.sampled && (
              <p className="mt-2 text-center text-xs text-muted-foreground">
                Based on a {report.n_rows_analyzed.toLocaleString()}-row sample
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Summary */}
      <Card className="border-border bg-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ClipboardList className="h-5 w-5 text-foreground" />
            Summary
            <Badge className="border-border bg-muted text-muted-foreground">
              {report.ai_available ? (
                <span className="flex items-center gap-1"><Sparkles className="h-3 w-3" /> assisted</span>
              ) : (
                "local"
              )}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="leading-relaxed text-foreground/90">{report.exec_summary}</p>
          {report.recommendations.length > 0 && (
            <div>
              <p className="mb-2 text-sm font-semibold text-foreground">Next steps</p>
              <ol className="space-y-2">
                {report.recommendations.map((rec, i) => (
                  <li key={i} className="flex gap-2 text-sm text-foreground/90">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border bg-background text-[11px] font-bold text-foreground">
                      {i + 1}
                    </span>
                    <span>{rec}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Findings + charts */}
      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-3 lg:col-span-3">
          <h3 className="flex items-center gap-2 text-lg font-semibold">
            <AlertTriangle className="h-5 w-5 text-foreground" />
            Critical Data Integrity Issues ({integrityIssues.length})
          </h3>
          {integrityIssues.length === 0 ? (
            <Alert variant="info">
              <Info className="h-4 w-4" />
              <AlertTitle>No major issues</AlertTitle>
              <AlertDescription>The integrity checks did not flag anything material.</AlertDescription>
            </Alert>
          ) : (
            <div className="space-y-2">
              {integrityIssues.map((f, i) => (
                <FindingCard key={`${f.code}-${f.column}-${i}`} finding={f} defaultOpen={i === 0} />
              ))}
            </div>
          )}
          <h3 className="pt-4 text-lg font-semibold">Modeling Warnings ({modelingWarnings.length})</h3>
          <div className="space-y-2">
            {modelingWarnings.map((f, i) => (
              <FindingCard key={`${f.code}-${f.column}-model-${i}`} finding={f} defaultOpen={i === 0 && integrityIssues.length === 0} />
            ))}
            {!modelingWarnings.length && <p className="text-sm text-muted-foreground">No modeling warnings found.</p>}
          </div>
          {infoDiagnostics.length > 0 && (
            <>
              <h3 className="pt-4 text-lg font-semibold">Informational Diagnostics ({infoDiagnostics.length})</h3>
              <div className="space-y-2">
                {infoDiagnostics.map((f, i) => (
                  <FindingCard key={`${f.code}-${f.column}-info-${i}`} finding={f} />
                ))}
              </div>
            </>
          )}
        </div>

        <div className="lg:col-span-2">
          <Card className="lg:sticky lg:top-6">
            <CardHeader>
              <CardTitle className="text-base">Diagnostics</CardTitle>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="missingness">
                <TabsList className="w-full">
                  <TabsTrigger value="missingness">Missingness</TabsTrigger>
                  <TabsTrigger value="correlation">Correlation</TabsTrigger>
                  <TabsTrigger value="imbalance">Imbalance</TabsTrigger>
                  <TabsTrigger value="outliers">Outliers</TabsTrigger>
                </TabsList>
                <TabsContent value="missingness">
                  <MissingnessChart report={report} />
                </TabsContent>
                <TabsContent value="correlation">
                  <CorrelationHeatmap report={report} />
                </TabsContent>
                <TabsContent value="imbalance">
                  <ImbalanceChart report={report} />
                </TabsContent>
                <TabsContent value="outliers">
                  <OutliersChart report={report} />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
