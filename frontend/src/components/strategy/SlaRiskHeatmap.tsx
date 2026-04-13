export default function SlaRiskHeatmap({ data }: { data: any }) {
  return (
    <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-5">
      <h2 className="text-xl font-semibold mb-4">SLA risk heatmap</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Object.entries(data?.tiers ?? {}).map(([tier, item]: any) => (
          <div key={tier} className="rounded-2xl border border-neutral-800 p-4">
            <div className="font-medium capitalize">{tier}</div>
            <div className="text-sm text-neutral-400 mt-1">risk score: {item.risk_score}</div>
            <div className="text-sm text-neutral-400">status: {item.status}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
