"use client";

import React from "react";

type CompetitionRecord = {
  id: string;
  compared_against_template_id: string;
  scope_key: string;
  win_count: number;
  loss_count: number;
  tie_count: number;
  sample_count: number;
  avg_score_delta: number;
  avg_retention_delta: number;
  avg_render_delta: number;
  avg_upload_delta: number;
  last_compared_at?: string | null;
};

type CompetitionSummary = {
  opponents: number;
  sample_count: number;
  win_count: number;
  loss_count: number;
  tie_count: number;
};

export type TemplateCompetitionPanelProps = {
  templateId: string;
  loading?: boolean;
  error?: string | null;
  summary?: CompetitionSummary | null;
  records?: CompetitionRecord[];
};

function formatDelta(value: number): string {
  const n = Number(value || 0);
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}`;
}

function winRate(summary?: CompetitionSummary | null): string {
  if (!summary) return "—";
  const total = summary.win_count + summary.loss_count + summary.tie_count;
  if (total === 0) return "0%";
  return `${((summary.win_count / total) * 100).toFixed(1)}%`;
}

function badgeClass(record: CompetitionRecord): string {
  if (record.avg_score_delta >= 3 && record.avg_retention_delta >= 3) {
    return "bg-emerald-100 text-emerald-700";
  }
  if (record.avg_score_delta <= -3 || record.avg_retention_delta <= -3) {
    return "bg-rose-100 text-rose-700";
  }
  return "bg-slate-100 text-slate-700";
}

export default function TemplateCompetitionPanel({
  templateId,
  loading = false,
  error = null,
  summary = null,
  records = [],
}: TemplateCompetitionPanelProps) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-slate-900">Competition</h3>
          <p className="mt-1 text-sm text-slate-500">
            Head-to-head performance for template <span className="font-medium">{templateId}</span>
          </p>
        </div>
        {summary ? (
          <div className="grid grid-cols-2 gap-2 text-right sm:grid-cols-4">
            <Metric label="Opponents" value={String(summary.opponents)} />
            <Metric label="Samples" value={String(summary.sample_count)} />
            <Metric label="Wins" value={String(summary.win_count)} />
            <Metric label="Win rate" value={winRate(summary)} />
          </div>
        ) : null}
      </div>

      {loading ? (
        <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
          Loading competition records...
        </div>
      ) : error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div>
      ) : records.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
          No competition data yet.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full border-separate border-spacing-y-2">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="px-3 py-2">Opponent</th>
                <th className="px-3 py-2">Scope</th>
                <th className="px-3 py-2">W / L / T</th>
                <th className="px-3 py-2">Samples</th>
                <th className="px-3 py-2">Score Δ</th>
                <th className="px-3 py-2">Retention Δ</th>
                <th className="px-3 py-2">Render Δ</th>
                <th className="px-3 py-2">Upload Δ</th>
                <th className="px-3 py-2">Signal</th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <tr key={record.id} className="rounded-xl bg-slate-50 text-sm text-slate-700">
                  <td className="rounded-l-xl px-3 py-3 font-medium text-slate-900">
                    {record.compared_against_template_id}
                  </td>
                  <td className="px-3 py-3 text-xs text-slate-600">{record.scope_key}</td>
                  <td className="px-3 py-3">
                    {record.win_count} / {record.loss_count} / {record.tie_count}
                  </td>
                  <td className="px-3 py-3">{record.sample_count}</td>
                  <td className="px-3 py-3">{formatDelta(record.avg_score_delta)}</td>
                  <td className="px-3 py-3">{formatDelta(record.avg_retention_delta)}</td>
                  <td className="px-3 py-3">{formatDelta(record.avg_render_delta)}</td>
                  <td className="px-3 py-3">{formatDelta(record.avg_upload_delta)}</td>
                  <td className="rounded-r-xl px-3 py-3">
                    <span
                      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${badgeClass(record)}`}
                    >
                      {record.avg_score_delta >= 0 ? "Positive" : "Pressure"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
