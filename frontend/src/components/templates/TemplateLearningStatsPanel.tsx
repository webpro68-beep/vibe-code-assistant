"use client";

import React from "react";

type LearningStat = {
  id: string;
  scope_key: string;
  sample_count: number;
  success_count: number;
  failure_count: number;
  retry_count: number;
  rerender_count: number;
  avg_render_score: number;
  avg_upload_score: number;
  avg_retention_score: number;
  avg_final_priority_score: number;
  success_rate: number;
  retry_rate: number;
  rerender_rate: number;
  avg_scene_failure_rate: number;
  stability_index: number;
  reuse_effectiveness: number;
  dominance_confidence: number;
  last_7d_score: number;
  last_30d_score: number;
  trend_direction: string;
  updated_from_project_id?: string | null;
  updated_at?: string | null;
};

type LearningSummary = {
  scopes: number;
  sample_count: number;
  avg_final_priority_score: number;
  avg_stability_index: number;
  avg_dominance_confidence: number;
};

export type TemplateLearningStatsPanelProps = {
  templateId: string;
  loading?: boolean;
  error?: string | null;
  summary?: LearningSummary | null;
  stats?: LearningStat[];
};

function pct(value: number): string {
  return `${(Number(value || 0) * 100).toFixed(1)}%`;
}

function num(value: number): string {
  return Number(value || 0).toFixed(2);
}

function trendBadge(trend: string): string {
  switch (trend) {
    case "up":
      return "bg-emerald-100 text-emerald-700";
    case "down":
      return "bg-rose-100 text-rose-700";
    default:
      return "bg-slate-100 text-slate-700";
  }
}

export default function TemplateLearningStatsPanel({
  templateId,
  loading = false,
  error = null,
  summary = null,
  stats = [],
}: TemplateLearningStatsPanelProps) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-slate-900">Learning stats</h3>
          <p className="mt-1 text-sm text-slate-500">
            Aggregated runtime learning for template <span className="font-medium">{templateId}</span>
          </p>
        </div>
        {summary ? (
          <div className="grid grid-cols-2 gap-2 text-right sm:grid-cols-5">
            <Metric label="Scopes" value={String(summary.scopes)} />
            <Metric label="Samples" value={String(summary.sample_count)} />
            <Metric label="Avg priority" value={num(summary.avg_final_priority_score)} />
            <Metric label="Avg stability" value={num(summary.avg_stability_index)} />
            <Metric label="Avg dominance" value={num(summary.avg_dominance_confidence)} />
          </div>
        ) : null}
      </div>

      {loading ? (
        <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
          Loading learning stats...
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div>
      ) : stats.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
          No learning stats yet.
        </div>
      ) : (
        <div className="space-y-3">
          {stats.map((stat) => (
            <div key={stat.id} className="rounded-2xl border border-slate-200 p-4">
              <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-slate-900">{stat.scope_key}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    Samples {stat.sample_count} · Source project {stat.updated_from_project_id || "—"}
                  </div>
                </div>
                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${trendBadge(stat.trend_direction)}`}>
                  {stat.trend_direction || "flat"}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
                <Cell label="Render" value={num(stat.avg_render_score)} />
                <Cell label="Upload" value={num(stat.avg_upload_score)} />
                <Cell label="Retention" value={num(stat.avg_retention_score)} />
                <Cell label="Final priority" value={num(stat.avg_final_priority_score)} />
                <Cell label="Success rate" value={pct(stat.success_rate)} />
                <Cell label="Retry rate" value={pct(stat.retry_rate)} />
                <Cell label="Rerender rate" value={pct(stat.rerender_rate)} />
                <Cell label="Scene failure" value={pct(stat.avg_scene_failure_rate)} />
                <Cell label="Stability" value={num(stat.stability_index)} />
                <Cell label="Reuse effectiveness" value={num(stat.reuse_effectiveness)} />
                <Cell label="Dominance confidence" value={num(stat.dominance_confidence)} />
                <Cell label="7d / 30d" value={`${num(stat.last_7d_score)} / ${num(stat.last_30d_score)}`} />
              </div>
            </div>
          ))}
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

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-slate-50 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-slate-900">{value}</div>
    </div>
  );
}
