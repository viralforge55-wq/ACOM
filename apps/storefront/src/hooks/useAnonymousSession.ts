"use client";

import { useCallback } from "react";

const STORAGE_KEY = "acom_anon_session_v1";
const ROTATION_MS = 30 * 24 * 60 * 60 * 1000; // 30 days per DATA_DICTIONARY.md §3

type StoredSession = {
  id: string;
  createdAt: number;
};

function generateAnonymousId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `s_${crypto.randomUUID().replace(/-/g, "")}`;
  }
  const bytes = new Uint8Array(16);
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    crypto.getRandomValues(bytes);
  }
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `s_${hex || Date.now().toString(36).padEnd(16, "0")}`;
}

/**
 * Manages a random anonymous session ID (rotated every 30 days).
 * Contains zero PII and performs no device fingerprinting.
 */
export function useAnonymousSession(): { getSessionId: () => string } {
  const getSessionId = useCallback((): string => {
    if (typeof window === "undefined") {
      return generateAnonymousId();
    }
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<StoredSession>;
        if (
          typeof parsed.id === "string" &&
          typeof parsed.createdAt === "number" &&
          Date.now() - parsed.createdAt < ROTATION_MS
        ) {
          return parsed.id;
        }
      }
      const fresh: StoredSession = { id: generateAnonymousId(), createdAt: Date.now() };
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(fresh));
      return fresh.id;
    } catch {
      return generateAnonymousId();
    }
  }, []);

  return { getSessionId };
}
