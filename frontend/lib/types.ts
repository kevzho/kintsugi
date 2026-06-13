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
  integrity_penalty: number;
  readiness_penalty: number;
  category: "data_integrity" | "modeling_warning" | string;
}

export interface ColumnProfile {
  dtype_inferred: string;
  n_unique: number;
  cardinality_ratio: number;
  null_rate: number;
  sample_values: string[];
  is_id_like: boolean;
  name_kind?: string;
  column_role?: string;
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
  integrity_score: number;
  integrity_grade: string;
  readiness_score: number;
  readiness_grade: string;
  overall_score: number;
  overall_grade: string;
  verdict: string;
  dataset_type: string;
  findings: Finding[];
  modeling_warnings: Finding[];
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
    badge: "border-foreground/30 bg-background text-foreground",
    dot: "bg-foreground",
    text: "text-foreground",
    ring: "ring-foreground/20",
  },
  high: {
    badge: "border-foreground/20 bg-muted text-foreground",
    dot: "bg-foreground/80",
    text: "text-foreground",
    ring: "ring-foreground/20",
  },
  medium: {
    badge: "border-border bg-secondary text-secondary-foreground",
    dot: "bg-foreground/60",
    text: "text-foreground",
    ring: "ring-foreground/15",
  },
  low: {
    badge: "border-border bg-background text-muted-foreground",
    dot: "bg-muted-foreground",
    text: "text-muted-foreground",
    ring: "ring-border",
  },
  info: {
    badge: "border-border bg-background text-muted-foreground",
    dot: "bg-muted-foreground/70",
    text: "text-muted-foreground",
    ring: "ring-border",
  },
};

export function gradeColor(grade: string): string {
  switch (grade) {
    case "A":
    case "B":
    case "C":
    case "D":
    default:
      return "text-foreground";
  }
}
