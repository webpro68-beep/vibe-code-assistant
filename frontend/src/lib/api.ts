export type AspectRatio = "9:16" | "16:9" | "1:1";
export type TargetPlatform = "shorts" | "tiktok" | "reels" | "youtube";
export type SourceMode = "script_upload";
export type SubtitleMode = "none" | "soft" | "burn";
export type RenderProvider =
  | "veo_3_1"
  | "runway_gen4_turbo"
  | "kling_text"
  | "kling_image";

export interface ScriptScene {
  scene_index: number;
  title: string;
  script_text: string;
  target_duration_sec: number;
}

export interface SubtitleSegment {
  scene_index?: number | null;
  text: string;
  start_sec: number;
  end_sec: number;
}

export interface ScriptPreviewPayload {
  source_mode: SourceMode;
  aspect_ratio: AspectRatio;
  target_platform: TargetPlatform;
  style_preset?: string | null;
  original_filename?: string | null;
  script_text: string;
  scenes: ScriptScene[];
  subtitle_segments: SubtitleSegment[];
}

export interface ValidationIssue {
  code: string;
  message: string;
  severity: "error" | "warning";
  target_type: "scene" | "subtitle" | "preview";
  target_index?: number | null;
  field?: string | null;
}

export interface ValidationResult {
  valid: boolean;
  issues: ValidationIssue[];
}

export interface RenderPlannedScene extends ScriptScene {
  provider?: RenderProvider | string;
  provider_mode?: string;
  provider_target_duration_sec?: number;
  source_scene_index?: number;
  visual_prompt?: string;
  start_image_url?: string | null;
  end_image_url?: string | null;
}

export interface PreparedRenderPlan {
  provider: RenderProvider | string;
  provider_label?: string;
  aspect_ratio: AspectRatio;
  supports_native_audio?: boolean;
  supports_multi_shot_prompt?: boolean;
  planned_scenes: RenderPlannedScene[];
}

export interface ProviderRenderPayload {
  scene_index: number;
  title: string;
  provider: RenderProvider | string;
  adapter_kind: string;
  endpoint: string;
  model: string;
  body: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface BuildProviderPayloadsResult {
  provider: RenderProvider | string;
  payloads: ProviderRenderPayload[];
}

export interface RenderJobScene {
  id: string;
  scene_index: number;
  title: string;
  status: string;
  provider_task_id?: string | null;
  provider_operation_name?: string | null;
  output_video_url?: string | null;
  local_video_path?: string | null;
  error_message?: string | null;
}

export interface FinalPreviewTimeline {
  video_url: string;
  scene_count: number;
  subtitle_count: number;
  scenes: Array<Record<string, unknown>>;
  subtitle_segments: SubtitleSegment[];
}

export interface RenderJob {
  id?: string;
  project_id?: string;
  job_id: string;
  status: string;
  provider: RenderProvider | string;
  aspect_ratio?: AspectRatio;
  style_preset?: string | null;
  planned_scene_count: number;
  completed_scene_count: number;
  failed_scene_count: number;
  subtitle_mode?: SubtitleMode;
  final_video_url?: string | null;
  output_url?: string | null;
  output_path?: string | null;
  storage_key?: string | null;
  thumbnail_url?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  timeline?: FinalPreviewTimeline | null;
  final_timeline?: FinalPreviewTimeline | null;
  error_message?: string | null;
  scenes: RenderJobScene[];
}

export interface HealthCheckPayload {
  ok: boolean;
  checks?: Record<string, unknown>;
  service?: string;
  workers?: string[];
  worker_count?: number;
  stats_keys?: string[];
  error?: string;
}

interface ApiEnvelope<T> {
  ok: boolean;
  data: T;
  error?: {
    message?: string;
    [key: string]: unknown;
  } | null;
  meta?: Record<string, unknown>;
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") ||
  "http://localhost:8000/api/v1";

const RAW_BASE_URL = API_BASE_URL.endsWith("/api/v1")
  ? API_BASE_URL.slice(0, -7)
  : API_BASE_URL;

function buildUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalized}`;
}

function buildRawUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${RAW_BASE_URL}${normalized}`;
}

async function parseErrorResponse(res: Response): Promise<string> {
  try {
    const json = await res.json();

    if (typeof json?.detail === "string") return json.detail;
    if (typeof json?.message === "string") return json.message;
    if (typeof json?.error?.message === "string") return json.error.message;
    if (typeof json?.error === "string") return json.error;

    if (json?.detail && typeof json.detail === "object") {
      const message = json.detail.message;
      if (typeof message === "string") return message;
    }
  } catch {
    // fall through
  }

  return `Request failed with status ${res.status}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers || {});

  if (!(init?.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(buildUrl(path), {
    ...init,
    headers,
  });

  if (!res.ok) {
    throw new Error(await parseErrorResponse(res));
  }

  const json = (await res.json()) as ApiEnvelope<T> | T;

  if (typeof json === "object" && json !== null && "ok" in json) {
    const envelope = json as ApiEnvelope<T>;
    if (!envelope.ok) {
      throw new Error(envelope.error?.message || "Request failed");
    }
    return envelope.data;
  }

  return json as T;
}

export { request };

export async function uploadScriptFileForPreview(input: {
  file: File;
  aspect_ratio?: AspectRatio;
  target_platform?: TargetPlatform;
  style_preset?: string;
}): Promise<ScriptPreviewPayload> {
  const form = new FormData();
  form.append("file", input.file);
  form.append("aspect_ratio", input.aspect_ratio || "9:16");
  form.append("target_platform", input.target_platform || "shorts");
  form.append("style_preset", input.style_preset || "cinematic_dark");

  const res = await fetch(buildRawUrl("/api/v1/script-upload/preview"), {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    throw new Error(await parseErrorResponse(res));
  }

  const json = (await res.json()) as ApiEnvelope<ScriptPreviewPayload>;
  if (!json.ok) {
    throw new Error(json.error?.message || "Failed to upload script file for preview");
  }

  return json.data;
}

export async function previewScriptUpload(input: {
  file: File;
  aspect_ratio?: AspectRatio;
  target_platform?: TargetPlatform;
  style_preset?: string;
}): Promise<ScriptPreviewPayload> {
  return uploadScriptFileForPreview(input);
}

export async function validatePreviewPayload(
  preview: ScriptPreviewPayload,
): Promise<ValidationResult> {
  return request<ValidationResult>("/script-preview/validate", {
    method: "POST",
    body: JSON.stringify(preview),
  });
}

export async function rebuildSubtitlesFromPreview(
  preview: ScriptPreviewPayload,
): Promise<ScriptPreviewPayload> {
  return request<ScriptPreviewPayload>("/script-preview/rebuild-subtitles", {
    method: "POST",
    body: JSON.stringify(preview),
  });
}

export async function recalculateDurationsFromPreview(
  preview: ScriptPreviewPayload,
): Promise<ScriptPreviewPayload> {
  return request<ScriptPreviewPayload>("/script-preview/recalculate-durations", {
    method: "POST",
    body: JSON.stringify(preview),
  });
}

export async function recalculateAllFromPreview(
  preview: ScriptPreviewPayload,
): Promise<ScriptPreviewPayload> {
  return request<ScriptPreviewPayload>("/script-preview/recalculate-all", {
    method: "POST",
    body: JSON.stringify(preview),
  });
}

export async function createProjectFromPreview(input: {
  name: string;
  idea?: string;
  preview_payload: ScriptPreviewPayload;
  confirmed?: boolean;
}): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>("/projects/create-from-script-preview", {
    method: "POST",
    body: JSON.stringify({
      confirmed: true,
      ...input,
    }),
  });
}

export async function createProjectFromScriptPreview(input: {
  name: string;
  idea?: string;
  preview_payload: ScriptPreviewPayload;
  confirmed?: boolean;
}): Promise<Record<string, unknown>> {
  return createProjectFromPreview(input);
}

export async function prepareRenderPlan(input: {
  provider: RenderProvider;
  aspect_ratio: AspectRatio;
  scenes: Array<{
    scene_index: number;
    title: string;
    script_text: string;
    target_duration_sec: number;
    visual_prompt?: string;
    start_image_url?: string | null;
    end_image_url?: string | null;
  }>;
}): Promise<PreparedRenderPlan> {
  return request<PreparedRenderPlan>("/render/prepare-plan", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function buildProviderPayloads(input: {
  provider: RenderProvider;
  aspect_ratio: AspectRatio;
  style_preset?: string;
  planned_scenes: RenderPlannedScene[];
}): Promise<BuildProviderPayloadsResult> {
  return request<BuildProviderPayloadsResult>("/render/build-provider-payloads", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function createRenderJob(input: {
  project_id: string;
  provider: RenderProvider;
  aspect_ratio: AspectRatio;
  style_preset?: string;
  subtitle_mode?: SubtitleMode;
  planned_scenes: RenderPlannedScene[];
}): Promise<{
  job_id: string;
  status: string;
  queue_message?: Record<string, unknown>;
}> {
  return request<{
    job_id: string;
    status: string;
    queue_message?: Record<string, unknown>;
  }>("/render/jobs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function getRenderJob(jobId: string): Promise<RenderJob> {
  const data = await request<any>(`/render/jobs/${jobId}`, { method: "GET" });
  return { id: data.id, job_id: data.id || jobId, project_id: data.project_id, status: data.status, provider: data.provider, aspect_ratio: data.aspect_ratio, style_preset: data.style_preset, subtitle_mode: data.subtitle_mode, planned_scene_count: data.planned_scene_count ?? 0, completed_scene_count: Array.isArray(data.scenes) ? data.scenes.filter((scene: any) => scene.status === "succeeded").length : 0, failed_scene_count: Array.isArray(data.scenes) ? data.scenes.filter((scene: any) => scene.status === "failed").length : 0, scenes: Array.isArray(data.scenes) ? data.scenes.map((scene: any) => ({ id: scene.id, job_id: scene.job_id, scene_index: scene.scene_index, title: scene.title || `Scene ${scene.scene_index}`, status: scene.status, provider_task_id: scene.provider_task_id, provider_operation_name: scene.provider_operation_name, output_url: scene.output_url, output_path: scene.output_path, error_message: scene.error_message, completed_at: scene.completed_at })) : [], started_at: data.started_at, completed_at: data.completed_at, created_at: data.created_at, updated_at: data.updated_at, final_video_url: data.output_url, output_url: data.output_url, output_path: data.output_path, storage_key: data.storage_key, thumbnail_url: data.thumbnail_url, timeline: data.final_timeline, final_timeline: data.final_timeline, error_message: data.error_message };
}

export async function getHealth(): Promise<HealthCheckPayload> {
  const res = await fetch(buildRawUrl("/healthz"), {
    method: "GET",
  });

  if (!res.ok) {
    throw new Error(await parseErrorResponse(res));
  }

  return (await res.json()) as HealthCheckPayload;
}

export async function getWorkerHealth(): Promise<HealthCheckPayload> {
  const res = await fetch(buildRawUrl("/healthz/workers"), {
    method: "GET",
  });

  if (!res.ok) {
    throw new Error(await parseErrorResponse(res));
  }

  return (await res.json()) as HealthCheckPayload;
}

export async function getPostgresHealth(): Promise<HealthCheckPayload> {
  const res = await fetch(buildRawUrl("/healthz/postgres"), {
    method: "GET",
  });

  if (!res.ok) {
    throw new Error(await parseErrorResponse(res));
  }

  return (await res.json()) as HealthCheckPayload;
}

export async function getRedisHealth(): Promise<HealthCheckPayload> {
  const res = await fetch(buildRawUrl("/healthz/redis"), {
    method: "GET",
  });

  if (!res.ok) {
    throw new Error(await parseErrorResponse(res));
  }

  return (await res.json()) as HealthCheckPayload;
}


export interface RenderEventItem { id: string; source: string; event_type: string; job_id: string; scene_task_id?: string | null; scene_index?: number | null; provider?: string | null; status?: string | null; provider_status_raw?: string | null; failure_code?: string | null; failure_category?: string | null; error_message?: string | null; provider_task_id?: string | null; provider_operation_name?: string | null; provider_request_id?: string | null; signature_valid?: boolean | null; processed?: boolean | null; occurred_at: string; payload: Record<string, unknown>; }
export interface RenderEventsResponse { items: RenderEventItem[]; total: number; }
export interface RenderJobHealthSummary { status: string; reason?: string | null; total_scenes: number; queued_scenes: number; processing_scenes: number; succeeded_scenes: number; failed_scenes: number; stalled_scenes: number; degraded_scenes: number; last_event_at?: string | null; active_scene_ids: string[]; stalled_scene_ids: string[]; degraded_scene_ids: string[]; }
export interface RenderJobListItem { id: string; project_id: string; provider: string; status: string; health_status?: string | null; health_reason?: string | null; aspect_ratio: string; style_preset?: string | null; subtitle_mode?: string | null; planned_scene_count: number; processing_scene_count: number; succeeded_scene_count: number; failed_scene_count_snapshot: number; stalled_scene_count: number; degraded_scene_count: number; active_scene_count: number; created_at?: string | null; updated_at?: string | null; last_event_at?: string | null; last_health_transition_at?: string | null; }
export interface RenderJobListPage { items: RenderJobListItem[]; total: number; limit: number; }
export interface ProviderCountItem { provider: string; total_jobs: number; healthy_jobs: number; degraded_jobs: number; stalled_jobs: number; failed_jobs: number; completed_jobs: number; }
export interface TransitionWindowSummary { window: string; total_transitions: number; degraded_transitions: number; stalled_transitions: number; recovered_transitions: number; failed_transitions: number; completed_transitions: number; }
export interface RenderDashboardSummaryResponse { total_jobs: number; healthy_jobs: number; degraded_jobs: number; stalled_jobs: number; failed_jobs: number; completed_jobs: number; queued_jobs: number; total_active_scenes: number; total_stalled_scenes: number; total_degraded_scenes: number; counts_by_provider: ProviderCountItem[]; recent_transitions: TransitionWindowSummary[]; }
export interface IncidentJobSnapshot { job_id: string; project_id: string; provider: string; status: string; health_status?: string | null; health_reason?: string | null; planned_scene_count: number; processing_scene_count: number; succeeded_scene_count: number; failed_scene_count_snapshot: number; stalled_scene_count: number; degraded_scene_count: number; active_scene_count: number; created_at?: string | null; updated_at?: string | null; last_event_at?: string | null; last_health_transition_at?: string | null; }
export interface RecentIncidentItem { event_id: string; incident_key: string; event_type: string; occurred_at: string; previous_status?: string | null; current_status?: string | null; previous_reason?: string | null; current_reason?: string | null; workflow_status?: string | null; acknowledged: boolean; muted: boolean; assigned_to?: string | null; job: IncidentJobSnapshot; payload: Record<string, unknown>; }
export interface RecentIncidentsResponse { items: RecentIncidentItem[]; limit: number; total_returned: number; next_cursor?: string | null; }

export interface IncidentActionLogItem { id: string; incident_key: string; event_id?: string | null; job_id: string; action_type: string; actor: string; reason?: string | null; payload: Record<string, unknown>; created_at: string; }
export interface IncidentStateSnapshot { incident_key: string; job_id: string; project_id: string; provider: string; incident_family: string; current_event_id?: string | null; current_event_type?: string | null; current_severity_rank: number; first_seen_at: string; last_seen_at: string; last_transition_at: string; status: string; acknowledged: boolean; acknowledged_by?: string | null; acknowledged_at?: string | null; assigned_to?: string | null; assigned_by?: string | null; assigned_at?: string | null; muted: boolean; muted_until?: string | null; muted_by?: string | null; mute_reason?: string | null; suppressed: boolean; suppression_reason?: string | null; reopen_count: number; last_reopened_at?: string | null; resolved_at?: string | null; note?: string | null; created_at: string; updated_at: string; }
export interface IncidentHistoryResponse { incident: IncidentStateSnapshot; actions: IncidentActionLogItem[]; timeline_events: RenderEventItem[]; projected_timeline: RenderEventItem[]; }

export async function getRenderJobHealth(jobId: string): Promise<RenderJobHealthSummary> { return request<RenderJobHealthSummary>(`/render/jobs/${jobId}/health`, { method: "GET" }); }

export async function getRenderJobEvents(jobId: string): Promise<RenderEventsResponse> { return request<RenderEventsResponse>(`/render/jobs/${jobId}/events`, { method: "GET" }); }

export async function getRenderSceneEvents(sceneTaskId: string): Promise<RenderEventsResponse> { return request<RenderEventsResponse>(`/render/scenes/${sceneTaskId}/events`, { method: "GET" }); }

export async function listRenderDashboardJobs(input?: { limit?: number; provider?: string; health_status?: string; }): Promise<RenderJobListPage> { const params = new URLSearchParams(); if (input?.limit) params.set("limit", String(input.limit)); if (input?.provider) params.set("provider", input.provider); if (input?.health_status) params.set("health_status", input.health_status); const suffix = params.toString() ? `?${params.toString()}` : ""; return request<RenderJobListPage>(`/render/dashboard/jobs${suffix}`, { method: "GET" }); }

export async function getRenderDashboardSummary(): Promise<RenderDashboardSummaryResponse> { return request<RenderDashboardSummaryResponse>("/render/dashboard/summary", { method: "GET" }); }


export async function acknowledgeRenderIncident(input: { incident_key: string; actor: string; reason?: string; }): Promise<{ ok: boolean; incident_key: string; status: string }> { return request<{ ok: boolean; incident_key: string; status: string }>(`/render/dashboard/incidents/${encodeURIComponent(input.incident_key)}/acknowledge`, { method: "POST", body: JSON.stringify({ actor: input.actor, reason: input.reason }) }); }

export async function assignRenderIncident(input: { incident_key: string; actor: string; assigned_to: string; reason?: string; }): Promise<{ ok: boolean; incident_key: string; status: string; assigned_to?: string | null }> { return request<{ ok: boolean; incident_key: string; status: string; assigned_to?: string | null }>(`/render/dashboard/incidents/${encodeURIComponent(input.incident_key)}/assign`, { method: "POST", body: JSON.stringify({ actor: input.actor, assigned_to: input.assigned_to, reason: input.reason }) }); }

export async function muteRenderIncident(input: { incident_key: string; actor: string; muted_until?: string; reason?: string; }): Promise<{ ok: boolean; incident_key: string; status: string; muted_until?: string | null }> { return request<{ ok: boolean; incident_key: string; status: string; muted_until?: string | null }>(`/render/dashboard/incidents/${encodeURIComponent(input.incident_key)}/mute`, { method: "POST", body: JSON.stringify({ actor: input.actor, muted_until: input.muted_until, reason: input.reason }) }); }


export async function getRenderIncidentDetail(incidentKey: string): Promise<IncidentHistoryResponse> { return request<IncidentHistoryResponse>(`/render/dashboard/incidents/${encodeURIComponent(incidentKey)}`, { method: "GET" }); }

export async function getRenderIncidentHistory(incidentKey: string): Promise<IncidentHistoryResponse> { return request<IncidentHistoryResponse>(`/render/dashboard/incidents/${encodeURIComponent(incidentKey)}/history`, { method: "GET" }); }


export async function resolveRenderIncident(input: { incident_key: string; actor: string; reason?: string; }): Promise<{ ok: boolean; incident_key: string; status: string; resolved_at?: string | null }> { return request<{ ok: boolean; incident_key: string; status: string; resolved_at?: string | null }>(`/render/dashboard/incidents/${encodeURIComponent(input.incident_key)}/resolve`, { method: "POST", body: JSON.stringify({ actor: input.actor, reason: input.reason }) }); }

export async function reopenRenderIncident(input: { incident_key: string; actor: string; reason?: string; }): Promise<{ ok: boolean; incident_key: string; status: string; reopen_count?: number }> { return request<{ ok: boolean; incident_key: string; status: string; reopen_count?: number }>(`/render/dashboard/incidents/${encodeURIComponent(input.incident_key)}/reopen`, { method: "POST", body: JSON.stringify({ actor: input.actor, reason: input.reason }) }); }

export async function updateRenderIncidentNote(input: { incident_key: string; actor: string; note?: string | null; }): Promise<{ ok: boolean; incident_key: string; note?: string | null; updated_at: string }> { return request<{ ok: boolean; incident_key: string; note?: string | null; updated_at: string }>(`/render/dashboard/incidents/${encodeURIComponent(input.incident_key)}/note`, { method: "PUT", body: JSON.stringify({ actor: input.actor, note: input.note }) }); }


export interface IncidentListFilters { provider?: string | null; workflow_status?: string | null; assigned_to?: string | null; segment?: string | null; show_muted?: boolean; limit?: number; }
export interface IncidentSavedView { id: string; owner_actor: string; name: string; description?: string | null; is_shared: boolean; share_scope?: string; shared_team_id?: string | null; allowed_roles?: string[]; filters: IncidentListFilters; sort_key?: string | null; created_at: string; updated_at: string; }
export interface IncidentSavedViewListResponse { items: IncidentSavedView[]; }
export interface BulkIncidentActionResult { incident_key: string; ok: boolean; status?: string | null; error?: string | null; }
export interface BulkIncidentActionResponse { ok: boolean; action_type: string; attempted: number; succeeded: number; failed: number; items: BulkIncidentActionResult[]; }

export interface IncidentSegmentMetricItem { segment: string; total: number; unacknowledged: number; assigned: number; muted: number; resolved: number; stale_over_30m: number; high_severity: number; }
export interface IncidentSegmentMetricsResponse { generated_at: string; provider?: string | null; show_muted: boolean; items: IncidentSegmentMetricItem[]; }
export interface BulkPreviewItem { incident_key: string; current_status?: string | null; assigned_to?: string | null; muted: boolean; acknowledged: boolean; eligible: boolean; reason?: string | null; predicted_status?: string | null; predicted_assigned_to?: string | null; predicted_muted_until?: string | null; }
export interface BulkPreviewResponse { ok: boolean; action_type: string; attempted: number; eligible: number; skipped: number; items: BulkPreviewItem[]; guardrails?: BulkGuardrailEvaluationResponse; }

export async function listIncidentSavedViews(actor?: string): Promise<IncidentSavedViewListResponse> { const params = new URLSearchParams(); if (actor) params.set("actor", actor); const suffix = params.toString() ? `?${params.toString()}` : ""; return request<IncidentSavedViewListResponse>(`/render/dashboard/incidents/views${suffix}`, { method: "GET" }); }
export async function createIncidentSavedView(input: { owner_actor: string; name: string; description?: string; is_shared?: boolean; share_scope?: string; shared_team_id?: string; allowed_roles?: string[]; filters: IncidentListFilters; sort_key?: string; }): Promise<IncidentSavedView> { return request<IncidentSavedView>(`/render/dashboard/incidents/views`, { method: "POST", body: JSON.stringify(input) }); }
export async function updateIncidentSavedView(input: { view_id: string; actor: string; name?: string; description?: string; is_shared?: boolean; share_scope?: string; shared_team_id?: string; allowed_roles?: string[]; filters?: IncidentListFilters; sort_key?: string; }): Promise<IncidentSavedView> { const { view_id, actor, ...body } = input; return request<IncidentSavedView>(`/render/dashboard/incidents/views/${encodeURIComponent(view_id)}?actor=${encodeURIComponent(actor)}`, { method: "PUT", body: JSON.stringify(body) }); }
export async function deleteIncidentSavedView(view_id: string, actor: string): Promise<{ ok: boolean; view_id: string }> { return request<{ ok: boolean; view_id: string }>(`/render/dashboard/incidents/views/${encodeURIComponent(view_id)}?actor=${encodeURIComponent(actor)}`, { method: "DELETE" }); }


export async function getIncidentSegmentMetrics(input?: { provider?: string; show_muted?: boolean; assignee?: string; }): Promise<IncidentSegmentMetricsResponse> { const params = new URLSearchParams(); if (input?.provider) params.set("provider", input.provider); if (typeof input?.show_muted === "boolean") params.set("show_muted", String(input.show_muted)); if (input?.assignee) params.set("assignee", input.assignee); const suffix = params.toString() ? `?${params.toString()}` : ""; return request<IncidentSegmentMetricsResponse>(`/render/dashboard/incidents/metrics${suffix}`, { method: "GET" }); }
export async function previewBulkIncidentAction(input: { action_type: "acknowledge" | "assign" | "mute" | "resolve"; actor: string; incident_keys: string[]; reason?: string; assigned_to?: string; muted_until?: string; }): Promise<BulkPreviewResponse> { const { action_type, ...body } = input; return request<BulkPreviewResponse>(`/render/dashboard/incidents/bulk/${action_type}/preview`, { method: "POST", body: JSON.stringify(body) }); }

export async function getRecentRenderIncidents(input?: { limit?: number; provider?: string; show_muted?: boolean; workflow_status?: string; assigned_to?: string; segment?: string; }): Promise<RecentIncidentsResponse> { const params = new URLSearchParams(); if (input?.limit) params.set("limit", String(input.limit)); if (input?.provider) params.set("provider", input.provider); if (typeof input?.show_muted === "boolean") params.set("show_muted", String(input.show_muted)); if (input?.workflow_status) params.set("workflow_status", input.workflow_status); if (input?.assigned_to) params.set("assigned_to", input.assigned_to); if (input?.segment) params.set("segment", input.segment); const suffix = params.toString() ? `?${params.toString()}` : ""; return request<RecentIncidentsResponse>(`/render/dashboard/incidents/recent${suffix}`, { method: "GET" }); }

async function bulkIncidentAction(path: string, body: { actor: string; incident_keys: string[]; reason?: string; assigned_to?: string; muted_until?: string; }): Promise<BulkIncidentActionResponse> { return request<BulkIncidentActionResponse>(path, { method: "POST", body: JSON.stringify(body) }); }
export async function bulkAcknowledgeRenderIncidents(input: { actor: string; incident_keys: string[]; reason?: string; }): Promise<BulkIncidentActionResponse> { return bulkIncidentAction(`/render/dashboard/incidents/bulk/acknowledge`, input); }
export async function bulkAssignRenderIncidents(input: { actor: string; incident_keys: string[]; assigned_to: string; reason?: string; }): Promise<BulkIncidentActionResponse> { return bulkIncidentAction(`/render/dashboard/incidents/bulk/assign`, input); }
export async function bulkMuteRenderIncidents(input: { actor: string; incident_keys: string[]; muted_until?: string; reason?: string; }): Promise<BulkIncidentActionResponse> { return bulkIncidentAction(`/render/dashboard/incidents/bulk/mute`, input); }
export async function bulkResolveRenderIncidents(input: { actor: string; incident_keys: string[]; reason?: string; }): Promise<BulkIncidentActionResponse> { return bulkIncidentAction(`/render/dashboard/incidents/bulk/resolve`, input); }

export interface RenderAccessProfile { actor_id: string; role: string; team_id?: string | null; is_active: boolean; scopes: Record<string, unknown>; created_at: string; updated_at: string; }
export interface BulkAuditRun { id: string; action_type: string; actor: string; actor_role: string; actor_team_id?: string | null; mode: string; reason?: string | null; attempted: number; succeeded: number; failed: number; filters: Record<string, unknown>; request: Record<string, unknown>; created_at: string; }
export interface BulkAuditItem { incident_key: string; ok: boolean; status?: string | null; error?: string | null; payload: Record<string, unknown>; created_at: string; }
export interface BulkAuditListResponse { items: BulkAuditRun[]; }
export interface BulkAuditDetailResponse { run: BulkAuditRun; items: BulkAuditItem[]; }

export async function getRenderAccessProfile(actor: string): Promise<RenderAccessProfile> { return request<RenderAccessProfile>(`/render/dashboard/access-profile?actor=${encodeURIComponent(actor)}`, { method: "GET" }); }
export async function listBulkIncidentActionHistory(input: { actor: string; limit?: number }): Promise<BulkAuditListResponse> { const params = new URLSearchParams({ actor: input.actor }); if (input.limit) params.set("limit", String(input.limit)); return request<BulkAuditListResponse>(`/render/dashboard/incidents/bulk/history?${params.toString()}`, { method: "GET" }); }
export async function getBulkIncidentActionHistoryDetail(input: { actor: string; run_id: string }): Promise<BulkAuditDetailResponse> { return request<BulkAuditDetailResponse>(`/render/dashboard/incidents/bulk/history/${encodeURIComponent(input.run_id)}?actor=${encodeURIComponent(input.actor)}`, { method: "GET" }); }


export interface AccessProfileUpdateInput { role?: string; team_id?: string; is_active?: boolean; scopes?: Record<string, unknown>; }
export interface RenderAccessProfileListResponse { items: RenderAccessProfile[]; }
export interface ProductivityOperatorItem { actor: string; role?: string | null; team_id?: string | null; active_assigned: number; acknowledged_count: number; assigned_count: number; muted_count: number; resolved_count: number; reopened_count: number; note_updates: number; }
export interface ProductivityTeamItem { team_id: string; member_count: number; active_assigned: number; acknowledged_count: number; assigned_count: number; muted_count: number; resolved_count: number; reopened_count: number; note_updates: number; }
export interface ProductivityBoardResponse { days: number; operators: ProductivityOperatorItem[]; teams: ProductivityTeamItem[]; }

export async function listRenderAccessProfiles(input: { actor: string; team_only?: boolean }): Promise<RenderAccessProfileListResponse> {
  const params = new URLSearchParams({ actor: input.actor });
  if (input.team_only) params.set("team_only", "true");
  return request<RenderAccessProfileListResponse>(`/render/dashboard/access-profiles?${params.toString()}`, { method: "GET" });
}
export async function updateRenderAccessProfile(input: { actor: string; target_actor: string; role?: string; team_id?: string; is_active?: boolean; scopes?: Record<string, unknown>; }): Promise<RenderAccessProfile> {
  const { actor, target_actor, ...body } = input;
  return request<RenderAccessProfile>(`/render/dashboard/access-profiles/${encodeURIComponent(target_actor)}?actor=${encodeURIComponent(actor)}`, { method: "PUT", body: JSON.stringify(body) });
}
export async function getIncidentProductivityBoard(input: { actor: string; days?: number }): Promise<ProductivityBoardResponse> {
  const params = new URLSearchParams({ actor: input.actor });
  if (input.days) params.set("days", String(input.days));
  return request<ProductivityBoardResponse>(`/render/dashboard/incidents/productivity?${params.toString()}`, { method: "GET" });
}


export interface SavedViewEffectiveAccessEntry { actor_id: string; role?: string | null; team_id?: string | null; can_view: boolean; reason?: string | null; }
export interface SavedViewEffectiveAccessResponse { view_id: string; view_name: string; requester_actor: string; requester_role?: string | null; requester_team_id?: string | null; share_scope: string; owner_actor: string; shared_team_id?: string | null; allowed_roles: string[]; visible_to_count: number; entries: SavedViewEffectiveAccessEntry[]; }
export interface BulkGuardrailEvaluationResponse { ok: boolean; action_type: string; actor: string; actor_role?: string | null; actor_team_id?: string | null; policy: Record<string, unknown>; observed: Record<string, unknown>; blocked_reasons: string[]; warnings: string[]; }
export interface ProductivityTrendBucket { day: string; team_id: string; resolved_count: number; assigned_count: number; acknowledged_count: number; muted_count: number; }
export interface ProductivityTrendWindow { days: number; team_totals: ProductivityTeamItem[]; operator_totals: ProductivityOperatorItem[]; }
export interface ProductivityTrendsResponse { windows: ProductivityTrendWindow[]; daily_team_trends: ProductivityTrendBucket[]; }

export async function getIncidentSavedViewEffectiveAccess(input: { actor: string; view_id: string }): Promise<SavedViewEffectiveAccessResponse> { return request<SavedViewEffectiveAccessResponse>(`/render/dashboard/incidents/views/${encodeURIComponent(input.view_id)}/effective-access?actor=${encodeURIComponent(input.actor)}`, { method: "GET" }); }
export async function getBulkIncidentGuardrails(input: { action_type: "acknowledge" | "assign" | "mute" | "resolve"; actor: string; incident_keys: string[]; reason?: string; assigned_to?: string; muted_until?: string; }): Promise<BulkGuardrailEvaluationResponse> { const { action_type, ...body } = input; return request<BulkGuardrailEvaluationResponse>(`/render/dashboard/incidents/bulk/${action_type}/guardrails`, { method: "POST", body: JSON.stringify(body) }); }
export async function getIncidentProductivityTrends(input: { actor: string; windows?: number[] }): Promise<ProductivityTrendsResponse> { const params = new URLSearchParams({ actor: input.actor }); if (input.windows?.length) params.set("windows", input.windows.join(",")); return request<ProductivityTrendsResponse>(`/render/dashboard/incidents/productivity/trends?${params.toString()}`, { method: "GET" }); }


export interface MetricSample {
  name: string;
  value: number;
  labels?: Record<string, string>;
}

export interface ObservabilityStatusResponse {
  generated_at: string;
  metrics: MetricSample[];
  release_gate_blocked: boolean;
  global_kill_switch_enabled: boolean;
  active_provider_overrides: number;
  notification_failures_last_24h: number;
  autopilot_last_execution_at?: string | null;
}

export interface KillSwitchResponse {
  switch_name: string;
  enabled: boolean;
  reason?: string | null;
  updated_by?: string | null;
}

export interface NotificationEndpointResponse {
  name: string;
  channel_type: string;
  target: string;
  event_filter?: string | null;
  enabled: boolean;
  updated_by?: string | null;
}

export interface NotificationDeliveryLogResponse {
  id: string;
  event_type: string;
  endpoint_name: string;
  channel_type: string;
  delivery_status: string;
  payload_json?: string | null;
  response_text?: string | null;
  error_message?: string | null;
  created_at: string;
}

export interface AutopilotDashboardResponse {
  generated_at: string;
  kill_switch_enabled: boolean;
  release_gate_blocked: boolean;
  active_provider_overrides: number;
  worker_dispatch_batch_limit: number;
  worker_poll_countdown_seconds: number;
  autopilot_states: Record<string, number>;
  latest_decision_audits: Array<Record<string, unknown>>;
  latest_notification_deliveries: Array<Record<string, unknown>>;
}

export async function getObservabilityStatus(): Promise<ObservabilityStatusResponse> {
  return fetchJson<ObservabilityStatusResponse>(`/api/v1/observability/status`);
}

export async function getAutopilotDashboard(): Promise<AutopilotDashboardResponse> {
  return fetchJson<AutopilotDashboardResponse>(`/api/v1/observability/autopilot-dashboard`);
}

export async function getKillSwitch(): Promise<KillSwitchResponse> {
  return fetchJson<KillSwitchResponse>(`/api/v1/observability/kill-switch`);
}

export async function updateKillSwitch(payload: { actor: string; enabled: boolean; reason?: string | null }): Promise<KillSwitchResponse> {
  return fetchJson<KillSwitchResponse>(`/api/v1/observability/kill-switch`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listNotificationEndpoints(): Promise<NotificationEndpointResponse[]> {
  return fetchJson<NotificationEndpointResponse[]>(`/api/v1/observability/notification-endpoints`);
}

export async function upsertNotificationEndpoint(payload: { actor: string; name: string; channel_type: string; target: string; event_filter?: string; enabled?: boolean; secret?: string | null }): Promise<NotificationEndpointResponse> {
  return fetchJson<NotificationEndpointResponse>(`/api/v1/observability/notification-endpoints`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listNotificationDeliveries(limit = 50): Promise<NotificationDeliveryLogResponse[]> {
  return fetchJson<NotificationDeliveryLogResponse[]>(`/api/v1/observability/notification-deliveries?limit=${limit}`);
}


export interface VoiceProfile {
  id: string;
  display_name: string;
  provider: string;
  provider_voice_id?: string | null;
  clone_mode: string;
  consent_status: string;
  owner_user_id?: string | null;
  language_code?: string | null;
  is_active: boolean;
}

export interface VoiceProfileCreatePayload {
  display_name: string;
  clone_mode?: string;
  language_code?: string | null;
  provider_voice_id?: string | null;
  owner_user_id?: string | null;
  consent_text: string;
  consent_confirmed: boolean;
}

export interface NarrationSegment {
  id: string;
  narration_job_id: string;
  segment_index: number;
  text: string;
  pause_after_ms: number;
  estimated_duration_ms?: number | null;
  output_url?: string | null;
}

export interface NarrationJob {
  id: string;
  render_job_id?: string | null;
  voice_profile_id: string;
  status: string;
  style_preset: string;
  breath_pacing_preset: string;
  output_url?: string | null;
  duration_ms?: number | null;
  error_message?: string | null;
  segments: NarrationSegment[];
}

export interface MusicAsset {
  id: string;
  display_name: string;
  source_mode: string;
  provider?: string | null;
  prompt_text?: string | null;
  mood?: string | null;
  bpm?: number | null;
  public_url?: string | null;
}

export interface AudioRenderOutput {
  id: string;
  render_job_id?: string | null;
  narration_job_id?: string | null;
  music_asset_id?: string | null;
  mix_profile_id?: string | null;
  status: string;
  voice_track_url?: string | null;
  music_track_url?: string | null;
  mixed_audio_url?: string | null;
  final_muxed_video_url?: string | null;
  error_message?: string | null;
}

export async function listVoiceProfiles(): Promise<VoiceProfile[]> {
  return apiFetch("/audio/voice-profiles");
}

export async function createVoiceProfile(payload: VoiceProfileCreatePayload): Promise<VoiceProfile> {
  return apiFetch("/audio/voice-profiles", { method: "POST", body: JSON.stringify(payload) });
}

export async function createNarrationJob(payload: {
  voice_profile_id: string;
  render_job_id?: string | null;
  script_text: string;
  style_preset?: string;
  breath_pacing_preset?: string;
  provider?: string;
}): Promise<NarrationJob> {
  return apiFetch("/audio/narration-jobs", { method: "POST", body: JSON.stringify(payload) });
}

export async function listMusicAssets(): Promise<MusicAsset[]> {
  return apiFetch("/audio/music-assets");
}

export async function createMusicAsset(payload: {
  display_name: string;
  source_mode?: string;
  provider?: string | null;
  prompt_text?: string | null;
  mood?: string | null;
  bpm?: number | null;
  force_instrumental?: boolean;
  license_note?: string | null;
}): Promise<MusicAsset> {
  return apiFetch("/audio/music-assets", { method: "POST", body: JSON.stringify(payload) });
}

export async function createAudioMixJob(payload: {
  render_job_id?: string | null;
  narration_job_id: string;
  music_asset_id?: string | null;
  mix_profile_id?: string | null;
  mux_to_video?: boolean;
}): Promise<AudioRenderOutput> {
  return apiFetch("/audio/mix-jobs", { method: "POST", body: JSON.stringify(payload) });
}


export async function getProductionRuns() {
  return handle<{items: any[]}>(await fetch(`${API_BASE}/api/v1/dashboard/production-runs`, { cache: "no-store" }));
}


export async function getRenderJobTimeline(renderJobId: string) {
  return handle<any>(await fetch(`${API_BASE}/api/v1/render-jobs/${renderJobId}/timeline`, { cache: "no-store" }));
}


export async function createProductionEvent(payload: any) {
  return handle<any>(await fetch(`${API_BASE}/api/v1/production/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }));
}


export async function getStrategyState() {
  return handle<any>(await fetch(`${API_BASE}/api/v1/strategy/state`, { cache: "no-store" }));
}


export async function createStrategySignal(payload: any) {
  return handle<any>(await fetch(`${API_BASE}/api/v1/strategy/signals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }));
}


export async function activateStrategyMode(payload: any) {
  return handle<any>(await fetch(`${API_BASE}/api/v1/strategy/modes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }));
}


export async function getStrategyDirectives() {
  return handle<any>(await fetch(`${API_BASE}/api/v1/strategy/directives`, { cache: "no-store" }));
}


export async function getStrategyPortfolio() {
  return handle<any>(await fetch(`${API_BASE}/api/v1/strategy/portfolio`, { cache: "no-store" }));
}


export async function getStrategySlaRisk() {
  return handle<any>(await fetch(`${API_BASE}/api/v1/strategy/sla-risk`, { cache: "no-store" }));
}


export async function getStrategyBusinessOutcomes() {
  return handle<any>(await fetch(`${API_BASE}/api/v1/strategy/business-outcomes`, { cache: "no-store" }));
}



export async function getTemplates(status?: string): Promise<any> {
  const url = status ? `${API_BASE}/api/v1/templates?status=${encodeURIComponent(status)}` : `${API_BASE}/api/v1/templates`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load templates");
  return res.json();
}

export async function getTemplateDetail(templateId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates/${templateId}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load template detail");
  return res.json();
}

export async function createTemplate(payload: any): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to create template");
  return res.json();
}

export async function publishTemplate(templateId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates/${templateId}/publish`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to publish template");
  return res.json();
}

export async function archiveTemplate(templateId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates/${templateId}/archive`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to archive template");
  return res.json();
}

export async function extractTemplate(payload: any): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to queue extraction");
  return res.json();
}

export async function generateFromTemplate(templateId: string, payload: any): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates/${templateId}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to generate from template");
  return res.json();
}

export async function batchGenerateFromTemplate(templateId: string, payload: any): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates/${templateId}/batch-generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to queue template batch");
  return res.json();
}



export async function getProjects(): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/projects`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load projects");
  return res.json();
}

export async function getProject(projectId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load project");
  return res.json();
}

export async function triggerProjectRender(projectId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/render`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to trigger render");
  return res.json();
}

export async function getProjectRenderStatus(projectId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/render-status`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load render status");
  return res.json();
}

export async function getProjectRenderEvents(projectId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/render-events`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load render events");
  return res.json();
}

export async function retryProjectRender(projectId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/render/retry`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to retry render");
  return res.json();
}

export async function rerenderScene(projectId: string, sceneId: string | number): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/scenes/${sceneId}/rerender`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId }),
  });
  if (!res.ok) throw new Error("Failed to rerender scene");
  return res.json();
}

export async function getTemplatesRanked(limit = 20): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates/ranked?limit=${limit}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load ranked templates");
  return res.json();
}

export async function autoPickTemplate(payload: any): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates/auto-pick`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to auto-pick template");
  return res.json();
}

export async function processTemplateProjectFeedback(projectId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates/feedback/process-project`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_id: projectId }),
  });
  if (!res.ok) throw new Error("Failed to process template feedback");
  return res.json();
}



export async function getCharacterReferencePacks(): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/character-reference-packs`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load character reference packs");
  return res.json();
}

export async function createCharacterReferencePack(payload: any): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/character-reference-packs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to create character reference pack");
  return res.json();
}

export async function updateProjectVeoConfig(projectId: string, payload: any): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/veo-config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to update Veo config");
  return res.json();
}

export async function createVeoBatchRun(payload: any): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/veo/batch-runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to create Veo batch run");
  return res.json();
}

export async function getVeoBatchRun(batchId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/veo/batch-runs/${batchId}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load Veo batch run");
  return res.json();
}



export async function scheduleExecutionPlan(
  planId: string,
  payload: {
    scheduled_at?: string | null;
    execution_window_start?: string | null;
    execution_window_end?: string | null;
    allow_run_outside_window: boolean;
  }
): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates/governance/execution-plans/${planId}/schedule`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to schedule execution plan");
  return res.json();
}

export async function pauseExecutionPlan(
  planId: string,
  actorId: string,
  reason?: string
): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates/governance/execution-plans/${planId}/pause`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor_id: actorId, reason: reason || "" }),
  });
  if (!res.ok) throw new Error("Failed to pause execution plan");
  return res.json();
}

export async function resumeExecutionPlan(
  planId: string,
  actorId: string
): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates/governance/execution-plans/${planId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor_id: actorId }),
  });
  if (!res.ok) throw new Error("Failed to resume execution plan");
  return res.json();
}

export async function cancelExecutionPlan(
  planId: string,
  actorId: string,
  reason?: string
): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates/governance/execution-plans/${planId}/cancel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor_id: actorId, reason: reason || "" }),
  });
  if (!res.ok) throw new Error("Failed to cancel execution plan");
  return res.json();
}

export async function evaluateExecutionPlan(planId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates/governance/execution-plans/${planId}/evaluate`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to evaluate execution plan");
  return res.json();
}

export async function getExecutionPlanEvaluation(planId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates/governance/execution-plans/${planId}/evaluation`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load execution plan evaluation");
  return res.json();
}

export async function evaluateExecutionPlanPolicyPath(planId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates/governance/execution-plans/${planId}/policy-path/evaluate`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to evaluate execution plan policy path");
  return res.json();
}

export async function getExecutionPlanPolicyPath(planId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/templates/governance/execution-plans/${planId}/policy-path`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load execution plan policy path");
  return res.json();
}
