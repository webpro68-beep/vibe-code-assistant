export default function StrategyStateCard({ title, value, hint }: { title: string; value: string; hint?: string }) {
  return (
    <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-5">
      <div className="text-sm text-neutral-500">{title}</div>
      <div className="text-xl font-semibold mt-2">{value}</div>
      {hint ? <div className="text-sm text-neutral-400 mt-2">{hint}</div> : null}
    </div>
  );
}
