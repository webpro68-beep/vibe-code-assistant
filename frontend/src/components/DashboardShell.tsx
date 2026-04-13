"use client";
import Sidebar from "@/src/components/Sidebar";
export default function DashboardShell({ title, eyebrow, description, children, aside, }: { title: string; eyebrow?: string; description?: string; children: React.ReactNode; aside?: React.ReactNode; }) {
  return <main className="min-h-screen bg-neutral-950 text-white"><div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[280px_minmax(0,1fr)_360px]"><div className="lg:sticky lg:top-6 lg:h-[calc(100vh-3rem)]"><Sidebar /></div><div className="space-y-6"><header className="rounded-3xl border border-white/10 bg-white/5 p-6">{eyebrow ? <p className="text-xs uppercase tracking-[0.25em] text-white/40">{eyebrow}</p> : null}<h1 className="mt-2 text-3xl font-semibold tracking-tight">{title}</h1>{description ? <p className="mt-3 max-w-3xl text-sm text-white/60">{description}</p> : null}</header>{children}</div><div className="space-y-6">{aside}</div></div></main>;
}
