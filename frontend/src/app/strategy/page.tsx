"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { activateStrategyMode, createStrategySignal, getStrategyBusinessOutcomes, getStrategyDirectives, getStrategyPortfolio, getStrategySlaRisk, getStrategyState } from "@/lib/api";
import StrategyStateCard from "@/components/strategy/StrategyStateCard";
import PortfolioAllocationTable from "@/components/strategy/PortfolioAllocationTable";
import DirectivePanel from "@/components/strategy/DirectivePanel";
import SlaRiskHeatmap from "@/components/strategy/SlaRiskHeatmap";
import CampaignTimeline from "@/components/strategy/CampaignTimeline";

export default function StrategyPage() {
  const [state, setState] = useState<any | null>(null);
  const [slaRisk, setSlaRisk] = useState<any | null>(null);
  const [portfolio, setPortfolio] = useState<any | null>(null);
  const [directives, setDirectives] = useState<any[]>([]);
  const [businessOutcomes, setBusinessOutcomes] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState("balanced");

  async function refresh() {
    const [s, risk, p, d, bo] = await Promise.all([
      getStrategyState(),
      getStrategySlaRisk(),
      getStrategyPortfolio(),
      getStrategyDirectives(),
      getStrategyBusinessOutcomes(),
    ]);
    setState(s);
    setSlaRisk(risk);
    setPortfolio(p);
    setDirectives(d.items ?? []);
    setBusinessOutcomes(bo.items ?? []);
    setMode(s.current_mode ?? "balanced");
  }

  useEffect(() => {
    refresh().catch((err) => setError(String(err)));
  }, []);

  async function onActivateMode() {
    await activateStrategyMode({ mode, ttl_minutes: 240 });
    await refresh();
  }

  async function onSeedLaunchSignal() {
    await createStrategySignal({
      signal_type: "launch_calendar",
      title: "Spring launch wave",
      description: "Protect launch throughput for enterprise and premium customers.",
      priority: 92,
      weight: 88,
      customer_tier: "premium",
      is_active: true,
    });
    await refresh();
  }

  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-100 p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-3xl font-semibold">Strategy Console</h1>
            <p className="text-neutral-400">Enterprise strategy → objective translation → directives for fabric and autonomy.</p>
          </div>
          <div className="flex gap-3 flex-wrap">
            <Link href="/dashboard" className="rounded-2xl border border-neutral-700 px-4 py-3">Production Dashboard</Link>
            <Link href="/audio" className="rounded-2xl border border-neutral-700 px-4 py-3">Audio Studio</Link>
          </div>
        </div>

        <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-5 flex gap-3 flex-wrap items-center">
          <select value={mode} onChange={(e) => setMode(e.target.value)} className="rounded-2xl bg-neutral-950 border border-neutral-800 p-3">
            <option value="balanced">balanced</option>
            <option value="launch_mode">launch_mode</option>
            <option value="margin_mode">margin_mode</option>
            <option value="sla_protection_mode">sla_protection_mode</option>
            <option value="quality_first_mode">quality_first_mode</option>
          </select>
          <button onClick={onActivateMode} className="rounded-2xl bg-white text-black px-4 py-3 font-medium">Activate mode</button>
          <button onClick={onSeedLaunchSignal} className="rounded-2xl border border-neutral-700 px-4 py-3">Seed launch signal</button>
        </div>

        {error ? <div className="rounded-2xl border border-red-800 bg-red-950/30 p-4">{error}</div> : null}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <StrategyStateCard title="Current mode" value={state?.current_mode ?? "-"} hint="Top-level mission shaping runtime directives." />
          <StrategyStateCard title="Signals" value={String(state?.signals?.length ?? 0)} hint="Revenue, SLA, launch, campaign, and roadmap inputs." />
          <StrategyStateCard title="Objective stack" value={(state?.objective_profile?.objective_stack ?? []).slice(0, 3).join(" → ") || "-"} hint="Highest priorities drive the directive bridge." />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <PortfolioAllocationTable portfolio={portfolio} />
          <DirectivePanel directives={directives} />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <SlaRiskHeatmap data={slaRisk} />
          <CampaignTimeline signals={state?.signals ?? []} />
        </div>

        <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-5">
          <h2 className="text-xl font-semibold mb-4">Business outcomes</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {businessOutcomes.map((item) => (
              <div key={item.mode + item.captured_at} className="rounded-2xl border border-neutral-800 p-4">
                <div className="font-medium">{item.mode}</div>
                <div className="text-sm text-neutral-400 mt-2">revenue index: {item.revenue_index}</div>
                <div className="text-sm text-neutral-400">sla: {item.sla_attainment_bps}</div>
                <div className="text-sm text-neutral-400">throughput: {item.throughput_index}</div>
                <div className="text-sm text-neutral-400">margin: {item.margin_index}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
