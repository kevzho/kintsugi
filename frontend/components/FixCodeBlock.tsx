"use client";

import * as React from "react";
import { Check, Copy } from "lucide-react";

import { cn } from "@/lib/utils";

export interface FixCode {
  type?: string;
  code: string;
}

const KEYWORDS = new Set([
  "as",
  "class",
  "def",
  "else",
  "False",
  "for",
  "from",
  "if",
  "import",
  "in",
  "None",
  "return",
  "True",
  "with",
]);

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

export function highlightedCodeHtml(code: string, language = "plaintext"): string {
  const lang = language.toLowerCase();
  if (!["python", "pandas", "sklearn", "sql"].includes(lang)) {
    return escapeHtml(code);
  }
  if (lang === "sql") {
    return escapeHtml(code).replace(
      /\b(select|from|where|join|left|right|inner|outer|group|by|order|limit|case|when|then|else|end|as|and|or|not|null)\b/gi,
      '<span class="text-foreground font-semibold">$1</span>',
    );
  }
  return code.split("\n").map((line) => highlightPythonLine(line)).join("\n");
}

function highlightPythonLine(line: string): string {
  let out = "";
  let i = 0;
  while (i < line.length) {
    const ch = line[i];
    if (ch === "#") {
      out += `<span class="text-muted-foreground">${escapeHtml(line.slice(i))}</span>`;
      break;
    }
    if (ch === "'" || ch === '"') {
      const quote = ch;
      let end = i + 1;
      while (end < line.length) {
        if (line[end] === quote && line[end - 1] !== "\\") {
          end += 1;
          break;
        }
        end += 1;
      }
      out += `<span class="text-foreground/80">${escapeHtml(line.slice(i, end))}</span>`;
      i = end;
      continue;
    }
    if (/[A-Za-z_]/.test(ch)) {
      let end = i + 1;
      while (end < line.length && /[A-Za-z0-9_]/.test(line[end])) {
        end += 1;
      }
      const word = line.slice(i, end);
      if (KEYWORDS.has(word)) {
        out += `<span class="text-foreground font-semibold">${word}</span>`;
      } else {
        out += escapeHtml(word);
      }
      i = end;
      continue;
    }
    out += escapeHtml(ch);
    i += 1;
  }
  return out;
}

function languageLabel(language = "plaintext") {
  const lang = language.toLowerCase();
  if (lang === "pandas" || lang === "sklearn") return "Python";
  if (lang === "sql") return "SQL";
  if (lang === "python") return "Python";
  return "Plaintext";
}

export function FixCodeBlock({
  fix,
  className,
}: {
  fix: FixCode;
  className?: string;
}) {
  const [copied, setCopied] = React.useState(false);
  const language = fix.type || "plaintext";
  const code = fix.code || "";

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };

  return (
    <div className={cn("overflow-hidden rounded-lg border bg-background", className)} data-testid="fix-code-block">
      <div className="flex items-center justify-between border-b bg-muted/50 px-3 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {languageLabel(language)}
        </span>
        <button
          type="button"
          onClick={copy}
          className="inline-flex h-8 items-center gap-2 rounded-md border bg-card px-2.5 text-xs font-medium text-foreground shadow-sm transition hover:bg-accent hover:text-accent-foreground"
          aria-label="Copy code"
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 text-xs leading-5">
        <code
          className="font-mono text-foreground"
          data-language={language}
          data-code={code}
          dangerouslySetInnerHTML={{ __html: highlightedCodeHtml(code, language) }}
        />
      </pre>
    </div>
  );
}
