"use client";

const VISITOR_ID_KEY = "kintsugi_visitor_id";
const SESSION_ID_KEY = "kintsugi_session_id";

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

export function getUsageIdentityHeaders(): Record<string, string> {
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

export function getJsonUsageHeaders(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    ...getUsageIdentityHeaders(),
  };
}
