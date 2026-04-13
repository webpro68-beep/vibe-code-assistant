"use client";

import React from "react";

export type PostPlanEvaluationPanelProps = {
  data?: {
    plan_id: string;
    status: string;
    outcome_label: string;
    evaluation_score: number;
    before_metrics_json?: Record<string, unknown> | null;
    after_metrics_json?: Record<string, unknown> | null;
    deltas_json?: Record<string, unknown> | null;
    evaluated_at?: string | null;
  } | null;
  loading?: boolean;
  error?: string | null;
  onEvaluate?: () => Promise<void>;
};

export default function PostPlanEvaluationPanel({
  data,
  loading = false,
  error = null,
  onEvaluate,
}: PostPlanEvaluationPanelProps) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-slate-900">Post-plan evaluation</h3>
          <p className="mt-1 text-sm text-slate-500">Evaluate actual outcome after plan completion.</p>
        </div>
        <button
          type="button"
          onClick={() => void onEvaluate?.()}
          className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white"
        >
          Evaluate
        </button>
      </div>

      {loading ? (
        <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
          Loading evaluation...
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div>
      ) : !data ? (
        <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
          No evaluation data.
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid gap-3 md:grid-cols-4">
            <Metric label="Status" value={data.status} />
            <Metric label="Outcome" value={data.outcome_label} />
            <Metric label="Score" value={data.evaluation_score.toFixed(2)} />
            <Metric label="Evaluated at" value={data.evaluated_at || "—"} />
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card title="Before metrics">
              <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-slate-700">
                {JSON.stringify(data.before_metrics_json || {}, null, 2)}
              </pre>
            </Card>

            <Card title="After metrics">
              <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-slate-700">
                {JSON.stringify(data.after_metrics_json || {}, null, 2)}
              </pre>
            </Card>

            <Card title="Deltas">
              <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-slate-700">
                {JSON.stringify(data.deltas_json || {}, null, 2)}
              </pre>
            </Card>
          </div>
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

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-200 p-4">
      <div className="mb-3 text-sm font-semibold text-slate-900">{title}</div>
      {children}
    </div>
  );
}
