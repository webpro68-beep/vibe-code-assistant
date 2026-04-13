export default function PortfolioAllocationTable({ portfolio }: { portfolio: any }) {
  return (
    <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-5">
      <h2 className="text-xl font-semibold mb-4">Portfolio allocation</h2>
      <div className="text-sm text-neutral-400 mb-4">Reserve capacity: {portfolio?.reserve_capacity_percent ?? 0}%</div>
      <div className="space-y-3">
        {Object.entries(portfolio?.tiers ?? {}).map(([tier, cfg]: any) => (
          <div key={tier} className="grid grid-cols-3 rounded-2xl border border-neutral-800 p-4 text-sm">
            <div className="font-medium capitalize">{tier}</div>
            <div>weight: {cfg.weight}</div>
            <div>lane: {cfg.lane}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
