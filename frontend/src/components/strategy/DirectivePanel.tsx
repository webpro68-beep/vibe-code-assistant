export default function DirectivePanel({ directives }: { directives: any[] }) {
  return (
    <div className="rounded-3xl border border-neutral-800 bg-neutral-900 p-5">
      <h2 className="text-xl font-semibold mb-4">Active directives</h2>
      <div className="space-y-3">
        {directives.map((directive) => (
          <div key={`${directive.directive_type}-${directive.scope}`} className="rounded-2xl border border-neutral-800 p-4">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div className="font-medium">{directive.directive_type}</div>
              <div className="text-xs rounded-full border border-neutral-700 px-3 py-1">p{directive.priority}</div>
            </div>
            <div className="text-sm text-neutral-400 mt-2">{directive.rationale}</div>
            <pre className="text-xs text-neutral-300 mt-3 overflow-auto">{JSON.stringify(directive.payload, null, 2)}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}
