"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getProductionRuns } from "@/lib/api";

export default function DashboardPage() {
  const [items, setItems] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProductionRuns().then((res) => setItems(res.items ?? [])).catch((err) => setError(String(err)));
  }, []);

  const filtered = useMemo(() => {
    return items.filter((item) => {
      const matchesStatus = statusFilter === "all" || item.status === statusFilter;
      const hay = `${item.title ?? ""} ${item.render_job_id ?? ""} ${item.current_stage ?? ""}`.toLowerCase();
      const matchesSearch = !search || hay.includes(search.toLowerCase());
      return matchesStatus && matchesSearch;
    });
  }, [items, search, statusFilter]);

  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-100 p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-3xl font-semibold">Production Dashboard</h1>
            <p className="text-neutral-400">Unified operator view for render, narration, music, mix, and mux.</p>
          </div>
          <Link href="/audio" className="rounded-2xl border border-neutral-700 px-4 py-3">Audio Studio</Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <input value={search} onChange={(e) => setSearch(e.target.value)} className="rounded-2xl bg-neutral-900 border border-neutral-800 p-3" placeholder="Search render job or title" />
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-2xl bg-neutral-900 border border-neutral-800 p-3">
            <option value="all">all statuses</option>
            <option value="queued">queued</option>
            <option value="running">running</option>
            <option value="blocked">blocked</option>
            <option value="needs_review">needs_review</option>
            <option value="failed">failed</option>
            <option value="succeeded">succeeded</option>
          </select>
          <div className="rounded-2xl bg-neutral-900 border border-neutral-800 p-3 text-sm text-neutral-400">{filtered.length} runs</div>
        </div>

        {error ? <div className="rounded-2xl border border-red-800 bg-red-950/30 p-4">{error}</div> : null}

        <div className="grid grid-cols-1 gap-4">
          {filtered.map((item) => (
            <Link key={item.id} href={`/render-jobs/${item.render_job_id ?? item.id}`} className="rounded-3xl border border-neutral-800 bg-neutral-900 p-5 hover:border-neutral-700 transition-colors">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="space-y-1">
                  <div className="text-lg font-medium">{item.title ?? item.render_job_id ?? item.id}</div>
                  <div className="text-sm text-neutral-500">run {item.id}</div>
                </div>
                <div className="text-sm px-3 py-1 rounded-full border border-neutral-700">{item.status}</div>
              </div>
              <div className="mt-4 h-2 bg-neutral-800 rounded-full overflow-hidden">
                <div className="h-full bg-white" style={{ width: `${item.percent_complete ?? 0}%` }} />
              </div>
              <div className="mt-4 grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
                <div><div className="text-neutral-500">Stage</div><div>{item.current_stage}</div></div>
                <div><div className="text-neutral-500">Progress</div><div>{item.percent_complete}%</div></div>
                <div><div className="text-neutral-500">Readiness</div><div>{item.output_readiness}</div></div>
                <div><div className="text-neutral-500">Worker</div><div>{item.active_worker ?? "-"}</div></div>
                <div><div className="text-neutral-500">Block</div><div>{item.blocking_reason ?? "-"}</div></div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
