"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type NavItem = {
  label: string;
  href: string;
  description: string;
};

const navItems: NavItem[] = [
  {
    label: "Dashboard",
    href: "/",
    description: "Overview, project creation, and workspace entry points",
  },
  {
    label: "Script Upload",
    href: "/script-upload",
    description: "Upload .txt / .docx, preview, edit, validate, and create project",
  },
  {
    label: "Render Jobs",
    href: "/render-jobs",
    description: "Track render pipelines, scene task progress, and final preview output",
  },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-full w-full flex-col rounded-3xl border border-white/10 bg-black/20 p-4 text-white">
      <div className="mb-6">
        <p className="text-xs uppercase tracking-[0.25em] text-white/40">
          Render Factory
        </p>
        <h2 className="mt-2 text-xl font-semibold tracking-tight">
          Production Console
        </h2>
        <p className="mt-2 text-sm text-white/55">
          Script preview, provider planning, render execution, and final output tracking.
        </p>
      </div>

      <nav className="flex-1 space-y-2">
        {navItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname === item.href || pathname.startsWith(`${item.href}/`);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={[
                "block rounded-2xl border px-4 py-3 transition",
                isActive
                  ? "border-white/20 bg-white text-black"
                  : "border-white/10 bg-white/5 text-white hover:border-white/20 hover:bg-white/10",
              ].join(" ")}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">{item.label}</p>
                  <p
                    className={[
                      "mt-1 text-xs",
                      isActive ? "text-black/70" : "text-white/55",
                    ].join(" ")}
                  >
                    {item.description}
                  </p>
                </div>

                <span
                  className={[
                    "mt-0.5 inline-flex rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wide",
                    isActive
                      ? "bg-black/10 text-black/70"
                      : "bg-white/10 text-white/50",
                  ].join(" ")}
                >
                  {isActive ? "Active" : "Open"}
                </span>
              </div>
            </Link>
          );
        })}
      </nav>

      <div className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-4">
        <p className="text-xs uppercase tracking-wide text-white/40">
          Workflow
        </p>
        <div className="mt-3 space-y-2 text-sm text-white/65">
          <p>1. Upload script</p>
          <p>2. Preview and edit</p>
          <p>3. Validate</p>
          <p>4. Prepare render plan</p>
          <p>5. Track render jobs</p>
        </div>
      </div>
    </aside>
  );
}
