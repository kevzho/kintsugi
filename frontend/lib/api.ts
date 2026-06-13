import type { DemoInfo, Report } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

export async function analyze(file: File, target?: string): Promise<Report> {
  const form = new FormData();
  form.append("file", file);
  if (target && target.trim()) form.append("target", target.trim());
  const res = await fetch(`${API_URL}/analyze`, {
    method: "POST",
    body: form,
  });
  return handle<Report>(res);
}

export async function analyzeDemo(demoId: string, target?: string): Promise<Report> {
  const res = await fetch(`${API_URL}/analyze/demo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
