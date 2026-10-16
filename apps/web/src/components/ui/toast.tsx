"use client";

import { useCallback, useRef, useState } from "react";
import { Icon } from "./icons";

export type ToastTone = "success" | "error" | "info";
export type Toast = { id: number; tone: ToastTone; title: string; body?: string };

export function useToasts() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counter = useRef(0);
  const dismiss = useCallback((id: number) => setToasts((current) => current.filter((toast) => toast.id !== id)), []);
  const push = useCallback((toast: Omit<Toast, "id">) => {
    counter.current += 1;
    const id = counter.current;
    setToasts((current) => [...current.slice(-2), { ...toast, id }]);
    window.setTimeout(() => dismiss(id), toast.tone === "error" ? 9000 : 5200);
  }, [dismiss]);
  return { toasts, push, dismiss };
}

export function ToastStack({ toasts, dismiss }: { toasts: Toast[]; dismiss: (id: number) => void }) {
  return (
    <div className="toast-stack" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast glass-strong toast-${toast.tone}`}>
          <span className="toast-icon"><Icon name={toast.tone === "success" ? "check" : toast.tone === "error" ? "alert" : "info"} size={15} /></span>
          <div><b>{toast.title}</b>{toast.body && <p>{toast.body}</p>}</div>
          <button type="button" className="icon-btn ghost" aria-label="Dismiss notification" onClick={() => dismiss(toast.id)}><Icon name="close" size={14} /></button>
        </div>
      ))}
    </div>
  );
}
