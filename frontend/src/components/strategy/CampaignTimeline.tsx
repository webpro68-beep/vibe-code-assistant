export default function CampaignTimeline({ signals }: { signals: any[] }) {
  const interesting = signals.filter((s) => ["campaign", "launch_calendar", "roadmap_priority"].includes(s.signal_type));
  return (
    <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-5">
      <h2 className="text-xl font-semibold mb-4">Campaign and launch timeline</h2>
      <div className="space-y-3">
        {interesting.length === 0 ? <div className="text-sm text-neutral-400">No campaign or launch windows active.</div> : null}
        {interesting.map((signal) => (
          <div key={signal.id} className="rounded-2xl border border-neutral-800 p-4">
            <div className="font-medium">{signal.title}</div>
            <div className="text-sm text-neutral-400 mt-1">{signal.signal_type}</div>
            <div className="text-xs text-neutral-500 mt-2">priority {signal.priority} • weight {signal.weight}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
