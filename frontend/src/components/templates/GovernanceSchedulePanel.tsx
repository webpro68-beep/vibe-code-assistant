"use client";

import React from "react";

export type GovernanceSchedulePanelProps = {
  onSaveSchedule: (payload: {
    scheduledAt?: string | null;
    executionWindowStart?: string | null;
    executionWindowEnd?: string | null;
    allowRunOutsideWindow: boolean;
  }) => Promise<void>;
};

export default function GovernanceSchedulePanel({
  onSaveSchedule,
}: GovernanceSchedulePanelProps) {
  const [scheduledAt, setScheduledAt] = React.useState("");
  const [windowStart, setWindowStart] = React.useState("");
  const [windowEnd, setWindowEnd] = React.useState("");
  const [allowOutside, setAllowOutside] = React.useState(false);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-slate-900">Plan schedule</h3>
      <p className="mt-1 text-sm text-slate-500">Set scheduled time and allowed execution window.</p>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Field label="Scheduled at (ISO datetime)">
          <input
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
            className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
            placeholder="2026-04-13T10:00:00+07:00"
          />
        </Field>

        <Field label="Execution window start">
          <input
            value={windowStart}
            onChange={(e) => setWindowStart(e.target.value)}
            className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
            placeholder="2026-04-13T09:00:00+07:00"
          />
        </Field>

        <Field label="Execution window end">
          <input
            value={windowEnd}
            onChange={(e) => setWindowEnd(e.target.value)}
            className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
            placeholder="2026-04-13T18:00:00+07:00"
          />
        </Field>

        <label className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700">
          <input type="checkbox" checked={allowOutside} onChange={(e) => setAllowOutside(e.target.checked)} />
          Allow run outside window
        </label>
      </div>

      <button
        type="button"
        onClick={() =>
          onSaveSchedule({
            scheduledAt: scheduledAt || null,
            executionWindowStart: windowStart || null,
            executionWindowEnd: windowEnd || null,
            allowRunOutsideWindow: allowOutside,
          })
        }
        className="mt-4 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white"
      >
        Save schedule
      </button>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="mb-1.5 text-sm font-medium text-slate-800">{label}</div>
      {children}
    </label>
  );
}
