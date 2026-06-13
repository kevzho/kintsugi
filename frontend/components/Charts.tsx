"use client";

import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CorrelationMatrixMetrics, Report } from "@/lib/types";

const BAR = "hsl(var(--foreground))";
const TOOLTIP_STYLE = {
  backgroundColor: "hsl(var(--popover))",
  border: "1px solid hsl(var(--border))",
  borderRadius: "8px",
  color: "hsl(var(--popover-foreground))",
  boxShadow: "0 10px 24px hsl(var(--foreground) / 0.12)",
};
const TOOLTIP_TEXT_STYLE = {
  color: "hsl(var(--popover-foreground))",
};
const PIE_COLORS = [
  "hsl(var(--foreground))",
  "hsl(var(--muted-foreground))",
  "hsl(var(--border))",
  "hsl(var(--accent-foreground))",
];

function EmptyChart({ message }: { message: string }) {
  return (
    <div className="flex h-64 items-center justify-center rounded-lg border border-dashed px-4 text-center text-sm text-muted-foreground">
      {message}
    </div>
  );
}

export function MissingnessChart({ report }: { report: Report }) {
  const data = Object.entries(report.schema.columns)
    .map(([col, p]) => ({ column: col, missing: +(p.null_rate * 100).toFixed(1) }))
    .filter((d) => d.missing > 0)
    .sort((a, b) => b.missing - a.missing)
    .slice(0, 15);

  if (!data.length) return <EmptyChart message="No missing values detected." />;

  return (
    <ResponsiveContainer width="100%" height={Math.max(260, data.length * 34)}>
      <BarChart data={data} layout="vertical" margin={{ left: 16, right: 24 }}>
        <XAxis type="number" unit="%" domain={[0, 100]} tick={{ fontSize: 12 }} />
        <YAxis type="category" dataKey="column" width={120} tick={{ fontSize: 12 }} />
        <Tooltip
          formatter={(v: number) => [`${v}%`, "missing"]}
          contentStyle={TOOLTIP_STYLE}
          labelStyle={TOOLTIP_TEXT_STYLE}
          itemStyle={TOOLTIP_TEXT_STYLE}
          cursor={{ fill: "hsl(var(--muted) / 0.45)" }}
        />
        <Bar dataKey="missing" fill={BAR} radius={[0, 6, 6, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function OutliersChart({ report }: { report: Report }) {
  const data = report.findings
    .filter((f) => f.engine === "outliers" && typeof f.metrics?.outlier_rate === "number")
    .map((f) => ({
      column: f.column ?? "?",
      rate: +(((f.metrics.outlier_rate as number) || 0) * 100).toFixed(1),
    }))
    .sort((a, b) => b.rate - a.rate)
    .slice(0, 15);

  if (!data.length) return <EmptyChart message="No significant outliers detected." />;

  return (
    <ResponsiveContainer width="100%" height={Math.max(260, data.length * 34)}>
      <BarChart data={data} layout="vertical" margin={{ left: 16, right: 24 }}>
        <XAxis type="number" unit="%" tick={{ fontSize: 12 }} />
        <YAxis type="category" dataKey="column" width={120} tick={{ fontSize: 12 }} />
        <Tooltip
          formatter={(v: number) => [`${v}%`, "outliers"]}
          contentStyle={TOOLTIP_STYLE}
          labelStyle={TOOLTIP_TEXT_STYLE}
          itemStyle={TOOLTIP_TEXT_STYLE}
          cursor={{ fill: "hsl(var(--muted) / 0.45)" }}
        />
        <Bar dataKey="rate" fill={BAR} radius={[0, 6, 6, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function ImbalanceChart({ report }: { report: Report }) {
  const finding = report.findings.find((f) => f.engine === "imbalance" && f.metrics?.class_proportions);
  if (!finding) return <EmptyChart message="Target looks balanced (or no target selected)." />;

  const props = finding.metrics.class_proportions as Record<string, number>;
  const data = Object.entries(props).map(([name, value]) => ({
    name,
    value: +(value * 100).toFixed(2),
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={60} outerRadius={100} paddingAngle={2}>
          {data.map((_, i) => (
            <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          formatter={(v: number, n: string) => [`${v}%`, n]}
          contentStyle={TOOLTIP_STYLE}
          labelStyle={TOOLTIP_TEXT_STYLE}
          itemStyle={TOOLTIP_TEXT_STYLE}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

function corrColor(v: number): string {
  const a = Math.abs(v);
  if (v >= 0) return `hsl(0 0% ${100 - a * 72}%)`;
  return `hsl(0 0% ${94 - a * 60}%)`;
}

export function CorrelationHeatmap({ report }: { report: Report }) {
  const finding = report.findings.find((f) => f.code === "CORRELATION_MATRIX");
  if (!finding) return <EmptyChart message="Need at least 2 numeric columns for a correlation heatmap." />;

  const { matrix, labels } = finding.metrics as unknown as CorrelationMatrixMetrics;
  if (!matrix?.length) return <EmptyChart message="No correlation matrix available." />;

  const cell = 26;
  return (
    <div className="overflow-auto">
      <div className="inline-block">
        <div className="flex" style={{ marginLeft: 96 }}>
          {labels.map((l) => (
            <div
              key={l}
              className="flex items-end justify-center text-[10px] text-muted-foreground"
              style={{ width: cell, height: 80, writingMode: "vertical-rl" }}
              title={l}
            >
              <span className="truncate" style={{ maxHeight: 76 }}>{l}</span>
            </div>
          ))}
        </div>
        {matrix.map((row, i) => (
          <div key={i} className="flex items-center">
            <div className="truncate pr-2 text-right text-[10px] text-muted-foreground" style={{ width: 96 }} title={labels[i]}>
              {labels[i]}
            </div>
            {row.map((v, j) => (
              <div
                key={j}
                className="border border-white/40"
                style={{ width: cell, height: cell, backgroundColor: corrColor(v) }}
                title={`${labels[i]} × ${labels[j]}: ${v.toFixed(2)}`}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
