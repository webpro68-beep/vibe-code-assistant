import { getTemplatesRanked } from "@/src/lib/api";

export default async function TemplatesPage() {
  const ranked = await getTemplatesRanked(20);
  const items = ranked.items || [];
  return (
    <main style={{ padding: 24 }}>
      <h1>Template Library</h1>
      <div style={{ display: "grid", gap: 12 }}>
        {items.map((item: any) => (
          <div key={item.template_id} style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12 }}>
            <div><strong>{item.template_name}</strong></div>
            <div>Final priority: {item.final_priority_score}</div>
            <div>Render: {item.render_score} | Upload: {item.upload_score} | Retention: {item.retention_score}</div>
            <div>Memory: {item.memory_state}</div>
          </div>
        ))}
      </div>
    </main>
  );
}
