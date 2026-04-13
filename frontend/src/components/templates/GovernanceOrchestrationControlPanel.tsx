"use client";

import React from "react";

export type GovernanceOrchestrationControlPanelProps = {
  onPause: (reason: string) => Promise<void>;
  onResume: () => Promise<void>;
  onCancel: (reason: string) => Promise<void>;
};

export default function GovernanceOrchestrationControlPanel({
  onPause,
  onResume,
  onCancel,
}: GovernanceOrchestrationControlPanelProps) {
  const [reason, setReason] = React.useState("");

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-slate-900">Orchestration control</h3>
      <p className="mt-1 text-sm text-slate-500">Pause, resume, or cancel plan execution.</p>

      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        className="mt-4 min-h-[96px] w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
        placeholder="Reason for pause or cancel"
      />

      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => onPause(reason || "Paused by operator")}
          className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700"
        >
          Pause
        </button>

        <button
          type="button"
          onClick={() => onResume()}
          className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white"
        >
          Resume
        </button>

        <button
          type="button"
          onClick={() => onCancel(reason || "Canceled by operator")}
          className="rounded-xl bg-rose-600 px-4 py-2 text-sm font-medium text-white"
        >
          Cancel
        </button>
      </div>
    </section>
  );
}
