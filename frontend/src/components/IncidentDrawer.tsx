"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import type { IncidentActionLogItem, RecentIncidentItem, RenderEventItem } from "@/src/lib/api";

function statusTone(status?: string | null) {
  const normalized = (status || "").toLowerCase();
  if (normalized.includes("failed") || normalized.includes("stalled")) return "border-rose-500/30 bg-rose-500/10 text-rose-100";
  if (normalized.includes("degraded") || normalized.includes("muted")) return "border-amber-500/30 bg-amber-500/10 text-amber-50";
  if (normalized.includes("completed") || normalized.includes("healthy") || normalized.includes("acknowledged") || normalized.includes("resolved")) return "border-emerald-500/30 bg-emerald-500/10 text-emerald-50";
  if (normalized.includes("assigned") || normalized.includes("open")) return "border-sky-500/30 bg-sky-500/10 text-sky-50";
  return "border-white/15 bg-white/5 text-white/75";
}

function formatTimestamp(value?: string | Date | null) {
  if (!value) return "—";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

function prettifyEventType(value?: string | null) {
  if (!value) return "Unknown";
  return value.replace(/_/g, " ");
}

function Badge({ tone, label }: { tone: "emerald" | "amber" | "sky"; label: string }) {
  const toneMap = {
    emerald: "border-emerald-500/25 bg-emerald-500/10 text-emerald-100",
    amber: "border-amber-500/25 bg-amber-500/10 text-amber-100",
    sky: "border-sky-500/25 bg-sky-500/10 text-sky-100",
  } as const;
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold ${toneMap[tone]}`}>{label}</span>;
}

function ActionButton({ label, onClick, loading, tone = "default", testId }: { label: string; onClick: () => void; loading?: boolean; tone?: "default" | "danger" | "success"; testId?: string; }) {
  const toneClass = tone === "danger" ? "border-rose-500/25 bg-rose-500/10 hover:bg-rose-500/15" : tone === "success" ? "border-emerald-500/25 bg-emerald-500/10 hover:bg-emerald-500/15" : "border-white/10 bg-white/10 hover:bg-white/15";
  return (
    <button data-testid={testId} type="button" onClick={onClick} disabled={!!loading} className={`rounded-xl border px-3 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60 ${toneClass}`}>
      {loading ? "Working…" : label}
    </button>
  );
}

export default function IncidentDrawer({
  incident,
  actor,
  assignee,
  actionReason,
  noteDraft,
  historyItems,
  actionItems,
  historyLoading,
  noteSaving,
  onActorChange,
  onAssigneeChange,
  onActionReasonChange,
  onNoteDraftChange,
  onSaveNote,
  onClose,
  onAcknowledge,
  onAssign,
  onMute,
  onResolve,
  onReopen,
  loadingAction,
}: {
  incident: RecentIncidentItem | null;
  actor: string;
  assignee: string;
  actionReason: string;
  noteDraft: string;
  historyItems: RenderEventItem[];
  actionItems: IncidentActionLogItem[];
  historyLoading?: boolean;
  noteSaving?: boolean;
  onActorChange: (value: string) => void;
  onAssigneeChange: (value: string) => void;
  onActionReasonChange: (value: string) => void;
  onNoteDraftChange: (value: string) => void;
  onSaveNote: () => void;
  onClose: () => void;
  onAcknowledge: () => void;
  onAssign: () => void;
  onMute: () => void;
  onResolve: () => void;
  onReopen: () => void;
  loadingAction?: "ack" | "assign" | "mute" | "resolve" | "reopen" | null;
}) {
  if (!incident) {
    return <section data-testid="incident-drawer" className="rounded-3xl border border-white/10 bg-white/5 p-5"><p className="text-lg font-semibold text-white">Incident detail</p><p className="mt-2 text-sm text-white/55">Select an incident from the feed to inspect and action it without leaving the dashboard.</p></section>;
  }

  const isResolved = (incident.workflow_status || incident.current_status || "").toLowerCase() === "resolved";

  return (
    <section data-testid="incident-drawer" className="rounded-3xl border border-white/10 bg-white/5 p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-lg font-semibold text-white">Incident operational panel</p>
          <p className="mt-1 text-xs text-white/45">{incident.incident_key}</p>
        </div>
        <button data-testid="incident-drawer-close" type="button" onClick={onClose} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/70 hover:bg-white/10">Close</button>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${statusTone(incident.current_status || incident.event_type)}`}>{incident.current_status || incident.event_type}</span>
        <span className="inline-flex rounded-full border border-white/15 bg-white/5 px-2.5 py-1 text-[11px] text-white/70">workflow: {incident.workflow_status || "open"}</span>
        {incident.acknowledged ? <Badge tone="emerald" label="acknowledged" /> : null}
        {incident.muted ? <Badge tone="amber" label="muted" /> : null}
        {incident.assigned_to ? <Badge tone="sky" label={`assigned: ${incident.assigned_to}`} /> : null}
      </div>

      <div className="mt-5 space-y-4 text-sm text-white/70">
        <div>
          <p className="text-xs uppercase tracking-wide text-white/40">Reason</p>
          <p className="mt-2 text-sm text-white/80">{incident.current_reason || incident.job.health_reason || incident.event_type}</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Meta label="Provider" value={incident.job.provider} />
          <Meta label="Project" value={incident.job.project_id} />
          <Meta label="Occurred at" value={formatTimestamp(incident.occurred_at)} />
          <Meta label="Job status" value={incident.job.status} />
        </div>
      </div>

      <Block title="Workflow history" subtitle="Persisted incident actions">
        {historyLoading ? <p className="text-sm text-white/45">Loading incident workflow history…</p> : actionItems.length === 0 ? <p className="text-sm text-white/45">No persisted actions yet.</p> : actionItems.map((item) => <div data-testid={`incident-history-item-${String(item.action_type).toLowerCase()}`} key={item.id} className="rounded-2xl border border-white/10 bg-white/5 p-3"><p className="text-sm font-semibold text-white/90">{prettifyEventType(item.action_type)}</p><p className="mt-1 text-[11px] text-white/45">{item.actor} · {formatTimestamp(item.created_at)}</p>{item.reason ? <p className="mt-2 text-xs text-white/75">{item.reason}</p> : null}</div>)}
      </Block>

      <Block title="Incident projected timeline" subtitle="Incident-specific backend projection">
        {historyLoading ? <p className="text-sm text-white/45">Loading projected timeline…</p> : historyItems.length === 0 ? <p className="text-sm text-white/45">No projected timeline available for this incident yet.</p> : historyItems.map((item) => <div data-testid={`incident-timeline-item-${String(item.event_type).toLowerCase().replace(/[^a-z0-9]+/g, "-")}`} key={item.id} className="rounded-2xl border border-white/10 bg-white/5 p-3"><div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold text-white/90">{prettifyEventType(item.event_type)}</p><p className="mt-1 text-[11px] text-white/45">{formatTimestamp(item.occurred_at)} · {item.source}</p></div>{item.status ? <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusTone(item.status)}`}>{item.status}</span> : null}</div>{item.payload?.reason ? <p className="mt-2 text-xs text-white/75">{String(item.payload.reason)}</p> : null}{item.error_message ? <p className="mt-2 text-xs text-rose-200/90">{item.error_message}</p> : null}</div>)}
      </Block>

      <Block title="Operational note" subtitle="Persisted in backend incident state">
        <textarea data-testid="incident-note-input" value={noteDraft} onChange={(e) => onNoteDraftChange(e.target.value)} placeholder="Write operator context, handoff note, or remediation context…" className="mt-3 min-h-[110px] w-full rounded-2xl border border-white/10 bg-white/5 px-3 py-3 text-sm text-white outline-none placeholder:text-white/25" />
        <div className="mt-3 flex gap-2"><ActionButton testId="incident-save-note" label={noteSaving ? "Saving…" : "Save note"} onClick={onSaveNote} loading={noteSaving} /></div>
      </Block>

      <Block title="Operator action">
        <label className="block text-xs text-white/50">Actor<input value={actor} onChange={(e) => onActorChange(e.target.value)} className="mt-1 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none" /></label>
        <label className="mt-3 block text-xs text-white/50">Assign to<input value={assignee} onChange={(e) => onAssigneeChange(e.target.value)} className="mt-1 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none" /></label>
        <label className="mt-3 block text-xs text-white/50">Action reason<textarea value={actionReason} onChange={(e) => onActionReasonChange(e.target.value)} placeholder="Reason sent to backend." className="mt-1 min-h-[84px] w-full rounded-2xl border border-white/10 bg-white/5 px-3 py-3 text-sm text-white outline-none placeholder:text-white/25" /></label>
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          <ActionButton label="Ack" onClick={onAcknowledge} loading={loadingAction === "ack"} />
          <ActionButton label="Assign" onClick={onAssign} loading={loadingAction === "assign"} />
          <ActionButton label="Mute 1h" onClick={onMute} loading={loadingAction === "mute"} />
          {isResolved ? <ActionButton label="Reopen" onClick={onReopen} loading={loadingAction === "reopen"} tone="success" /> : <ActionButton label="Resolve" onClick={onResolve} loading={loadingAction === "resolve"} tone="danger" />}
        </div>
      </Block>

      <div className="mt-5 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-white/65">
        <p className="text-xs uppercase tracking-wide text-white/40">Job snapshot</p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2"><Meta label="Planned scenes" value={String(incident.job.planned_scene_count)} /><Meta label="Processing scenes" value={String(incident.job.processing_scene_count)} /><Meta label="Succeeded scenes" value={String(incident.job.succeeded_scene_count)} /><Meta label="Failed scenes" value={String(incident.job.failed_scene_count_snapshot)} /></div>
        <div className="mt-4"><Link href={`/render-jobs/${incident.job.job_id}`} className="text-xs font-semibold text-emerald-300 hover:text-emerald-200">Open full job detail →</Link></div>
      </div>
    </section>
  );
}

function Block({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return <div className="mt-5 rounded-2xl border border-white/10 bg-black/20 p-4"><div className="flex items-center justify-between gap-3"><p className="text-xs uppercase tracking-wide text-white/40">{title}</p>{subtitle ? <span className="text-[11px] text-white/35">{subtitle}</span> : null}</div><div className="mt-3 max-h-72 space-y-3 overflow-auto pr-1">{children}</div></div>;
}

function Meta({ label, value }: { label: string; value?: string | null }) {
  return <div><p className="text-[11px] uppercase tracking-wide text-white/35">{label}</p><p className="mt-1 text-sm text-white/80">{value || "—"}</p></div>;
}
