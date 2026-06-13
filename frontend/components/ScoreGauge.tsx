"use client";

import { gradeColor } from "@/lib/types";

export function ScoreGauge({ score, grade }: { score: number; grade: string }) {
  const radius = 80;
  const stroke = 14;
  const normalized = radius - stroke / 2;
  const circumference = Math.PI * normalized; // half circle
  const clamped = Math.max(0, Math.min(100, score));
  const offset = circumference * (1 - clamped / 100);

  return (
    <div className="relative flex flex-col items-center">
      <svg width={radius * 2} height={radius + 20} viewBox={`0 0 ${radius * 2} ${radius + 20}`}>
        <path
          d={`M ${stroke / 2} ${radius} A ${normalized} ${normalized} 0 0 1 ${radius * 2 - stroke / 2} ${radius}`}
          fill="none"
          stroke="hsl(var(--muted))"
          strokeWidth={stroke}
          strokeLinecap="round"
        />
        <path
          d={`M ${stroke / 2} ${radius} A ${normalized} ${normalized} 0 0 1 ${radius * 2 - stroke / 2} ${radius}`}
          fill="none"
          stroke="hsl(var(--foreground))"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.8s ease" }}
        />
      </svg>
      <div className="absolute inset-x-0 top-7 flex flex-col items-center">
        <div className="text-5xl font-bold tabular-nums text-foreground">
          {Math.round(score)}
          <span className="text-xl font-medium text-muted-foreground">/100</span>
        </div>
        <div className={`mt-1 text-2xl font-extrabold ${gradeColor(grade)}`}>Grade {grade}</div>
      </div>
    </div>
  );
}
