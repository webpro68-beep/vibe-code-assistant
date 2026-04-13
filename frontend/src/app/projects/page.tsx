import Link from "next/link";
import { getProjects } from "@/src/lib/api";

export default async function ProjectsPage() {
  const data = await getProjects();
  const items = data.items || [];
  return (
    <main style={{ padding: 24 }}>
      <h1>Projects</h1>
      <div style={{ display: "grid", gap: 12 }}>
        {items.map((project: any) => (
          <Link key={project.id} href={`/projects/${project.id}`} style={{ padding: 12, border: "1px solid #ddd", borderRadius: 8 }}>
            <div><strong>{project.name}</strong></div>
            <div>Status: {project.status}</div>
            <div>Platform: {project.target_platform}</div>
            <div>Format: {project.format}</div>
          </Link>
        ))}
      </div>
    </main>
  );
}
