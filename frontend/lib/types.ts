// TypeScript mirrors of the backend dqi.report dataclasses.

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface Finding {
  engine: string;
  code: string;
  severity: Severity;
  title: string;
  detail: string;
  impact: string;
  column: string | null;
  fix_snippet: string | null;
  metrics: Record<string, unknown>;
  score_penalty: number;
}

export interface ColumnProfile {
  dtype_inferred: string;
  n_unique: number;
  cardinality_ratio: number;
  null_rate: number;
  sample_values: string[];
  is_id_like: boolean;
  is_high_cardinality: boolean;
  is_constant: boolean;
}

export interface Schema {
  columns: Record<string, ColumnProfile>;
  n_numeric: number;
  n_categorical: number;
  n_datetime: number;
  n_id_like: number;
}

export interface Report {
  dataset_name: string;
  n_rows: number;
  n_cols: number;
  n_rows_analyzed: number;
  sampled: boolean;
  target_column: string | null;
  health_score: number;
  grade: string;
  findings: Finding[];
  schema: Schema;
  fingerprint: string;
  severity_counts: Record<string, number>;
  exec_summary: string;
  recommendations: string[];
  ai_available: boolean;
  generated_at: string;
}

export interface DemoInfo {
  id: string;
  name: string;
  description: string;
  suggested_target: string;
}

// Metric helpers (loosely typed payloads coming from specific engines).
export interface CorrelationMatrixMetrics {
  matrix: number[][];
  labels: string[];
}

export const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

export const SEVERITY_COLORS: Record<
  Severity,
  { badge: string; dot: string; text: string; ring: string }
> = {
  critical: {
    badge: "bg-red-100 text-red-700 border-red-200",
    dot: "bg-red-500",
    text: "text-red-600",
    ring: "ring-red-200",
  },
  high: {
    badge: "bg-orange-100 text-orange-700 border-orange-200",
    dot: "bg-orange-500",
    text: "text-orange-600",
    ring: "ring-orange-200",
  },
  medium: {
    badge: "bg-amber-100 text-amber-700 border-amber-200",
    dot: "bg-amber-500",
    text: "text-amber-600",
    ring: "ring-amber-200",
  },
  low: {
    badge: "bg-sky-100 text-sky-700 border-sky-200",
    dot: "bg-sky-500",
    text: "text-sky-600",
    ring: "ring-sky-200",
  },
  info: {
    badge: "bg-slate-100 text-slate-600 border-slate-200",
    dot: "bg-slate-400",
    text: "text-slate-600",
    ring: "ring-slate-200",
  },
};

export function gradeColor(grade: string): string {
  switch (grade) {
    case "A":
      return "text-emerald-600";
    case "B":
      return "text-green-600";
    case "C":
      return "text-amber-600";
    case "D":
      return "text-orange-600";
    default:
      return "text-red-600";
  }
}
