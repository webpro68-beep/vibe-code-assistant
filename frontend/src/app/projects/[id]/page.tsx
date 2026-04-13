"use client";
import { useEffect, useState } from "react";
import {
  getProject,
  getProjectRenderStatus,
  getProjectRenderEvents,
  triggerProjectRender,
  retryProjectRender,
  rerenderScene,
  processTemplateProjectFeedback,
  getCharacterReferencePacks,
  createCharacterReferencePack,
  updateProjectVeoConfig,
  createVeoBatchRun,
} from "@/src/lib/api";

export default function ProjectWorkspacePage({ params }: { params: { id: string } }) {
  const projectId = params.id;
  const [project, setProject] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [packs, setPacks] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [veoMode, setVeoMode] = useState("text_to_video");
  const [providerModel, setProviderModel] = useState("veo-3.1-generate-001");
  const [characterReferencePackId, setCharacterReferencePackId] = useState("");
  const [applyLockAll, setApplyLockAll] = useState(true);
  const [previewReferenceMode, setPreviewReferenceMode] = useState(false);
  const [soundGeneration, setSoundGeneration] = useState(false);
  const [startImageUrl, setStartImageUrl] = useState("");
  const [endImageUrl, setEndImageUrl] = useState("");
  const [batchScripts, setBatchScripts] = useState("");
  const [newPackName, setNewPackName] = useState("");
  const [newPackSummary, setNewPackSummary] = useState("");
  const [newPackHeroImage, setNewPackHeroImage] = useState("");
  const [batchResult, setBatchResult] = useState<any>(null);

  const refresh = async () => {
    const [p, s, e, packData] = await Promise.all([
      getProject(projectId),
      getProjectRenderStatus(projectId),
      getProjectRenderEvents(projectId),
      getCharacterReferencePacks(),
    ]);
    setProject(p);
    setStatus(s);
    setEvents(e.items || []);
    setPacks(packData.items || []);
    if (p?.veo_config) {
      setVeoMode(p.veo_config.veo_mode || "text_to_video");
      setProviderModel(p.veo_config.provider_model || "veo-3.1-generate-001");
      setCharacterReferencePackId(p.veo_config.character_reference_pack_id || "");
      setApplyLockAll(Boolean(p.veo_config.apply_character_lock_to_all_scenes));
      setPreviewReferenceMode(Boolean(p.veo_config.use_preview_reference_mode));
      setSoundGeneration(Boolean(p.veo_config.sound_generation));
    }
    const firstScene = p?.scenes?.[0];
    if (firstScene?.start_image_url) setStartImageUrl(firstScene.start_image_url);
    if (firstScene?.end_image_url) setEndImageUrl(firstScene.end_image_url);
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [projectId]);

  const canRender = project && ["ready_to_render", "draft", "render_failed", "final_ready"].includes(project.status);

  const saveVeoConfig = async () => {
    setBusy(true);
    await updateProjectVeoConfig(projectId, {
      provider_model: providerModel,
      veo_mode: veoMode,
      character_reference_pack_id: characterReferencePackId || null,
      apply_character_lock_to_all_scenes: applyLockAll,
      use_preview_reference_mode: previewReferenceMode,
      sound_generation: soundGeneration,
      scene_inputs: [
        {
          scene_index: 1,
          start_image_url: startImageUrl || null,
          end_image_url: endImageUrl || null,
          character_reference_image_urls: [],
        },
      ],
    });
    await refresh();
    setBusy(false);
  };

  const createPack = async () => {
    setBusy(true);
    await createCharacterReferencePack({
      pack_name: newPackName,
      owner_project_id: projectId,
      identity_summary: newPackSummary,
      appearance_lock_json: { summary: newPackSummary },
      prompt_lock_tokens: [],
      negative_drift_tokens: [],
      images: newPackHeroImage ? [{ image_role: "hero", image_url: newPackHeroImage }] : [],
    });
    setNewPackName("");
    setNewPackSummary("");
    setNewPackHeroImage("");
    await refresh();
    setBusy(false);
  };

  const createBatch = async () => {
    const scripts = batchScripts
      .split("\n---\n")
      .map((x) => x.trim())
      .filter(Boolean)
      .map((script_text, index) => ({ name: `Batch Script ${index + 1}`, script_text, style_preset: project?.style_preset || null }));
    setBusy(true);
    const result = await createVeoBatchRun({
      batch_name: `${project?.name || "Project"} Veo Batch`,
      provider_model: providerModel,
      veo_mode: veoMode,
      aspect_ratio: project?.format || "9:16",
      target_platform: project?.target_platform || "shorts",
      character_reference_pack_id: characterReferencePackId || null,
      apply_character_lock_to_all_scenes: applyLockAll,
      use_preview_reference_mode: previewReferenceMode,
      sound_generation: soundGeneration,
      scene_inputs: [{ scene_index: 1, start_image_url: startImageUrl || null, end_image_url: endImageUrl || null, character_reference_image_urls: [] }],
      scripts,
    });
    setBatchResult(result);
    setBusy(false);
  };

  return (
    <main style={{ padding: 24 }}>
      <h1>{project?.name || "Project Workspace"}</h1>

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 16 }}>
        <section style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
          <h2>Idea & Style</h2>
          <div>Idea: {project?.idea}</div>
          <div>Style: {project?.style_preset}</div>
          <div>Platform: {project?.target_platform}</div>
          <div>Format: {project?.format}</div>
          <div>Status: {project?.status}</div>
          <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button onClick={async () => { setBusy(true); await triggerProjectRender(projectId); await refresh(); setBusy(false); }} disabled={!canRender || busy}>Render Video</button>
            <button onClick={async () => { setBusy(true); await retryProjectRender(projectId); await refresh(); setBusy(false); }} disabled={busy}>Retry Render</button>
            <button onClick={async () => { setBusy(true); await processTemplateProjectFeedback(projectId); await refresh(); setBusy(false); }} disabled={busy}>Process Template Feedback</button>
          </div>
        </section>

        <section style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
          <h2>Render Status</h2>
          <div>Current step: {status?.current_step || "-"}</div>
          <div>Progress: {status?.progress_percent || 0}%</div>
          <div>Render status: {status?.render_status || "-"}</div>
          <div>Fail reason: {status?.fail_reason || "-"}</div>
          {status?.preview_video_url && <div>Preview: <a href={status.preview_video_url}>Open preview</a></div>}
          {status?.final_video_url && <div>Final: <a href={status.final_video_url}>Open final</a></div>}
          {status?.thumbnail_url && <div>Thumbnail: <a href={status.thumbnail_url}>Open thumbnail</a></div>}
        </section>
      </div>

      <section style={{ marginTop: 16, border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
        <h2>Veo 3.1 Controls</h2>
        <div style={{ display: "grid", gap: 10 }}>
          <label>Model
            <select value={providerModel} onChange={(e) => setProviderModel(e.target.value)}>
              <option value="veo-3.1-generate-001">veo-3.1-generate-001</option>
              <option value="veo-3.1-fast-generate-001">veo-3.1-fast-generate-001</option>
              <option value="veo-3.1-generate-preview">veo-3.1-generate-preview</option>
              <option value="veo-3.1-fast-generate-preview">veo-3.1-fast-generate-preview</option>
            </select>
          </label>
          <label>Mode
            <select value={veoMode} onChange={(e) => setVeoMode(e.target.value)}>
              <option value="text_to_video">Text to Video</option>
              <option value="image_to_video">Image to Video</option>
              <option value="first_last_frames">Start - End</option>
              <option value="reference_image_to_video">Preview Reference Image to Video</option>
            </select>
          </label>
          <label>Character Reference Pack
            <select value={characterReferencePackId} onChange={(e) => setCharacterReferencePackId(e.target.value)}>
              <option value="">None</option>
              {packs.map((p: any) => <option key={p.id} value={p.id}>{p.pack_name}</option>)}
            </select>
          </label>
          <label>Start Image URL
            <input value={startImageUrl} onChange={(e) => setStartImageUrl(e.target.value)} />
          </label>
          <label>End Image URL
            <input value={endImageUrl} onChange={(e) => setEndImageUrl(e.target.value)} />
          </label>
          <label><input type="checkbox" checked={applyLockAll} onChange={(e) => setApplyLockAll(e.target.checked)} /> Apply character lock to all scenes</label>
          <label><input type="checkbox" checked={previewReferenceMode} onChange={(e) => setPreviewReferenceMode(e.target.checked)} /> Use preview reference mode</label>
          <label><input type="checkbox" checked={soundGeneration} onChange={(e) => setSoundGeneration(e.target.checked)} /> Request native sound generation</label>
          <button onClick={saveVeoConfig} disabled={busy}>Save Veo Config</button>
        </div>
      </section>

      <section style={{ marginTop: 16, border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
        <h2>Character Reference Pack</h2>
        <div style={{ display: "grid", gap: 8 }}>
          <input placeholder="Pack name" value={newPackName} onChange={(e) => setNewPackName(e.target.value)} />
          <textarea placeholder="Identity summary" value={newPackSummary} onChange={(e) => setNewPackSummary(e.target.value)} />
          <input placeholder="Hero image URL" value={newPackHeroImage} onChange={(e) => setNewPackHeroImage(e.target.value)} />
          <button onClick={createPack} disabled={busy || !newPackName}>Create Pack</button>
        </div>
      </section>

      <section style={{ marginTop: 16, border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
        <h2>Veo Batch Run</h2>
        <p>Separate scripts with <code>---</code> on its own line.</p>
        <textarea rows={10} value={batchScripts} onChange={(e) => setBatchScripts(e.target.value)} style={{ width: "100%" }} />
        <div style={{ marginTop: 8 }}>
          <button onClick={createBatch} disabled={busy || !batchScripts.trim()}>Create Veo Batch</button>
        </div>
        {batchResult && (
          <div style={{ marginTop: 12 }}>
            <div>Batch ID: {batchResult.veo_batch_run_id}</div>
            <div>Total scripts: {batchResult.total_scripts}</div>
            <div>Status: {batchResult.status}</div>
          </div>
        )}
      </section>

      <section style={{ marginTop: 16, border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
        <h2>Scenes</h2>
        <div style={{ display: "grid", gap: 10 }}>
          {(project?.scenes || []).map((scene: any) => (
            <div key={scene.scene_index} style={{ border: "1px solid #eee", borderRadius: 8, padding: 12 }}>
              <div><strong>Scene {scene.scene_index} — {scene.title}</strong></div>
              <div>{scene.script_text}</div>
              <div>Duration: {scene.target_duration_sec}s</div>
              <div>Mode: {scene.provider_mode || veoMode}</div>
              <button onClick={async () => { setBusy(true); await rerenderScene(projectId, scene.scene_index); await refresh(); setBusy(false); }} disabled={busy}>
                Rerender Scene
              </button>
            </div>
          ))}
        </div>
      </section>

      <section style={{ marginTop: 16, border: "1px solid #ddd", borderRadius: 8, padding: 16 }}>
        <h2>Render Events</h2>
        <div style={{ display: "grid", gap: 8 }}>
          {events.map((event: any) => (
            <div key={event.id} style={{ borderBottom: "1px solid #eee", paddingBottom: 8 }}>
              <div><strong>{event.event_type}</strong> — {event.status || "-"}</div>
              <div>Scene: {event.scene_index ?? "-"}</div>
              <div>At: {event.occurred_at || "-"}</div>
              <div>{event.error_message || ""}</div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
