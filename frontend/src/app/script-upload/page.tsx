"use client";

import ScriptUploadPreviewFlow from "@/src/components/ScriptUploadPreviewFlow";

export default function ScriptUploadPage() {
  return (
    <main className="min-h-screen bg-neutral-950 text-white">
      <div className="mx-auto max-w-6xl px-6 py-8">
        <header className="mb-8">
          <p className="text-sm uppercase tracking-[0.25em] text-white/40">
            Script Upload
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">
            Upload Script → Preview → Edit → Validate → Create Project
          </h1>
          <p className="mt-2 max-w-3xl text-sm text-white/55">
            Upload a <code className="rounded bg-white/10 px-1 py-0.5">.txt</code> or{" "}
            <code className="rounded bg-white/10 px-1 py-0.5">.docx</code> script,
            preview parsed scenes and subtitles, edit them in place, validate the
            structure, then confirm to create a project ready for render planning.
          </p>
        </header>

        <section className="mb-6 rounded-3xl border border-white/10 bg-white/5 p-5">
          <div className="grid gap-4 md:grid-cols-3">
            <InfoCard
              label="Flow"
              value="Preview-first"
              hint="No project is created until the user confirms a valid preview."
            />
            <InfoCard
              label="Validation"
              value="Inline + panel"
              hint="Errors are highlighted at row level and field level before confirm."
            />
            <InfoCard
              label="Next step"
              value="Render planning"
              hint="Use the created project to prepare provider-specific render plans."
            />
          </div>
        </section>

        <ScriptUploadPreviewFlow />
      </div>
    </main>
  );
}

function InfoCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
      <p className="text-xs uppercase tracking-wide text-white/45">{label}</p>
      <p className="mt-2 text-sm font-semibold text-white">{value}</p>
      <p className="mt-2 text-sm text-white/55">{hint}</p>
    </div>
  );
}
