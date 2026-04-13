"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getRenderJobTimeline } from "@/lib/api";

function badgeClass(status: string) {
  switch (status) {
    case "succeeded": return "border-emerald-700 text-emerald-300";
    case "failed": return "border-red-700 text-red-300";
    case "blocked": return "border-amber-700 text-amber-300";
    case "running": return "border-blue-700 text-blue-300";
    default: return "border-neutral-700 text-neutral-300";
  }
}

export default function RenderJobDetailPage({ params }: { params: { id: string } }) {
  const [detail, setDetail] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"overview" | "timeline" | "audio" | "outputs">("overview");

  useEffect(() => {
    getRenderJobTimeline(params.id).then(setDetail).catch((err) => setError(String(err)));
  }, [params.id]);

  const grouped = useMemo(() => {
    const phases = new Map<string, any[]>();
    for (const event of detail?.timeline ?? []) {
      const arr = phases.get(event.phase) ?? [];
      arr.push(event);
      phases.set(event.phase, arr);
    }
    return Array.from(phases.entries());
  }, [detail]);

  if (error) {
    return <main className="min-h-screen bg-neutral-950 text-neutral-100 p-8"><div className="rounded-2xl border border-red-800 bg-red-950/30 p-4">{error}</div></main>;
  }

  const run = detail?.run;
  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-100 p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <div className="text-sm text-neutral-500">Render job</div>
            <h1 className="text-3xl font-semibold">{run?.title ?? run?.render_job_id ?? params.id}</h1>
          </div>
          <Link href="/dashboard" className="rounded-2xl border border-neutral-700 px-4 py-3">Back to dashboard</Link>
        </div>

        <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-5">
          <div className="flex gap-2 flex-wrap">
            {(["overview", "timeline", "audio", "outputs"] as const).map((key) => (
              <button key={key} onClick={() => setTab(key)} className={`rounded-2xl px-4 py-2 border ${tab === key ? "bg-white text-black border-white" : "border-neutral-700"}`}>{key}</button>
            ))}
          </div>
        </div>

        {tab === "overview" ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-5"><div className="text-neutral-500 text-sm">Status</div><div className="text-xl font-semibold mt-2">{run?.status ?? "-"}</div></div>
            <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-5"><div className="text-neutral-500 text-sm">Stage</div><div className="text-xl font-semibold mt-2">{run?.current_stage ?? "-"}</div></div>
            <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-5"><div className="text-neutral-500 text-sm">Progress</div><div className="text-xl font-semibold mt-2">{run?.percent_complete ?? 0}%</div></div>
            <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-5"><div className="text-neutral-500 text-sm">Output</div><div className="text-xl font-semibold mt-2">{run?.output_readiness ?? "-"}</div></div>
          </div>
        ) : null}

        {tab === "timeline" ? (
          <div className="space-y-6">
            {grouped.map(([phase, events]) => (
              <section key={phase} className="rounded-3xl border border-neutral-800 bg-neutral-900 p-5">
                <h2 className="text-xl font-semibold capitalize mb-4">{phase}</h2>
                <div className="space-y-3">
                  {events.map((event) => (
                    <div key={event.id} className="rounded-2xl border border-neutral-800 p-4">
                      <div className="flex items-start justify-between gap-3 flex-wrap">
                        <div>
                          <div className="font-medium">{event.title}</div>
                          <div className="text-sm text-neutral-400">{event.message ?? event.stage}</div>
                        </div>
                        <div className={`text-xs rounded-full px-3 py-1 border ${badgeClass(event.status)}`}>{event.status}</div>
                      </div>
                      <div className="mt-3 grid grid-cols-2 md:grid-cols-5 gap-3 text-sm text-neutral-400">
                        <div><span className="text-neutral-500">Stage:</span> {event.stage}</div>
                        <div><span className="text-neutral-500">Worker:</span> {event.worker_name ?? "-"}</div>
                        <div><span className="text-neutral-500">Provider:</span> {event.provider ?? "-"}</div>
                        <div><span className="text-neutral-500">Progress:</span> {event.progress_percent ?? "-"}</div>
                        <div><span className="text-neutral-500">At:</span> {new Date(event.occurred_at).toLocaleString()}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : null}

        {tab === "audio" ? (
          <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-5 space-y-4">
            <h2 className="text-xl font-semibold">Audio phases</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {(detail?.timeline ?? []).filter((e: any) => ["narration", "music", "mix", "mux"].includes(e.phase)).map((event: any) => (
                <div key={event.id} className="rounded-2xl border border-neutral-800 p-4">
                  <div className="text-sm text-neutral-500 uppercase">{event.phase}</div>
                  <div className="font-medium mt-1">{event.title}</div>
                  <div className="text-sm text-neutral-400 mt-1">{event.message ?? "-"}</div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {tab === "outputs" ? (
          <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-5 space-y-4">
            <h2 className="text-xl font-semibold">Outputs</h2>
            <div className="text-sm text-neutral-400">Readiness: {run?.output_readiness ?? "-"}</div>
            <div className="text-sm">URL: {run?.output_url ?? "-"}</div>
          </div>
        ) : null}
      </div>
    </main>
  );
}
