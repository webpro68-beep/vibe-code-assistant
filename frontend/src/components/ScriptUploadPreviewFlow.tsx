"use client";

import { useState } from "react";
import {
  createProjectFromPreview,
  ScriptPreviewPayload,
  uploadScriptFileForPreview,
  ValidationIssue,
  validatePreviewPayload,
} from "@/src/lib/api";

import PreviewEditingLayer from "@/src/components/PreviewEditingLayer";

type UploadState = "idle" | "uploading" | "ready" | "error";

export default function ScriptUploadPreviewFlow() {
  const [file, setFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [preview, setPreview] = useState<ScriptPreviewPayload | null>(null);

  const [error, setError] = useState<string | null>(null);

  const [creatingProject, setCreatingProject] = useState(false);

  const [validationState, setValidationState] = useState<{
    valid: boolean;
    issues: ValidationIssue[];
  }>({
    valid: true,
    issues: [],
  });

  const [aspectRatio, setAspectRatio] = useState<"16:9" | "9:16" | "1:1">("9:16");
  const [targetPlatform, setTargetPlatform] = useState<"shorts" | "youtube" | "tiktok">("shorts");
  const [stylePreset, setStylePreset] = useState<string>("default");

  // -----------------------------
  // Upload handler
  // -----------------------------
  const handleUpload = async () => {
    if (!file) {
      alert("Please select a .txt or .docx file");
      return;
    }

    setUploadState("uploading");
    setError(null);

    try {
      const result = await uploadScriptFileForPreview({
        file,
        aspect_ratio: aspectRatio,
        target_platform: targetPlatform,
        style_preset: stylePreset,
      });

      setPreview(result);
      setUploadState("ready");
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : "Upload failed");
      setUploadState("error");
    }
  };

  // -----------------------------
  // Confirm create project
  // -----------------------------
  const handleCreateProject = async () => {
    if (!preview) return;

    try {
      setCreatingProject(true);

      // validate lần cuối (hard check)
      const result = await validatePreviewPayload(preview);
      setValidationState(result);

      if (!result.valid) {
        alert("Preview has validation errors. Please fix them first.");
        return;
      }

      const created = await createProjectFromPreview({
        name: buildProjectName(preview),
        preview_payload: preview,
        confirmed: true,
      });

      alert("Project created successfully!");

      console.log("Created project:", created);

      // reset nếu muốn
      // setPreview(null);

    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setCreatingProject(false);
    }
  };

  // -----------------------------
  // UI
  // -----------------------------
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-white">
          Script Upload → Preview → Create Project
        </h1>
        <p className="text-sm text-white/60">
          Upload your script file, edit scenes & subtitles, validate, and create project.
        </p>
      </header>

      {/* Upload Panel */}
      <section className="rounded-3xl border border-white/10 bg-black/20 p-5 space-y-4">
        <div className="grid gap-4 md:grid-cols-3">
          <Field label="Aspect Ratio">
            <select
              value={aspectRatio}
              onChange={(e) => setAspectRatio(e.target.value as any)}
              className={inputClass}
            >
              <option value="9:16">9:16 (Vertical)</option>
              <option value="16:9">16:9 (Horizontal)</option>
              <option value="1:1">1:1 (Square)</option>
            </select>
          </Field>

          <Field label="Platform">
            <select
              value={targetPlatform}
              onChange={(e) => setTargetPlatform(e.target.value as any)}
              className={inputClass}
            >
              <option value="shorts">YouTube Shorts</option>
              <option value="tiktok">TikTok</option>
              <option value="youtube">YouTube Long</option>
            </select>
          </Field>

          <Field label="Style Preset">
            <input
              value={stylePreset}
              onChange={(e) => setStylePreset(e.target.value)}
              className={inputClass}
              placeholder="cinematic_dark / minimal / default"
            />
          </Field>
        </div>

        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <input
            type="file"
            accept=".txt,.docx"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm text-white"
          />

          <button
            onClick={() => void handleUpload()}
            disabled={uploadState === "uploading"}
            className="rounded-2xl bg-white px-4 py-2.5 text-sm font-semibold text-black disabled:opacity-50"
          >
            {uploadState === "uploading" ? "Uploading..." : "Upload & Generate Preview"}
          </button>
        </div>

        {error && (
          <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">
            {error}
          </div>
        )}
      </section>

      {/* Preview Editing Layer */}
      {preview && (
        <PreviewEditingLayer
          preview={preview}
          onChange={setPreview}
          onValidationChange={setValidationState}
        />
      )}

      {/* Footer Actions */}
      {preview && (
        <section className="rounded-3xl border border-white/10 bg-black/20 p-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="text-sm text-white/60">
            {validationState.valid
              ? "Preview is valid. Ready to create project."
              : "Fix validation issues before creating project."}
          </div>

          <button
            onClick={() => void handleCreateProject()}
            disabled={!validationState.valid || creatingProject}
            className="rounded-2xl border border-white/15 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50"
          >
            {creatingProject ? "Creating..." : "Confirm & Create Project"}
          </button>
        </section>
      )}
    </div>
  );
}

// -----------------------------
// Helpers
// -----------------------------

function buildProjectName(preview: ScriptPreviewPayload): string {
  const firstLine =
    preview.script_text?.split("\n").find((line) => line.trim().length > 0) ??
    "New Project";

  return firstLine.slice(0, 60);
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-white/70">
        {label}
      </span>
      {children}
    </label>
  );
}

const inputClass =
  "w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none";