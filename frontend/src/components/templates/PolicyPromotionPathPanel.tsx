"use client";

import React from "react";

export type PolicyPromotionPathPanelProps = {
  data?: {
    plan_id: string;
    path_type: string;
    status: string;
    confidence_delta: number;
    approval_requirement_delta: number;
    cooldown_delta_seconds: number;
    recommendation_reason?: string | null;
    payload_json?: Record<string, unknown> | null;
  } | null;
  loading?: boolean;
  error?: string | null;
  onEvaluate?: () => Promise<void>;
};

export default function PolicyPromotionPathPanel({
  data,
  loading = false,
  error = null,
  onEvaluate,
}: PolicyPromotionPathPanelProps) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-slate-900">Policy promotion path</h3>
          <p className="mt-1 text-sm text-slate-500">Promote, hold, or demote policy path from real plan outcome.</p>
        </div>
        <button
          type="button"
          onClick={() => void onEvaluate?.()}
          className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white"
        >
          Evaluate policy path
        </button>
      </div>

      {loading ? (
        <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
          Loading policy path...
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div>
      ) : !data ? (
        <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
          No policy path data.
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid gap-3 md:grid-cols-5">
            <Metric label="Path type" value={data.path_type} />
            <Metric label="Status" value={data.status} />
            <Metric label="Confidence Δ" value={data.confidence_delta.toFixed(2)} />
            <Metric label="Approval Δ" value={String(data.approval_requirement_delta)} />
            <Metric label="Cooldown Δ" value={`${data.cooldown_delta_seconds}s`} />
          </div>

          {data.recommendation_reason ? (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
              {data.recommendation_reason}
            </div>
          ) : null}

          {data.payload_json ? (
            <div className="rounded-xl border border-slate-200 p-4">
              <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-slate-700">
                {JSON.stringify(data.payload_json, null, 2)}
              </pre>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-slate-50 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-slate-900">{value}</div>
    </div>
  );
}
