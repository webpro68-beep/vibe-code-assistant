"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  rebuildSubtitlesFromPreview,
  recalculateAllFromPreview,
  recalculateDurationsFromPreview,
  ScriptPreviewPayload,
  ValidationIssue,
  validatePreviewPayload,
} from "@/src/lib/api";

type LoadingAction = null | "subtitles" | "durations" | "all" | "validate";

type PreviewEditingLayerProps = {
  preview: ScriptPreviewPayload;
  onChange: (next: ScriptPreviewPayload) => void;
  onValidationChange?: (result: { valid: boolean; issues: ValidationIssue[] }) => void;
};

export default function PreviewEditingLayer({
  preview,
  onChange,
  onValidationChange,
}: PreviewEditingLayerProps) {
  const [loadingAction, setLoadingAction] = useState<LoadingAction>(null);
  const [validationIssues, setValidationIssues] = useState<ValidationIssue[]>([]);
  const [isValid, setIsValid] = useState(true);

  const fieldRefs = useRef<Record<string, HTMLElement | null>>({});

  const previewIssues = useMemo(
    () => validationIssues.filter((issue) => issue.target_type === "preview"),
    [validationIssues],
  );

  useEffect(() => {
    if (!validationIssues.length) return;

    const firstIssue = validationIssues[0];
    const key = issueToFieldKey(firstIssue);
    const node = fieldRefs.current[key];

    if (!node) return;

    node.scrollIntoView({
      behavior: "smooth",
      block: "center",
      inline: "nearest",
    });

    if ("focus" in node && typeof node.focus === "function") {
      window.setTimeout(() => {
        node.focus();
      }, 150);
    }
  }, [validationIssues]);

  const registerField = (key: string) => (node: HTMLElement | null) => {
    fieldRefs.current[key] = node;
  };

  const runValidation = async () => {
    setLoadingAction("validate");
    try {
      const result = await validatePreviewPayload(preview);
      setValidationIssues(result.issues);
      setIsValid(result.valid);
      onValidationChange?.(result);
    } catch (error) {
      console.error(error);
      alert(error instanceof Error ? error.message : "Failed to validate preview");
    } finally {
      setLoadingAction(null);
    }
  };

  const handleRebuildSubtitles = async () => {
    setLoadingAction("subtitles");
    try {
      const next = await rebuildSubtitlesFromPreview(preview);
      onChange(next);
    } catch (error) {
      console.error(error);
      alert(error instanceof Error ? error.message : "Failed to rebuild subtitles");
    } finally {
      setLoadingAction(null);
    }
  };

  const handleRecalculateDurations = async () => {
    setLoadingAction("durations");
    try {
      const next = await recalculateDurationsFromPreview(preview);
      onChange(next);
    } catch (error) {
      console.error(error);
      alert(error instanceof Error ? error.message : "Failed to recalculate durations");
    } finally {
      setLoadingAction(null);
    }
  };

  const handleRecalculateAll = async () => {
    setLoadingAction("all");
    try {
      const next = await recalculateAllFromPreview(preview);
      onChange(next);
    } catch (error) {
      console.error(error);
      alert(error instanceof Error ? error.message : "Failed to recalculate preview");
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="space-y-6">
      <ValidationPanel issues={validationIssues} valid={isValid} />

      <section className="rounded-3xl border border-white/10 bg-black/20 p-5">
        <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">Regenerate + Validate Tools</h3>
            <p className="mt-1 text-sm text-white/55">
              Rebuild subtitles, recalculate durations, and validate preview before confirm.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => void handleRebuildSubtitles()}
              disabled={loadingAction !== null}
              className="rounded-2xl border border-white/15 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              {loadingAction === "subtitles" ? "Rebuilding..." : "Rebuild subtitles"}
            </button>

            <button
              onClick={() => void handleRecalculateDurations()}
              disabled={loadingAction !== null}
              className="rounded-2xl border border-white/15 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              {loadingAction === "durations" ? "Recalculating..." : "Recalculate durations"}
            </button>

            <button
              onClick={() => void handleRecalculateAll()}
              disabled={loadingAction !== null}
              className="rounded-2xl border border-white/15 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              {loadingAction === "all" ? "Updating..." : "Recalculate all"}
            </button>

            <button
              onClick={() => void runValidation()}
              disabled={loadingAction !== null}
              className="rounded-2xl bg-white px-4 py-2.5 text-sm font-semibold text-black disabled:opacity-50"
            >
              {loadingAction === "validate" ? "Validating..." : "Validate preview"}
            </button>
          </div>
        </div>

        {previewIssues.length ? (
          <InlineFieldError messages={previewIssues.map((x) => x.message)} />
        ) : null}
      </section>

      <section className="rounded-3xl border border-white/10 bg-black/20 p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-white">Scene Editor</h3>
            <p className="mt-1 text-sm text-white/55">
              Edit, add, remove, and reorder scenes before confirming project creation.
            </p>
          </div>

          <button
            onClick={() => onChange(addScene(preview))}
            className="rounded-2xl border border-white/15 px-4 py-2 text-sm font-semibold text-white"
          >
            Add scene
          </button>
        </div>

        <div className="space-y-4">
          {preview.scenes.map((scene, sceneRowIndex) => {
            const rowIssues = getIssues(validationIssues, "scene", sceneRowIndex);

            return (
              <div
                key={`scene-${scene.scene_index}-${sceneRowIndex}`}
                className={`rounded-2xl border p-4 ${
                  rowIssues.length
                    ? "border-rose-500/40 bg-rose-500/10"
                    : "border-white/10 bg-white/5"
                }`}
              >
                <div className="mb-4 flex flex-wrap gap-2">
                  <button
                    onClick={() => onChange(moveScene(preview, sceneRowIndex, -1))}
                    className="rounded-xl border border-white/10 px-3 py-2 text-xs text-white"
                  >
                    Move up
                  </button>
                  <button
                    onClick={() => onChange(moveScene(preview, sceneRowIndex, 1))}
                    className="rounded-xl border border-white/10 px-3 py-2 text-xs text-white"
                  >
                    Move down
                  </button>
                  <button
                    onClick={() => onChange(deleteScene(preview, sceneRowIndex))}
                    className="rounded-xl border border-rose-500/30 px-3 py-2 text-xs text-rose-200"
                  >
                    Delete scene
                  </button>
                </div>

                <div className="grid gap-4 md:grid-cols-[120px_1fr_140px]">
                  <Field label="Scene">
                    <input
                      ref={registerField(buildFieldKey("scene", sceneRowIndex, "scene_index"))}
                      value={scene.scene_index}
                      readOnly
                      className={inputClassMuted}
                    />
                    <InlineFieldError
                      messages={getFieldIssues(
                        validationIssues,
                        "scene",
                        sceneRowIndex,
                        "scene_index",
                      ).map((x) => x.message)}
                    />
                  </Field>

                  <Field label="Title">
                    <input
                      ref={registerField(buildFieldKey("scene", sceneRowIndex, "title"))}
                      value={scene.title}
                      onChange={(e) =>
                        onChange(updateSceneField(preview, scene.scene_index, "title", e.target.value))
                      }
                      className={getFieldClassName(
                        validationIssues,
                        "scene",
                        sceneRowIndex,
                        "title",
                        inputClass,
                      )}
                    />
                    <InlineFieldError
                      messages={getFieldIssues(
                        validationIssues,
                        "scene",
                        sceneRowIndex,
                        "title",
                      ).map((x) => x.message)}
                    />
                  </Field>

                  <Field label="Duration (sec)">
                    <input
                      ref={registerField(
                        buildFieldKey("scene", sceneRowIndex, "target_duration_sec"),
                      )}
                      type="number"
                      min={0.1}
                      step={0.1}
                      value={scene.target_duration_sec}
                      onChange={(e) =>
                        onChange(
                          updateSceneField(
                            preview,
                            scene.scene_index,
                            "target_duration_sec",
                            Number(e.target.value),
                          ),
                        )
                      }
                      className={getFieldClassName(
                        validationIssues,
                        "scene",
                        sceneRowIndex,
                        "target_duration_sec",
                        inputClass,
                      )}
                    />
                    <InlineFieldError
                      messages={getFieldIssues(
                        validationIssues,
                        "scene",
                        sceneRowIndex,
                        "target_duration_sec",
                      ).map((x) => x.message)}
                    />
                  </Field>
                </div>

                <div className="mt-4">
                  <Field label="Scene script">
                    <textarea
                      ref={registerField(buildFieldKey("scene", sceneRowIndex, "script_text"))}
                      rows={5}
                      value={scene.script_text}
                      onChange={(e) => {
                        const next = updateSceneField(
                          preview,
                          scene.scene_index,
                          "script_text",
                          e.target.value,
                        );
                        onChange(rebuildScriptTextFromScenes(next));
                      }}
                      className={getFieldClassName(
                        validationIssues,
                        "scene",
                        sceneRowIndex,
                        "script_text",
                        textareaClass,
                      )}
                    />
                    <InlineFieldError
                      messages={getFieldIssues(
                        validationIssues,
                        "scene",
                        sceneRowIndex,
                        "script_text",
                      ).map((x) => x.message)}
                    />
                  </Field>
                </div>

                <InlineFieldError messages={rowIssues.map((x) => x.message)} />
              </div>
            );
          })}
        </div>
      </section>

      <section className="rounded-3xl border border-white/10 bg-black/20 p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-white">Subtitle Editor</h3>
            <p className="mt-1 text-sm text-white/55">
              Edit, add, remove, and reorder subtitle segments before confirming.
            </p>
          </div>

          <button
            onClick={() => onChange(addSubtitle(preview))}
            className="rounded-2xl border border-white/15 px-4 py-2 text-sm font-semibold text-white"
          >
            Add subtitle
          </button>
        </div>

        <div className="space-y-3">
          {preview.subtitle_segments.map((seg, subtitleRowIndex) => {
            const rowIssues = getIssues(validationIssues, "subtitle", subtitleRowIndex);

            return (
              <div
                key={`subtitle-${subtitleRowIndex}-${seg.start_sec}-${seg.end_sec}`}
                className={`rounded-2xl border p-4 ${
                  rowIssues.length
                    ? "border-rose-500/40 bg-rose-500/10"
                    : "border-white/10 bg-white/5"
                }`}
              >
                <div className="mb-4 flex flex-wrap gap-2">
                  <button
                    onClick={() => onChange(moveSubtitle(preview, subtitleRowIndex, -1))}
                    className="rounded-xl border border-white/10 px-3 py-2 text-xs text-white"
                  >
                    Move up
                  </button>
                  <button
                    onClick={() => onChange(moveSubtitle(preview, subtitleRowIndex, 1))}
                    className="rounded-xl border border-white/10 px-3 py-2 text-xs text-white"
                  >
                    Move down
                  </button>
                  <button
                    onClick={() => onChange(deleteSubtitle(preview, subtitleRowIndex))}
                    className="rounded-xl border border-rose-500/30 px-3 py-2 text-xs text-rose-200"
                  >
                    Delete subtitle
                  </button>
                </div>

                <div className="grid gap-4 md:grid-cols-[110px_110px_110px_1fr]">
                  <Field label="Scene">
                    <input
                      ref={registerField(buildFieldKey("subtitle", subtitleRowIndex, "scene_index"))}
                      type="number"
                      min={1}
                      value={seg.scene_index ?? ""}
                      onChange={(e) =>
                        onChange(
                          updateSubtitleField(
                            preview,
                            subtitleRowIndex,
                            "scene_index",
                            e.target.value ? Number(e.target.value) : null,
                          ),
                        )
                      }
                      className={getFieldClassName(
                        validationIssues,
                        "subtitle",
                        subtitleRowIndex,
                        "scene_index",
                        inputClass,
                      )}
                    />
                    <InlineFieldError
                      messages={getFieldIssues(
                        validationIssues,
                        "subtitle",
                        subtitleRowIndex,
                        "scene_index",
                      ).map((x) => x.message)}
                    />
                  </Field>

                  <Field label="Start">
                    <input
                      ref={registerField(buildFieldKey("subtitle", subtitleRowIndex, "start_sec"))}
                      type="number"
                      min={0}
                      step={0.01}
                      value={seg.start_sec}
                      onChange={(e) =>
                        onChange(
                          updateSubtitleField(
                            preview,
                            subtitleRowIndex,
                            "start_sec",
                            Number(e.target.value),
                          ),
                        )
                      }
                      className={getFieldClassName(
                        validationIssues,
                        "subtitle",
                        subtitleRowIndex,
                        "start_sec",
                        inputClass,
                      )}
                    />
                    <InlineFieldError
                      messages={getFieldIssues(
                        validationIssues,
                        "subtitle",
                        subtitleRowIndex,
                        "start_sec",
                      ).map((x) => x.message)}
                    />
                  </Field>

                  <Field label="End">
                    <input
                      ref={registerField(buildFieldKey("subtitle", subtitleRowIndex, "end_sec"))}
                      type="number"
                      min={0}
                      step={0.01}
                      value={seg.end_sec}
                      onChange={(e) =>
                        onChange(
                          updateSubtitleField(
                            preview,
                            subtitleRowIndex,
                            "end_sec",
                            Number(e.target.value),
                          ),
                        )
                      }
                      className={getFieldClassName(
                        validationIssues,
                        "subtitle",
                        subtitleRowIndex,
                        "end_sec",
                        inputClass,
                      )}
                    />
                    <InlineFieldError
                      messages={getFieldIssues(
                        validationIssues,
                        "subtitle",
                        subtitleRowIndex,
                        "end_sec",
                      ).map((x) => x.message)}
                    />
                  </Field>

                  <Field label="Text">
                    <input
                      ref={registerField(buildFieldKey("subtitle", subtitleRowIndex, "text"))}
                      value={seg.text}
                      onChange={(e) =>
                        onChange(
                          updateSubtitleField(preview, subtitleRowIndex, "text", e.target.value),
                        )
                      }
                      className={getFieldClassName(
                        validationIssues,
                        "subtitle",
                        subtitleRowIndex,
                        "text",
                        inputClass,
                      )}
                    />
                    <InlineFieldError
                      messages={getFieldIssues(
                        validationIssues,
                        "subtitle",
                        subtitleRowIndex,
                        "text",
                      ).map((x) => x.message)}
                    />
                  </Field>
                </div>

                <InlineFieldError messages={rowIssues.map((x) => x.message)} />
              </div>
            );
          })}
        </div>
      </section>

      <section className="rounded-3xl border border-white/10 bg-black/20 p-5">
        <div className="mb-3">
          <h3 className="text-lg font-semibold text-white">Rebuilt Script</h3>
          <p className="mt-1 text-sm text-white/55">
            This is rebuilt automatically from edited scenes and will be saved into the project.
          </p>
        </div>

        <textarea
          ref={registerField(buildFieldKey("preview", null, "script_text"))}
          value={preview.script_text}
          readOnly
          rows={10}
          className={getFieldClassName(
            validationIssues,
            "preview",
            null,
            "script_text",
            textareaClass,
          )}
        />
        <InlineFieldError
          messages={getFieldIssues(validationIssues, "preview", null, "script_text").map(
            (x) => x.message,
          )}
        />
      </section>
    </div>
  );
}

function ValidationPanel({
  issues,
  valid,
}: {
  issues: ValidationIssue[];
  valid: boolean;
}) {
  if (valid && issues.length === 0) {
    return (
      <div className="rounded-3xl border border-emerald-500/20 bg-emerald-500/10 p-5">
        <h3 className="text-lg font-semibold text-emerald-200">Preview is valid</h3>
        <p className="mt-1 text-sm text-emerald-100/80">
          No blocking issues found. You can confirm and create the project.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-3xl border border-rose-500/20 bg-rose-500/10 p-5">
      <h3 className="text-lg font-semibold text-rose-200">Validation issues found</h3>
      <p className="mt-1 text-sm text-rose-100/80">
        Fix the issues below before creating the project.
      </p>

      <div className="mt-4 space-y-2">
        {issues.map((issue, index) => (
          <div
            key={`${issue.code}-${issue.target_type}-${issue.target_index}-${index}`}
            className="rounded-2xl border border-rose-500/20 bg-black/20 p-3"
          >
            <p className="text-sm font-medium text-rose-100">{issue.message}</p>
            <p className="mt-1 text-xs text-rose-200/70">
              {issue.target_type}
              {issue.target_index != null ? ` #${issue.target_index + 1}` : ""}
              {issue.field ? ` • ${issue.field}` : ""}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function InlineFieldError({ messages }: { messages: string[] }) {
  if (!messages.length) return null;

  return (
    <div className="mt-2 space-y-1">
      {messages.map((message, index) => (
        <p key={`${message}-${index}`} className="text-xs text-rose-300">
          {message}
        </p>
      ))}
    </div>
  );
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
      <span className="mb-2 block text-sm font-medium text-white/70">{label}</span>
      {children}
    </label>
  );
}

function buildFieldKey(
  targetType: "scene" | "subtitle" | "preview",
  targetIndex: number | null | undefined,
  field: string | null | undefined,
): string {
  return `${targetType}:${targetIndex ?? "root"}:${field ?? "root"}`;
}

function issueToFieldKey(issue: ValidationIssue): string {
  return buildFieldKey(issue.target_type, issue.target_index, issue.field);
}

function getIssues(
  issues: ValidationIssue[],
  targetType: "scene" | "subtitle" | "preview",
  targetIndex: number | null | undefined,
): ValidationIssue[] {
  return issues.filter(
    (issue) =>
      issue.target_type === targetType &&
      (issue.target_index ?? null) === (targetIndex ?? null),
  );
}

function getFieldIssues(
  issues: ValidationIssue[],
  targetType: "scene" | "subtitle" | "preview",
  targetIndex: number | null | undefined,
  field: string,
): ValidationIssue[] {
  return issues.filter(
    (issue) =>
      issue.target_type === targetType &&
      (issue.target_index ?? null) === (targetIndex ?? null) &&
      issue.field === field,
  );
}

function getFieldClassName(
  issues: ValidationIssue[],
  targetType: "scene" | "subtitle" | "preview",
  targetIndex: number | null | undefined,
  field: string,
  baseClass: string,
): string {
  const hasIssue = getFieldIssues(issues, targetType, targetIndex, field).length > 0;
  return hasIssue ? `${baseClass} border-rose-500/70 ring-2 ring-rose-500/30` : baseClass;
}

function updateSceneField(
  preview: ScriptPreviewPayload,
  sceneIndex: number,
  field: "title" | "script_text" | "target_duration_sec",
  value: string | number,
): ScriptPreviewPayload {
  return {
    ...preview,
    scenes: preview.scenes.map((scene) =>
      scene.scene_index === sceneIndex ? { ...scene, [field]: value } : scene,
    ),
  };
}

function updateSubtitleField(
  preview: ScriptPreviewPayload,
  subtitleIndex: number,
  field: "text" | "start_sec" | "end_sec" | "scene_index",
  value: string | number | null,
): ScriptPreviewPayload {
  return {
    ...preview,
    subtitle_segments: preview.subtitle_segments.map((seg, index) =>
      index === subtitleIndex ? { ...seg, [field]: value } : seg,
    ),
  };
}

function rebuildScriptTextFromScenes(preview: ScriptPreviewPayload): ScriptPreviewPayload {
  const scriptText = preview.scenes
    .map((scene) => scene.script_text.trim())
    .filter(Boolean)
    .join("\n\n");

  return {
    ...preview,
    script_text: scriptText,
  };
}

function renumberScenes(preview: ScriptPreviewPayload): ScriptPreviewPayload {
  const oldScenes = preview.scenes;

  const scenes = oldScenes.map((scene, index) => ({
    ...scene,
    scene_index: index + 1,
  }));

  const oldToNew = new Map<number, number>();
  oldScenes.forEach((scene, index) => {
    oldToNew.set(scene.scene_index, index + 1);
  });

  const subtitle_segments = preview.subtitle_segments.map((seg) => ({
    ...seg,
    scene_index:
      seg.scene_index == null ? null : (oldToNew.get(seg.scene_index) ?? null),
  }));

  return {
    ...preview,
    scenes,
    subtitle_segments,
  };
}

function addScene(preview: ScriptPreviewPayload): ScriptPreviewPayload {
  const next = {
    ...preview,
    scenes: [
      ...preview.scenes,
      {
        scene_index: preview.scenes.length + 1,
        title: `Scene ${preview.scenes.length + 1}`,
        script_text: "",
        target_duration_sec: 5,
      },
    ],
  };

  return rebuildScriptTextFromScenes(renumberScenes(next));
}

function deleteScene(preview: ScriptPreviewPayload, rowIndex: number): ScriptPreviewPayload {
  const removedScene = preview.scenes[rowIndex];
  const remainingScenes = preview.scenes.filter((_, index) => index !== rowIndex);

  const next = {
    ...preview,
    scenes: remainingScenes,
    subtitle_segments: preview.subtitle_segments.map((seg) => ({
      ...seg,
      scene_index: seg.scene_index === removedScene?.scene_index ? null : seg.scene_index,
    })),
  };

  return rebuildScriptTextFromScenes(renumberScenes(next));
}

function moveScene(
  preview: ScriptPreviewPayload,
  rowIndex: number,
  direction: -1 | 1,
): ScriptPreviewPayload {
  const targetIndex = rowIndex + direction;
  if (targetIndex < 0 || targetIndex >= preview.scenes.length) return preview;

  const scenes = [...preview.scenes];
  [scenes[rowIndex], scenes[targetIndex]] = [scenes[targetIndex], scenes[rowIndex]];

  return rebuildScriptTextFromScenes(
    renumberScenes({
      ...preview,
      scenes,
    }),
  );
}

function addSubtitle(preview: ScriptPreviewPayload): ScriptPreviewPayload {
  return {
    ...preview,
    subtitle_segments: [
      ...preview.subtitle_segments,
      {
        scene_index: preview.scenes[0]?.scene_index ?? 1,
        text: "",
        start_sec: 0,
        end_sec: 1,
      },
    ],
  };
}

function deleteSubtitle(
  preview: ScriptPreviewPayload,
  subtitleIndex: number,
): ScriptPreviewPayload {
  return {
    ...preview,
    subtitle_segments: preview.subtitle_segments.filter((_, index) => index !== subtitleIndex),
  };
}

function moveSubtitle(
  preview: ScriptPreviewPayload,
  subtitleIndex: number,
  direction: -1 | 1,
): ScriptPreviewPayload {
  const targetIndex = subtitleIndex + direction;
  if (targetIndex < 0 || targetIndex >= preview.subtitle_segments.length) return preview;

  const subtitle_segments = [...preview.subtitle_segments];
  [subtitle_segments[subtitleIndex], subtitle_segments[targetIndex]] = [
    subtitle_segments[targetIndex],
    subtitle_segments[subtitleIndex],
  ];

  return {
    ...preview,
    subtitle_segments,
  };
}

const inputClass =
  "w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none";

const inputClassMuted =
  "w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white/55 outline-none";

const textareaClass =
  "w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none resize-y";