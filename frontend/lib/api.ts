import type { DemoInfo, Report } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const VISITOR_ID_KEY = "kintsugi_visitor_id";
const SESSION_ID_KEY = "kintsugi_session_id";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export async function getDemos(): Promise<DemoInfo[]> {
  const res = await fetch(`${API_URL}/demos`, { cache: "no-store" });
  const data = await handle<{ demos: DemoInfo[] }>(res);
  return data.demos;
}

function randomId(prefix: string): string {
  const cryptoObj = typeof crypto !== "undefined" ? crypto : null;
  if (cryptoObj && "randomUUID" in cryptoObj) {
    return `${prefix}_${cryptoObj.randomUUID()}`;
  }
  return `${prefix}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

function getStoredId(storage: Storage | null, key: string, prefix: string): string {
  if (typeof window === "undefined") return randomId(prefix);
  const next = randomId(prefix);
  if (!storage) return next;
  try {
    const existing = storage.getItem(key);
    if (existing) return existing;
    storage.setItem(key, next);
  } catch {
    return next;
  }
  return next;
}

function usageHeaders(): Record<string, string> {
  return {
    "X-Kintsugi-Visitor-Id": getStoredId(
      typeof window !== "undefined" ? window.localStorage : null,
      VISITOR_ID_KEY,
      "visitor"
    ),
    "X-Kintsugi-Session-Id": getStoredId(
      typeof window !== "undefined" ? window.sessionStorage : null,
      SESSION_ID_KEY,
      "session"
    ),
  };
}

export async function analyze(file: File, target?: string): Promise<Report> {
  const form = new FormData();
  form.append("file", file);
  if (target && target.trim()) form.append("target", target.trim());
  const res = await fetch(`${API_URL}/analyze`, {
    method: "POST",
    headers: usageHeaders(),
    body: form,
  });
  return handle<Report>(res);
}

export async function analyzeDemo(demoId: string, target?: string): Promise<Report> {
  const res = await fetch(`${API_URL}/analyze/demo`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...usageHeaders() },
    body: JSON.stringify({
      demo_id: demoId,
      ...(target && target.trim() ? { target: target.trim() } : {}),
    }),
  });
  return handle<Report>(res);
}

export async function ping(): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

export { API_URL };
