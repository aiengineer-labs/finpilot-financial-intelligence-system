"use client";

import { useSyncExternalStore } from "react";
import { THEME_STORAGE_KEY as STORAGE_KEY } from "@/lib/theme-boot";
import { Icon } from "./icons";

export type ThemePreference = "system" | "light" | "dark";
const listeners = new Set<() => void>();

function read(): ThemePreference {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    return "system";
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function setThemePreference(preference: ThemePreference) {
  try {
    if (preference === "system") window.localStorage.removeItem(STORAGE_KEY);
    else window.localStorage.setItem(STORAGE_KEY, preference);
  } catch {
    // Storage can be unavailable (private mode); the choice still applies to this page.
  }
  if (preference === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = preference;
  listeners.forEach((listener) => listener());
}

export function useThemePreference() {
  return useSyncExternalStore(subscribe, read, () => "system" as ThemePreference);
}

const order: ThemePreference[] = ["system", "light", "dark"];

export function ThemeToggle() {
  const preference = useThemePreference();
  const next = order[(order.indexOf(preference) + 1) % order.length];
  const icon = preference === "light" ? "sun" : preference === "dark" ? "moon" : "monitor";
  return (
    <button type="button" className="icon-btn" onClick={() => setThemePreference(next)} aria-label={`Theme: ${preference}. Switch to ${next}`} title={`Theme: ${preference}`}>
      <Icon name={icon} size={17} />
    </button>
  );
}
