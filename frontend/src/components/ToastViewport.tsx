"use client";

import { useEffect } from "react";

export type ToastTone = "success" | "error" | "info";

export interface ToastItem {
  id: string;
  title: string;
  description?: string;
  tone?: ToastTone;
}

const toneClasses: Record<ToastTone, string> = {
  success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-50",
  error: "border-rose-500/30 bg-rose-500/10 text-rose-50",
  info: "border-sky-500/30 bg-sky-500/10 text-sky-50",
};

export default function ToastViewport({
  items,
  onDismiss,
  autoDismissMs = 3200,
}: {
  items: ToastItem[];
  onDismiss: (id: string) => void;
  autoDismissMs?: number;
}) {
  useEffect(() => {
    if (items.length === 0) return;
    const timers = items.map((item) =>
      window.setTimeout(() => onDismiss(item.id), autoDismissMs),
    );
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [items, onDismiss, autoDismissMs]);

  if (items.length === 0) return null;

  return (
    <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-full max-w-sm flex-col gap-3">
      {items.map((item) => {
        const tone = item.tone || "info";
        return (
          <div
            key={item.id}
            className={`pointer-events-auto rounded-2xl border p-4 shadow-2xl backdrop-blur ${toneClasses[tone]}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">{item.title}</p>
                {item.description ? (
                  <p className="mt-1 text-xs opacity-80">{item.description}</p>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => onDismiss(item.id)}
                className="rounded-lg px-2 py-1 text-xs opacity-70 transition hover:opacity-100"
              >
                Close
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
