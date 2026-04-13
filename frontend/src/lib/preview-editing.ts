import { ScriptPreviewPayload } from "@/src/lib/api";

export function updateSceneField(
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

export function updateSubtitleField(
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

export function rebuildScriptTextFromScenes(preview: ScriptPreviewPayload): ScriptPreviewPayload {
  const scriptText = preview.scenes
    .map((scene) => scene.script_text.trim())
    .filter(Boolean)
    .join("\n\n");

  return {
    ...preview,
    script_text: scriptText,
  };
}

export function renumberScenes(preview: ScriptPreviewPayload): ScriptPreviewPayload {
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

export function addScene(preview: ScriptPreviewPayload): ScriptPreviewPayload {
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

export function deleteScene(preview: ScriptPreviewPayload, rowIndex: number): ScriptPreviewPayload {
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

export function moveScene(preview: ScriptPreviewPayload, rowIndex: number, direction: -1 | 1): ScriptPreviewPayload {
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

export function addSubtitle(preview: ScriptPreviewPayload): ScriptPreviewPayload {
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

export function deleteSubtitle(preview: ScriptPreviewPayload, subtitleIndex: number): ScriptPreviewPayload {
  return {
    ...preview,
    subtitle_segments: preview.subtitle_segments.filter((_, index) => index !== subtitleIndex),
  };
}

export function moveSubtitle(
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