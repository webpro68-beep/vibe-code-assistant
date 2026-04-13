"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import DashboardShell from "@/src/components/DashboardShell";
import IncidentDrawer from "@/src/components/IncidentDrawer";
import ToastViewport, { type ToastItem, type ToastTone } from "@/src/components/ToastViewport";
import {
  acknowledgeRenderIncident,
  assignRenderIncident,
  bulkAcknowledgeRenderIncidents,
  bulkAssignRenderIncidents,
  bulkMuteRenderIncidents,
  bulkResolveRenderIncidents,
  getBulkIncidentActionHistoryDetail,
  getBulkIncidentGuardrails,
  getIncidentProductivityBoard,
  getIncidentProductivityTrends,
  getIncidentSavedViewEffectiveAccess,
  getRenderAccessProfile,
  listBulkIncidentActionHistory,
  listRenderAccessProfiles,
  createIncidentSavedView,
  deleteIncidentSavedView,
  getIncidentSegmentMetrics,
  getRecentRenderIncidents,
  getRenderDashboardSummary,
  getRenderIncidentHistory,
  listIncidentSavedViews,
  previewBulkIncidentAction,
  listRenderDashboardJobs,
  muteRenderIncident,
  reopenRenderIncident,
  resolveRenderIncident,
  updateRenderIncidentNote,
  updateIncidentSavedView,
  updateRenderAccessProfile,
  type IncidentActionLogItem,
  type IncidentHistoryResponse,
  type IncidentSavedView,
  type ProductivityBoardResponse,
  type RenderAccessProfile,
  type RenderAccessProfileListResponse,
  type IncidentSegmentMetricsResponse,
  type BulkAuditDetailResponse,
  type BulkAuditRun,
  type BulkGuardrailEvaluationResponse,
  type BulkPreviewResponse,
  type ProductivityTrendsResponse,
  type RecentIncidentItem,
  type SavedViewEffectiveAccessResponse,
  type RenderDashboardSummaryResponse,
  type RenderEventItem,
  type RenderJobListItem,
} from "@/src/lib/api";

const HEALTH_OPTIONS = ["all", "healthy", "degraded", "stalled", "failed", "completed", "queued"] as const;
const SEGMENT_OPTIONS = [
  { key: "active", label: "Active" },
  { key: "untriaged", label: "Untriaged" },
  { key: "assigned", label: "Assigned" },
  { key: "muted", label: "Muted" },
  { key: "resolved", label: "Resolved" },
  { key: "mine", label: "Mine" },
] as const;
const OPTIMISTIC_TTL_MS = 15000;

type IncidentActionName = "ack" | "assign" | "mute" | "resolve" | "reopen";
type BulkActionName = "ack" | "assign" | "mute" | "resolve";
type OptimisticPatch = { patch: Partial<RecentIncidentItem>; expiresAt: number };

function buildActionReason(action: IncidentActionName | BulkActionName, actionReason: string, noteDraft: string) {
  const trimmed = actionReason.trim();
  if (trimmed) return trimmed;
  const defaults: Record<string, string> = {
    ack: "Dashboard acknowledge",
    assign: "Dashboard assign",
    mute: "Dashboard mute",
    resolve: "Dashboard resolve",
    reopen: "Dashboard reopen",
  };
  const note = noteDraft.trim();
  return note ? `${defaults[action]} | note: ${note.slice(0, 300)}` : defaults[action];
}

function SummaryCard({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
      <p className="text-xs uppercase tracking-wide text-white/45">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
      {hint ? <p className="mt-2 text-xs text-white/45">{hint}</p> : null}
    </div>
  );
}

function SegmentButton({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return <button type="button" onClick={onClick} className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${active ? "border-sky-400/40 bg-sky-500/15 text-sky-100" : "border-white/10 bg-white/5 text-white/65 hover:bg-white/10"}`}>{label}</button>;
}

export default function RenderJobsDashboardPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const initialProvider = searchParams.get("provider") || "all";
  const initialHealth = searchParams.get("health") || "all";
  const initialSegment = searchParams.get("segment") || "active";
  const initialShowMuted = searchParams.get("show_muted") === "true";
  const selectedIncidentKey = searchParams.get("incident");
  const selectedViewId = searchParams.get("view");

  const [summary, setSummary] = useState<RenderDashboardSummaryResponse | null>(null);
  const [jobs, setJobs] = useState<RenderJobListItem[]>([]);
  const [incidents, setIncidents] = useState<RecentIncidentItem[]>([]);
  const [savedViews, setSavedViews] = useState<IncidentSavedView[]>([]);
  const [accessProfile, setAccessProfile] = useState<RenderAccessProfile | null>(null);
  const [bulkAuditRuns, setBulkAuditRuns] = useState<BulkAuditRun[]>([]);
  const [accessProfiles, setAccessProfiles] = useState<RenderAccessProfile[]>([]);
  const [productivity, setProductivity] = useState<ProductivityBoardResponse | null>(null);
  const [productivityTrends, setProductivityTrends] = useState<ProductivityTrendsResponse | null>(null);
  const [effectiveAccess, setEffectiveAccess] = useState<SavedViewEffectiveAccessResponse | null>(null);
  const [lastGuardrailCheck, setLastGuardrailCheck] = useState<BulkGuardrailEvaluationResponse | null>(null);
  const [bulkAuditDetail, setBulkAuditDetail] = useState<BulkAuditDetailResponse | null>(null);
  const [segmentMetrics, setSegmentMetrics] = useState<IncidentSegmentMetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [providerFilter, setProviderFilter] = useState(initialProvider);
  const [healthFilter, setHealthFilter] = useState(initialHealth);
  const [segment, setSegment] = useState(initialSegment);
  const [showMuted, setShowMuted] = useState(initialShowMuted);
  const [actor, setActor] = useState("operator@local");
  const [assignee, setAssignee] = useState("owner@local");
  const [actionReason, setActionReason] = useState("");
  const [noteDraft, setNoteDraft] = useState("");
  const [historyItems, setHistoryItems] = useState<RenderEventItem[]>([]);
  const [actionItems, setActionItems] = useState<IncidentActionLogItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [noteSaving, setNoteSaving] = useState(false);
  const [loadingAction, setLoadingAction] = useState<Record<string, IncidentActionName | null>>({});
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [saveViewName, setSaveViewName] = useState("");
  const [saveViewShared, setSaveViewShared] = useState(false);
  const [saveViewShareScope, setSaveViewShareScope] = useState("private");
  const [saveViewTeamId, setSaveViewTeamId] = useState("ops");
  const [saveViewAllowedRoles, setSaveViewAllowedRoles] = useState("team_lead,admin");
  const [aclTargetActor, setAclTargetActor] = useState("");
  const [aclRole, setAclRole] = useState("operator");
  const [aclTeamId, setAclTeamId] = useState("ops");
  const [aclActive, setAclActive] = useState(true);
  const [bulkLoading, setBulkLoading] = useState<BulkActionName | null>(null);
  const [previewLoading, setPreviewLoading] = useState<BulkActionName | null>(null);
  const [bulkPreview, setBulkPreview] = useState<BulkPreviewResponse | null>(null);
  const [editingViewId, setEditingViewId] = useState<string | null>(null);
  const [editViewName, setEditViewName] = useState("");
  const [editViewDescription, setEditViewDescription] = useState("");
  const [editViewShared, setEditViewShared] = useState(false);
  const [editViewShareScope, setEditViewShareScope] = useState("private");
  const [editViewTeamId, setEditViewTeamId] = useState("ops");
  const [editViewAllowedRoles, setEditViewAllowedRoles] = useState("team_lead,admin");
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const optimisticRef = useRef<Record<string, OptimisticPatch>>({});

  const pushToast = useCallback((title: string, description?: string, tone: ToastTone = "info") => {
    const id = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => [...prev, { id, title, description, tone }]);
  }, []);
  const dismissToast = useCallback((id: string) => setToasts((prev) => prev.filter((item) => item.id !== id)), []);

  const syncUrl = useCallback((next: { provider?: string; health?: string; segment?: string; show_muted?: boolean; incident?: string | null; view?: string | null }) => {
    const params = new URLSearchParams(searchParams.toString());
    const provider = next.provider ?? providerFilter;
    const health = next.health ?? healthFilter;
    const nextSegment = next.segment ?? segment;
    const muted = typeof next.show_muted === "boolean" ? next.show_muted : showMuted;
    const incident = next.incident === undefined ? selectedIncidentKey : next.incident;
    const view = next.view === undefined ? selectedViewId : next.view;
    provider !== "all" ? params.set("provider", provider) : params.delete("provider");
    health !== "all" ? params.set("health", health) : params.delete("health");
    nextSegment !== "active" ? params.set("segment", nextSegment) : params.delete("segment");
    muted ? params.set("show_muted", "true") : params.delete("show_muted");
    incident ? params.set("incident", incident) : params.delete("incident");
    view ? params.set("view", view) : params.delete("view");
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }, [healthFilter, pathname, providerFilter, router, searchParams, selectedIncidentKey, selectedViewId, segment, showMuted]);

  useEffect(() => {
    setProviderFilter(initialProvider);
    setHealthFilter(initialHealth);
    setShowMuted(initialShowMuted);
    setSegment(initialSegment);
  }, [initialHealth, initialProvider, initialSegment, initialShowMuted]);

  const cleanupOptimistic = useCallback(() => {
    const now = Date.now();
    optimisticRef.current = Object.fromEntries(Object.entries(optimisticRef.current).filter(([, value]) => value.expiresAt > now));
  }, []);

  const mergeIncidentsWithOptimistic = useCallback((items: RecentIncidentItem[]) => {
    cleanupOptimistic();
    return items.map((item) => {
      const optimistic = optimisticRef.current[item.incident_key];
      if (!optimistic) return item;
      const remoteMatches = Object.entries(optimistic.patch).every(([key, value]) => (item as unknown as Record<string, unknown>)[key] === value);
      if (remoteMatches) {
        delete optimisticRef.current[item.incident_key];
        return item;
      }
      return { ...item, ...optimistic.patch };
    });
  }, [cleanupOptimistic]);

  const loadAccessProfiles = useCallback(async () => {
    try {
      const response: RenderAccessProfileListResponse = await listRenderAccessProfiles({ actor, team_only: accessProfile?.role !== "admin" });
      setAccessProfiles(response.items || []);
      if (!aclTargetActor && response.items?.length) {
        const first = response.items[0];
        setAclTargetActor(first.actor_id);
        setAclRole(first.role);
        setAclTeamId(first.team_id || "ops");
        setAclActive(first.is_active);
      }
    } catch (err) {
      pushToast("Access profiles load failed", err instanceof Error ? err.message : "Unknown error", "error");
    }
  }, [accessProfile?.role, aclTargetActor, actor, pushToast]);

  const loadProductivity = useCallback(async () => {
    try {
      const [response, trendResponse] = await Promise.all([
        getIncidentProductivityBoard({ actor, days: 7 }),
        getIncidentProductivityTrends({ actor, windows: [1, 7, 14] }),
      ]);
      setProductivity(response);
      setProductivityTrends(trendResponse);
    } catch (err) {
      pushToast("Productivity board load failed", err instanceof Error ? err.message : "Unknown error", "error");
    }
  }, [actor, pushToast]);

  const loadSavedViews = useCallback(async () => {
    try {
      const response = await listIncidentSavedViews(actor);
      setSavedViews(response.items || []);
    } catch (err) {
      pushToast("Saved views load failed", err instanceof Error ? err.message : "Unknown error", "error");
    }
  }, [actor, pushToast]);

  const loadEffectiveAccess = useCallback(async (viewId: string) => {
    try {
      const response = await getIncidentSavedViewEffectiveAccess({ actor, view_id: viewId });
      setEffectiveAccess(response);
    } catch (err) {
      setEffectiveAccess(null);
      pushToast("Effective access preview failed", err instanceof Error ? err.message : "Unknown error", "error");
    }
  }, [actor, pushToast]);


  const loadAccessProfile = useCallback(async () => {
    try {
      const response = await getRenderAccessProfile(actor);
      setAccessProfile(response);
    } catch (err) {
      pushToast("Access profile load failed", err instanceof Error ? err.message : "Unknown error", "error");
    }
  }, [actor, pushToast]);

  const loadBulkAuditRuns = useCallback(async () => {
    try {
      const response = await listBulkIncidentActionHistory({ actor, limit: 20 });
      setBulkAuditRuns(response.items || []);
    } catch (err) {
      pushToast("Bulk audit load failed", err instanceof Error ? err.message : "Unknown error", "error");
    }
  }, [actor, pushToast]);

  const loadDashboard = useCallback(async (mode: "initial" | "refresh" = "refresh") => {
    mode === "initial" ? setLoading(true) : setRefreshing(true);
    try {
      const [summaryData, jobsData, incidentData, metricsData] = await Promise.all([
        getRenderDashboardSummary(),
        listRenderDashboardJobs({ limit: 100, provider: providerFilter === "all" ? undefined : providerFilter, health_status: healthFilter === "all" ? undefined : healthFilter }),
        getRecentRenderIncidents({ limit: 50, provider: providerFilter === "all" ? undefined : providerFilter, show_muted: showMuted, segment, assigned_to: segment === "mine" ? assignee : undefined }),
        getIncidentSegmentMetrics({ provider: providerFilter === "all" ? undefined : providerFilter, show_muted: showMuted, assignee }),
      ]);
      setSummary(summaryData);
      setJobs(jobsData.items || []);
      setIncidents(mergeIncidentsWithOptimistic(incidentData.items || []));
      setSegmentMetrics(metricsData);
      setSelectedKeys((prev) => prev.filter((key) => incidentData.items?.some((item) => item.incident_key === key)));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
      if (mode === "refresh") pushToast("Dashboard refresh failed", err instanceof Error ? err.message : "Unknown error", "error");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [assignee, healthFilter, mergeIncidentsWithOptimistic, providerFilter, pushToast, segment, showMuted]);

  useEffect(() => { void loadSavedViews(); }, [loadSavedViews]);
  useEffect(() => { if (selectedViewId) { void loadEffectiveAccess(selectedViewId); } else { setEffectiveAccess(null); } }, [loadEffectiveAccess, selectedViewId]);
  useEffect(() => { void loadAccessProfile(); }, [loadAccessProfile]);
  useEffect(() => { if (accessProfile) void loadAccessProfiles(); }, [accessProfile, loadAccessProfiles]);
  useEffect(() => { if (accessProfile?.role === "team_lead" || accessProfile?.role === "admin") void loadProductivity(); }, [accessProfile, loadProductivity]);

  useEffect(() => {
    let active = true;
    let timer: number | null = null;
    const loop = async (mode: "initial" | "refresh") => {
      await loadDashboard(mode);
      if (!active) return;
      timer = window.setTimeout(() => void loop("refresh"), 7000);
    };
    void loop("initial");
    return () => { active = false; if (timer) window.clearTimeout(timer); };
  }, [loadDashboard]);

  const selectedIncident = useMemo(() => incidents.find((item) => item.incident_key === selectedIncidentKey) || null, [incidents, selectedIncidentKey]);

  const loadIncidentDetail = useCallback(async (incidentKey: string) => {
    setHistoryLoading(true);
    try {
      const detail: IncidentHistoryResponse = await getRenderIncidentHistory(incidentKey);
      setHistoryItems(detail.projected_timeline || detail.timeline_events || []);
      setActionItems(detail.actions || []);
      setNoteDraft(detail.incident.note || "");
      setError(null);
    } catch (err) {
      setHistoryItems([]); setActionItems([]); setNoteDraft("");
      pushToast("Incident history load failed", err instanceof Error ? err.message : "Unknown error", "error");
    } finally {
      setHistoryLoading(false);
    }
  }, [pushToast]);

  useEffect(() => {
    if (!selectedIncidentKey) {
      setHistoryItems([]); setActionItems([]); setNoteDraft(""); setActionReason("");
      return;
    }
    void loadIncidentDetail(selectedIncidentKey);
    setActionReason("");
  }, [loadIncidentDetail, selectedIncidentKey]);

  const providerOptions = useMemo(() => {
    const providers = new Set<string>();
    summary?.counts_by_provider?.forEach((i) => providers.add(i.provider));
    jobs.forEach((j) => providers.add(j.provider));
    return ["all", ...Array.from(providers)];
  }, [jobs, summary]);

  const applyOptimisticPatch = useCallback((incidentKey: string, patch: Partial<RecentIncidentItem>) => {
    optimisticRef.current[incidentKey] = { patch, expiresAt: Date.now() + OPTIMISTIC_TTL_MS };
    setIncidents((prev) => prev.map((item) => item.incident_key === incidentKey ? { ...item, ...patch } : item));
  }, []);

  const saveIncidentNote = useCallback(async () => {
    if (!selectedIncidentKey) return;
    setNoteSaving(true);
    try {
      await updateRenderIncidentNote({ incident_key: selectedIncidentKey, actor, note: noteDraft });
      await loadIncidentDetail(selectedIncidentKey);
      pushToast("Incident note saved", selectedIncidentKey, "success");
    } catch (err) {
      pushToast("Incident note save failed", err instanceof Error ? err.message : "Unknown error", "error");
    } finally {
      setNoteSaving(false);
    }
  }, [actor, loadIncidentDetail, noteDraft, pushToast, selectedIncidentKey]);

  const handleIncidentAction = useCallback(async (incident: RecentIncidentItem, action: IncidentActionName) => {
    const incidentKey = incident.incident_key;
    const reason = buildActionReason(action, actionReason, noteDraft);
    const previousIncident = incident;
    setLoadingAction((prev) => ({ ...prev, [incidentKey]: action }));
    try {
      const normalizedAction = action === "ack" ? "acknowledge" : action === "reopen" ? "resolve" : action;
      const guardrails = await getBulkIncidentGuardrails({
        action_type: normalizedAction,
        actor,
        incident_keys: selectedKeys,
        assigned_to: action === "assign" ? assignee : undefined,
        muted_until: action === "mute" ? new Date(Date.now() + 3600_000).toISOString() : undefined,
        reason,
      });
      setLastGuardrailCheck(guardrails);
      if (!guardrails.ok) {
        pushToast("Bulk action blocked", guardrails.blocked_reasons.join(", "), "error");
        return;
      }
      if (action === "ack") {
        applyOptimisticPatch(incidentKey, { acknowledged: true, workflow_status: "acknowledged", current_status: "acknowledged", current_reason: reason });
        await acknowledgeRenderIncident({ incident_key: incidentKey, actor, reason });
      } else if (action === "assign") {
        applyOptimisticPatch(incidentKey, { assigned_to: assignee, workflow_status: "assigned", current_status: "assigned", current_reason: reason });
        await assignRenderIncident({ incident_key: incidentKey, actor, assigned_to: assignee, reason });
      } else if (action === "mute") {
        applyOptimisticPatch(incidentKey, { muted: true, workflow_status: "muted", current_status: "muted", current_reason: reason });
        await muteRenderIncident({ incident_key: incidentKey, actor, muted_until: new Date(Date.now() + 3600_000).toISOString(), reason });
      } else if (action === "resolve") {
        applyOptimisticPatch(incidentKey, { workflow_status: "resolved", current_status: "resolved", current_reason: reason });
        await resolveRenderIncident({ incident_key: incidentKey, actor, reason });
      } else if (action === "reopen") {
        applyOptimisticPatch(incidentKey, { muted: false, workflow_status: "open", current_status: "open", current_reason: reason });
        await reopenRenderIncident({ incident_key: incidentKey, actor, reason });
      }
      await loadDashboard("refresh");
      await loadIncidentDetail(incidentKey);
      pushToast(`Incident ${action} complete`, incidentKey, "success");
    } catch (err) {
      delete optimisticRef.current[incidentKey];
      setIncidents((prev) => prev.map((item) => item.incident_key === incidentKey ? previousIncident : item));
      pushToast("Incident action failed", err instanceof Error ? err.message : `Failed to ${action} incident`, "error");
    } finally {
      setLoadingAction((prev) => ({ ...prev, [incidentKey]: null }));
    }
  }, [actionReason, actor, applyOptimisticPatch, assignee, loadDashboard, loadIncidentDetail, noteDraft, pushToast]);

  const selectedCount = selectedKeys.length;
  const toggleSelect = useCallback((incidentKey: string) => {
    setSelectedKeys((prev) => prev.includes(incidentKey) ? prev.filter((key) => key !== incidentKey) : [...prev, incidentKey]);
  }, []);
  const toggleSelectAll = useCallback(() => {
    setSelectedKeys((prev) => prev.length === incidents.length ? [] : incidents.map((item) => item.incident_key));
  }, [incidents]);

  const runBulkAction = useCallback(async (action: BulkActionName) => {
    if (!selectedKeys.length) return;
    setBulkLoading(action);
    const reason = buildActionReason(action, actionReason, noteDraft);
    try {
      if (action === "ack") {
        selectedKeys.forEach((key) => applyOptimisticPatch(key, { acknowledged: true, workflow_status: "acknowledged", current_status: "acknowledged", current_reason: reason }));
        await bulkAcknowledgeRenderIncidents({ actor, incident_keys: selectedKeys, reason });
      } else if (action === "assign") {
        selectedKeys.forEach((key) => applyOptimisticPatch(key, { assigned_to: assignee, workflow_status: "assigned", current_status: "assigned", current_reason: reason }));
        await bulkAssignRenderIncidents({ actor, incident_keys: selectedKeys, assigned_to: assignee, reason });
      } else if (action === "mute") {
        selectedKeys.forEach((key) => applyOptimisticPatch(key, { muted: true, workflow_status: "muted", current_status: "muted", current_reason: reason }));
        await bulkMuteRenderIncidents({ actor, incident_keys: selectedKeys, muted_until: new Date(Date.now() + 3600_000).toISOString(), reason });
      } else if (action === "resolve") {
        selectedKeys.forEach((key) => applyOptimisticPatch(key, { workflow_status: "resolved", current_status: "resolved", current_reason: reason }));
        await bulkResolveRenderIncidents({ actor, incident_keys: selectedKeys, reason });
      }
      setSelectedKeys([]);
      await loadDashboard("refresh");
      await loadBulkAuditRuns();
      pushToast("Bulk action completed", `${action} → ${selectedCount} incidents`, "success");
    } catch (err) {
      pushToast("Bulk action failed", err instanceof Error ? err.message : "Unknown error", "error");
      await loadDashboard("refresh");
    } finally {
      setBulkLoading(null);
    }
  }, [actionReason, actor, applyOptimisticPatch, assignee, loadDashboard, noteDraft, pushToast, selectedCount, selectedKeys]);

  const currentFilters = useMemo(() => ({
    provider: providerFilter === "all" ? undefined : providerFilter,
    workflow_status: healthFilter === "all" ? undefined : healthFilter,
    assigned_to: segment === "mine" ? assignee : undefined,
    segment,
    show_muted: showMuted,
    limit: 50,
  }), [assignee, healthFilter, providerFilter, segment, showMuted]);

  const runBulkPreview = useCallback(async (action: BulkActionName) => {
    if (!selectedKeys.length) return;
    setPreviewLoading(action);
    try {
      const preview = await previewBulkIncidentAction({
        action_type: action === "ack" ? "acknowledge" : action,
        actor,
        incident_keys: selectedKeys,
        assigned_to: action === "assign" ? assignee : undefined,
        muted_until: action === "mute" ? new Date(Date.now() + 3600_000).toISOString() : undefined,
        reason: buildActionReason(action, actionReason, noteDraft),
      });
      setBulkPreview(preview);
      setLastGuardrailCheck((preview as any).guardrails || null);
      pushToast("Bulk preview ready", `${preview.eligible}/${preview.attempted} eligible`, (preview as any).guardrails?.ok === false ? "info" : "success");
    } catch (err) {
      pushToast("Bulk preview failed", err instanceof Error ? err.message : "Unknown error", "error");
    } finally {
      setPreviewLoading(null);
    }
  }, [actionReason, actor, assignee, noteDraft, pushToast, selectedKeys]);

  const startEditView = useCallback((view: IncidentSavedView) => {
    setEditingViewId(view.id);
    setEditViewName(view.name);
    setEditViewDescription(view.description || "");
    setEditViewShared(view.is_shared);
    setEditViewShareScope((view as any).share_scope || "private");
    setEditViewTeamId((view as any).shared_team_id || "ops");
    setEditViewAllowedRoles(((view as any).allowed_roles || []).join(","));
  }, []);

  const handleUpdateView = useCallback(async () => {
    if (!editingViewId) return;
    try {
      await updateIncidentSavedView({
        view_id: editingViewId,
        actor,
        name: editViewName.trim() || undefined,
        description: editViewDescription.trim() || undefined,
        is_shared: editViewShared,
        share_scope: editViewShareScope as any,
        shared_team_id: editViewShareScope === "team" ? editViewTeamId : undefined,
        allowed_roles: editViewShareScope === "role" ? editViewAllowedRoles.split(",").map((item) => item.trim()).filter(Boolean) : [],
        filters: currentFilters,
      });
      await loadSavedViews();
      pushToast("Saved view updated", editViewName || editingViewId, "success");
      setEditingViewId(null);
    } catch (err) {
      pushToast("Saved view update failed", err instanceof Error ? err.message : "Unknown error", "error");
    }
  }, [actor, currentFilters, editViewDescription, editViewName, editViewShared, editingViewId, loadSavedViews, pushToast]);

  const handleSaveCurrentView = useCallback(async () => {
    if (!saveViewName.trim()) {
      pushToast("Saved view name required", "Enter a name before saving", "error");
      return;
    }
    try {
      await createIncidentSavedView({ owner_actor: actor, name: saveViewName.trim(), is_shared: saveViewShared, share_scope: saveViewShareScope as any, shared_team_id: saveViewShareScope === "team" ? saveViewTeamId : undefined, allowed_roles: saveViewShareScope === "role" ? saveViewAllowedRoles.split(",").map((item) => item.trim()).filter(Boolean) : [], filters: currentFilters });
      setSaveViewName("");
      setSaveViewShared(false);
      setSaveViewShareScope("private");
      await loadSavedViews();
      pushToast("Saved view created", undefined, "success");
    } catch (err) {
      pushToast("Save view failed", err instanceof Error ? err.message : "Unknown error", "error");
    }
  }, [actor, currentFilters, loadSavedViews, pushToast, saveViewName, saveViewShared]);

  const applySavedView = useCallback((view: IncidentSavedView) => {
    const filters = view.filters || {};
    setProviderFilter(filters.provider || "all");
    setHealthFilter(filters.workflow_status || "all");
    setSegment(filters.segment || "active");
    setShowMuted(Boolean(filters.show_muted));
    syncUrl({ provider: filters.provider || "all", health: filters.workflow_status || "all", segment: filters.segment || "active", show_muted: Boolean(filters.show_muted), view: view.id, incident: null });
  }, [syncUrl]);

  const openBulkAuditRun = useCallback(async (runId: string) => {
    try {
      const detail = await getBulkIncidentActionHistoryDetail({ actor, run_id: runId });
      setBulkAuditDetail(detail);
    } catch (err) {
      pushToast("Bulk audit detail failed", err instanceof Error ? err.message : "Unknown error", "error");
    }
  }, [actor, pushToast]);

  const activeView = useMemo(() => savedViews.find((item) => item.id === selectedViewId) || null, [savedViews, selectedViewId]);
  const visibleEffectiveEntries = useMemo(() => (effectiveAccess?.entries || []).filter((item) => item.can_view).slice(0, 8), [effectiveAccess]);
  const selectedAclProfile = useMemo(() => accessProfiles.find((item) => item.actor_id === aclTargetActor) || null, [accessProfiles, aclTargetActor]);

  const saveAclProfile = useCallback(async () => {
    if (!aclTargetActor) return;
    try {
      await updateRenderAccessProfile({ actor, target_actor: aclTargetActor, role: aclRole, team_id: aclTeamId, is_active: aclActive });
      await loadAccessProfiles();
      await loadProductivity();
      pushToast("Access profile updated", aclTargetActor, "success");
    } catch (err) {
      pushToast("Access profile update failed", err instanceof Error ? err.message : "Unknown error", "error");
    }
  }, [aclActive, aclRole, aclTargetActor, aclTeamId, actor, loadAccessProfiles, loadProductivity, pushToast]);

  return (
    <>
      <ToastViewport items={toasts} onDismiss={dismissToast} />
      <DashboardShell
        eyebrow="Render Dashboard"
        title="Incident work surface"
        description="Segment incidents, save reusable views, and run bulk actions without leaving the dashboard. This upgrades the panel into an operator/team-lead work surface on top of the new incident workflow routes."
        aside={<IncidentDrawer incident={selectedIncident} actor={actor} assignee={assignee} actionReason={actionReason} noteDraft={noteDraft} historyItems={historyItems} actionItems={actionItems} historyLoading={historyLoading} noteSaving={noteSaving} onActorChange={setActor} onAssigneeChange={setAssignee} onActionReasonChange={setActionReason} onNoteDraftChange={setNoteDraft} onSaveNote={() => void saveIncidentNote()} onClose={() => syncUrl({ incident: null })} onAcknowledge={() => selectedIncident && void handleIncidentAction(selectedIncident, "ack")} onAssign={() => selectedIncident && void handleIncidentAction(selectedIncident, "assign")} onMute={() => selectedIncident && void handleIncidentAction(selectedIncident, "mute")} onResolve={() => selectedIncident && void handleIncidentAction(selectedIncident, "resolve")} onReopen={() => selectedIncident && void handleIncidentAction(selectedIncident, "reopen")} loadingAction={selectedIncident ? loadingAction[selectedIncident.incident_key] : null} />}
      >
        <section className="grid gap-4 md:grid-cols-4">
          <SummaryCard label="Total jobs" value={summary?.total_jobs ?? "—"} hint="Persisted render_jobs snapshot" />
          <SummaryCard label="Healthy" value={summary?.healthy_jobs ?? "—"} hint="Healthy jobs right now" />
          <SummaryCard label="Degraded / stalled" value={`${summary?.degraded_jobs ?? 0} / ${summary?.stalled_jobs ?? 0}`} hint="At-risk jobs" />
          <SummaryCard label="Active scenes" value={summary?.total_active_scenes ?? "—"} hint="Processing scenes across jobs" />
        </section>

        <section className="rounded-3xl border border-white/10 bg-white/5 p-5 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {SEGMENT_OPTIONS.map((item) => <SegmentButton key={item.key} active={segment === item.key} label={item.label} onClick={() => { setSegment(item.key); syncUrl({ segment: item.key, incident: null, view: null }); }} />)}
          </div>
          <div className="grid gap-3 md:grid-cols-4">
            <label className="space-y-2 text-sm"><span className="text-white/60">Provider</span><select value={providerFilter} onChange={(e) => { setProviderFilter(e.target.value); syncUrl({ provider: e.target.value, view: null }); }} className="w-full rounded-2xl border border-white/10 bg-black/30 px-3 py-2 text-white">{providerOptions.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
            <label className="space-y-2 text-sm"><span className="text-white/60">Health filter</span><select value={healthFilter} onChange={(e) => { setHealthFilter(e.target.value); syncUrl({ health: e.target.value, view: null }); }} className="w-full rounded-2xl border border-white/10 bg-black/30 px-3 py-2 text-white">{HEALTH_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
            <label className="space-y-2 text-sm"><span className="text-white/60">Actor</span><input data-testid="dashboard-actor-input" value={actor} onChange={(e) => setActor(e.target.value)} className="w-full rounded-2xl border border-white/10 bg-black/30 px-3 py-2 text-white" /></label>
            <label className="space-y-2 text-sm"><span className="text-white/60">Assignee</span><input data-testid="dashboard-assignee-input" value={assignee} onChange={(e) => setAssignee(e.target.value)} className="w-full rounded-2xl border border-white/10 bg-black/30 px-3 py-2 text-white" /></label>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm text-white/70">
            <label className="inline-flex items-center gap-2"><input type="checkbox" checked={showMuted} onChange={(e) => { setShowMuted(e.target.checked); syncUrl({ show_muted: e.target.checked, view: null }); }} />Show muted</label>
            <button type="button" onClick={() => void loadDashboard("refresh")} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold hover:bg-white/10">{refreshing ? "Refreshing…" : "Refresh now"}</button>
            <button type="button" onClick={() => { setProviderFilter("all"); setHealthFilter("all"); setSegment("active"); setShowMuted(false); syncUrl({ provider: "all", health: "all", segment: "active", show_muted: false, view: null, incident: null }); }} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold hover:bg-white/10">Clear filters</button>
            {activeView ? <span className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-100">View: {activeView.name}</span> : null}
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-3xl border border-white/10 bg-white/5 p-5 space-y-4">
            <div>
              <p className="text-sm font-semibold text-white">Team-scoped saved view ACL editor</p>
              <p className="mt-1 text-xs text-white/45">Team leads and admins can adjust who owns scope on shared work surfaces.</p>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="space-y-1 text-xs text-white/55"><span>Target actor</span><select value={aclTargetActor} onChange={(e) => { const next = e.target.value; setAclTargetActor(next); const found = accessProfiles.find((item) => item.actor_id === next); if (found) { setAclRole(found.role); setAclTeamId(found.team_id || "ops"); setAclActive(found.is_active); } }} className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-white">{accessProfiles.map((item) => <option key={item.actor_id} value={item.actor_id}>{item.actor_id}</option>)}</select></label>
              <label className="space-y-1 text-xs text-white/55"><span>Role</span><select value={aclRole} onChange={(e) => setAclRole(e.target.value)} className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-white"><option value="viewer">viewer</option><option value="operator">operator</option><option value="team_lead">team_lead</option><option value="admin">admin</option></select></label>
              <label className="space-y-1 text-xs text-white/55"><span>Team</span><input value={aclTeamId} onChange={(e) => setAclTeamId(e.target.value)} className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-white" /></label>
              <label className="inline-flex items-center gap-2 text-xs text-white/60 self-end"><input type="checkbox" checked={aclActive} onChange={(e) => setAclActive(e.target.checked)} />Profile active</label>
            </div>
            <div className="flex items-center gap-2"><button data-testid="acl-update-button" type="button" onClick={() => void saveAclProfile()} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white hover:bg-white/10">Update ACL</button><button type="button" onClick={() => void loadAccessProfiles()} className="rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-xs text-white/70">Refresh team</button></div>
            <div className="max-h-56 space-y-2 overflow-auto pr-1">{accessProfiles.map((item) => <button key={item.actor_id} type="button" onClick={() => { setAclTargetActor(item.actor_id); setAclRole(item.role); setAclTeamId(item.team_id || "ops"); setAclActive(item.is_active); }} className={`w-full rounded-2xl border p-3 text-left ${aclTargetActor === item.actor_id ? "border-sky-400/30 bg-sky-500/10" : "border-white/10 bg-black/20"}`}><div className="flex items-center justify-between gap-2"><span className="text-sm font-semibold text-white">{item.actor_id}</span><span className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-white/65">{item.role}</span></div><p className="mt-1 text-xs text-white/45">team: {item.team_id || "—"} · active: {String(item.is_active)}</p></button>)}</div>
          </div>
          <div data-testid="productivity-board" className="rounded-3xl border border-white/10 bg-white/5 p-5 space-y-4">
            <div className="flex items-center justify-between gap-3"><div><p className="text-sm font-semibold text-white">Operator / team productivity board</p><p className="mt-1 text-xs text-white/45">Resolved, assigned, muted, reopened, note-updated, and active assigned counts over the last {productivity?.days || 7} days.</p></div><button data-testid="productivity-refresh-button" type="button" onClick={() => void loadProductivity()} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white hover:bg-white/10">Refresh board</button></div>
            <div className="grid gap-4 lg:grid-cols-2">
              <div data-testid="productivity-teams" className="rounded-2xl border border-white/10 bg-black/20 p-4"><p className="text-xs uppercase tracking-wide text-white/40">Teams</p><div className="mt-3 space-y-2">{(productivity?.teams || []).map((team) => <div key={team.team_id} className="rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-white/70"><div className="flex items-center justify-between gap-2"><span className="font-semibold text-white/85">{team.team_id}</span><span>{team.member_count} members</span></div><div className="mt-2 grid grid-cols-2 gap-2"><span>resolved {team.resolved_count}</span><span>assigned {team.assigned_count}</span><span>ack {team.acknowledged_count}</span><span>active {team.active_assigned}</span></div></div>)}{!(productivity?.teams || []).length ? <p className="text-sm text-white/45">No productivity data yet.</p> : null}</div></div>
              <div data-testid="productivity-operators" className="rounded-2xl border border-white/10 bg-black/20 p-4"><p className="text-xs uppercase tracking-wide text-white/40">Operators</p><div className="mt-3 max-h-72 space-y-2 overflow-auto pr-1">{(productivity?.operators || []).map((op) => <div key={op.actor} className="rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-white/70"><div className="flex items-center justify-between gap-2"><span className="font-semibold text-white/85">{op.actor}</span><span>{op.role || "—"}</span></div><p className="mt-1 text-white/45">team: {op.team_id || "—"}</p><div className="mt-2 grid grid-cols-2 gap-2"><span>resolved {op.resolved_count}</span><span>assigned {op.assigned_count}</span><span>ack {op.acknowledged_count}</span><span>active {op.active_assigned}</span><span>reopen {op.reopened_count}</span><span>notes {op.note_updates}</span></div></div>)}{!(productivity?.operators || []).length ? <p className="text-sm text-white/45">No operator productivity data yet.</p> : null}</div></div>
            </div>
            <div data-testid="productivity-trends" className="rounded-2xl border border-white/10 bg-black/20 p-4"><div className="flex items-center justify-between gap-3"><p className="text-xs uppercase tracking-wide text-white/40">Trend windows</p><span className="text-[11px] text-white/45">1 / 7 / 14 day windows</span></div><div className="mt-3 grid gap-3 md:grid-cols-3">{(productivityTrends?.windows || []).map((windowItem) => <div key={windowItem.days} className="rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-white/70"><div className="flex items-center justify-between gap-2"><span className="font-semibold text-white/85">{windowItem.days}d</span><span>{windowItem.team_totals.length} teams</span></div><div className="mt-2 space-y-1">{windowItem.team_totals.slice(0, 3).map((team) => <div key={`${windowItem.days}_${team.team_id}`} className="flex items-center justify-between gap-2"><span>{team.team_id}</span><span>resolved {team.resolved_count}</span></div>)}{!windowItem.team_totals.length ? <p className="text-white/45">No data</p> : null}</div></div>)}</div><div className="mt-3 max-h-40 space-y-2 overflow-auto pr-1">{(productivityTrends?.daily_team_trends || []).slice(-12).map((item) => <div key={`${item.day}_${item.team_id}`} className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/70"><span>{item.day} · {item.team_id}</span><span>resolved {item.resolved_count} · assigned {item.assigned_count}</span></div>)}{!(productivityTrends?.daily_team_trends || []).length ? <p className="text-sm text-white/45">No trend data yet.</p> : null}</div></div>
          </div>
        </section>

        <section className="rounded-3xl border border-white/10 bg-white/5 p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-white">Queue metrics by segment</p>
              <p className="mt-1 text-xs text-white/45">Fast workload signal for team leads before they open bulk actions or change views.</p>
            </div>
            <span className="text-xs text-white/40">{segmentMetrics?.generated_at ? new Date(segmentMetrics.generated_at).toLocaleTimeString() : "—"}</span>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {(segmentMetrics?.items || []).map((item) => (
              <div key={item.segment} className={`rounded-2xl border p-4 ${segment === item.segment ? "border-sky-400/30 bg-sky-500/10" : "border-white/10 bg-black/20"}`}>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-white capitalize">{item.segment}</p>
                  <button type="button" onClick={() => { setSegment(item.segment); syncUrl({ segment: item.segment, view: null }); }} className="rounded-xl border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-white/70 hover:bg-white/10">Open</button>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-white/65">
                  <span>Total: {item.total}</span>
                  <span>Unack: {item.unacknowledged}</span>
                  <span>Assigned: {item.assigned}</span>
                  <span>Muted: {item.muted}</span>
                  <span>Resolved: {item.resolved}</span>
                  <span>High sev: {item.high_severity}</span>
                </div>
                <p className="mt-3 text-[11px] text-white/40">Stale &gt; 30m: {item.stale_over_30m}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-3xl border border-white/10 bg-white/5 p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">Incident inbox</p>
                <p className="mt-1 text-xs text-white/45">Segmented recent incidents with bulk actions and drawer-based workflow.</p>
              </div>
              <label className="inline-flex items-center gap-2 text-xs text-white/55"><input type="checkbox" checked={incidents.length > 0 && selectedKeys.length === incidents.length} onChange={() => toggleSelectAll()} />Select page</label>
            </div>
            {selectedCount ? <div className="rounded-2xl border border-sky-500/25 bg-sky-500/10 p-3 space-y-3"><div data-testid="bulk-actions-panel" className="flex flex-wrap items-center gap-2"><span data-testid="bulk-selected-count" className="text-sm font-semibold text-sky-100">{selectedCount} selected</span><button type="button" data-testid="bulk-preview-ack-button" onClick={() => void runBulkPreview("ack")} disabled={!!previewLoading || !!bulkLoading} className="rounded-xl border border-white/10 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/10 disabled:opacity-60">{previewLoading === "ack" ? "Previewing…" : "Preview ack"}</button><button type="button" onClick={() => void runBulkPreview("assign")} disabled={!!previewLoading || !!bulkLoading} className="rounded-xl border border-white/10 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/10 disabled:opacity-60">{previewLoading === "assign" ? "Previewing…" : "Preview assign"}</button><button type="button" onClick={() => void runBulkPreview("mute")} disabled={!!previewLoading || !!bulkLoading} className="rounded-xl border border-white/10 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/10 disabled:opacity-60">{previewLoading === "mute" ? "Previewing…" : "Preview mute"}</button><button type="button" data-testid="bulk-preview-resolve-button" onClick={() => void runBulkPreview("resolve")} disabled={!!previewLoading || !!bulkLoading} className="rounded-xl border border-white/10 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/10 disabled:opacity-60">{previewLoading === "resolve" ? "Previewing…" : "Preview resolve"}</button><button type="button" data-testid="bulk-ack-button" onClick={() => void runBulkAction("ack")} disabled={!!bulkLoading || !!previewLoading} className="rounded-xl border border-white/10 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/10 disabled:opacity-60">{bulkLoading === "ack" ? "Working…" : "Bulk ack"}</button><button type="button" onClick={() => void runBulkAction("assign")} disabled={!!bulkLoading || !!previewLoading} className="rounded-xl border border-white/10 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/10 disabled:opacity-60">{bulkLoading === "assign" ? "Working…" : "Bulk assign"}</button><button type="button" onClick={() => void runBulkAction("mute")} disabled={!!bulkLoading || !!previewLoading} className="rounded-xl border border-white/10 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/10 disabled:opacity-60">{bulkLoading === "mute" ? "Working…" : "Bulk mute 1h"}</button><button type="button" data-testid="bulk-resolve-button" onClick={() => void runBulkAction("resolve")} disabled={!!bulkLoading || !!previewLoading} className="rounded-xl border border-emerald-500/25 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-100 hover:bg-emerald-500/15 disabled:opacity-60">{bulkLoading === "resolve" ? "Working…" : "Bulk resolve"}</button></div>{bulkPreview ? <div data-testid="bulk-preview-result" className="rounded-2xl border border-white/10 bg-black/20 p-3"><div className="flex items-center justify-between gap-3"><p className="text-xs uppercase tracking-wide text-white/40">Bulk dry-run · {bulkPreview.action_type}</p><button type="button" onClick={() => setBulkPreview(null)} className="rounded-lg border border-white/10 px-2 py-1 text-[11px] text-white/65">Clear</button></div><p className="mt-2 text-xs text-white/55">Eligible {bulkPreview.eligible} / {bulkPreview.attempted} · skipped {bulkPreview.skipped}</p>{(bulkPreview as any).guardrails ? <div className={`mt-2 rounded-xl border px-3 py-2 text-xs ${(bulkPreview as any).guardrails.ok ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-100" : "border-rose-500/25 bg-rose-500/10 text-rose-100"}`}><p className="font-semibold">Guardrails {(bulkPreview as any).guardrails.ok ? "passed" : "blocked"}</p><p className="mt-1 text-white/70">selection {(bulkPreview as any).guardrails.observed?.selection_size ?? 0} · high severity {(bulkPreview as any).guardrails.observed?.high_severity_items ?? 0}</p>{((bulkPreview as any).guardrails.blocked_reasons || []).length ? <div className="mt-2 space-y-1">{((bulkPreview as any).guardrails.blocked_reasons || []).map((reason: string) => <p key={reason}>• {reason}</p>)}</div> : null}</div> : null}<div className="mt-3 max-h-40 space-y-2 overflow-auto pr-1">{bulkPreview.items.slice(0, 10).map((item) => <div key={item.incident_key} className="rounded-xl border border-white/10 bg-white/5 p-2 text-xs text-white/70"><div className="flex items-center justify-between gap-2"><span className="font-semibold text-white/85">{item.incident_key}</span><span className={`rounded-full border px-2 py-0.5 ${item.eligible ? "border-emerald-500/25 text-emerald-100" : "border-amber-500/25 text-amber-100"}`}>{item.eligible ? "eligible" : item.reason || "skip"}</span></div><p className="mt-1 text-white/45">{item.current_status || "open"} → {item.predicted_status || item.current_status || "open"}</p></div>)}</div></div> : null}</div> : null}
            <div className="space-y-3">
              {incidents.map((incident) => {
                const active = incident.incident_key === selectedIncidentKey;
                return (
                  <div data-testid="incident-card" key={incident.incident_key} className={`rounded-2xl border p-4 ${active ? "border-sky-400/30 bg-sky-500/10" : "border-white/10 bg-black/20"}`}>
                    <div className="flex items-start gap-3">
                      <input data-testid="incident-select-checkbox" type="checkbox" checked={selectedKeys.includes(incident.incident_key)} onChange={() => toggleSelect(incident.incident_key)} className="mt-1" />
                      <button type="button" onClick={() => syncUrl({ incident: incident.incident_key })} className="flex-1 text-left">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-semibold text-white">{incident.incident_key}</span>
                          <span className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-white/65">{incident.current_status || incident.event_type}</span>
                          {incident.acknowledged ? <span className="rounded-full border border-emerald-500/25 px-2 py-0.5 text-[11px] text-emerald-100">ack</span> : null}
                          {incident.assigned_to ? <span className="rounded-full border border-sky-500/25 px-2 py-0.5 text-[11px] text-sky-100">{incident.assigned_to}</span> : null}
                          {incident.muted ? <span className="rounded-full border border-amber-500/25 px-2 py-0.5 text-[11px] text-amber-100">muted</span> : null}
                        </div>
                        <p className="mt-2 text-sm text-white/65">{incident.current_reason || incident.job.health_reason || incident.event_type}</p>
                        <div className="mt-3 flex flex-wrap gap-4 text-xs text-white/45">
                          <span>provider: {incident.job.provider}</span>
                          <span>project: {incident.job.project_id}</span>
                          <span>{new Date(incident.occurred_at).toLocaleString()}</span>
                        </div>
                      </button>
                    </div>
                  </div>
                );
              })}
              {!loading && incidents.length === 0 ? <div className="rounded-2xl border border-dashed border-white/10 p-6 text-sm text-white/50">No incidents match the current filters.</div> : null}
              {loading ? <div className="text-sm text-white/55">Loading incidents…</div> : null}
            </div>
          </div>

          <div data-testid="saved-views-panel" className="rounded-3xl border border-white/10 bg-white/5 p-5 space-y-4">
            <div>
              <p className="text-sm font-semibold text-white">Saved incident views</p>
              <p className="mt-1 text-xs text-white/45">Reusable filters for operator and team-lead work surfaces.</p>
            </div>{effectiveAccess ? <div data-testid="effective-access-preview" className="rounded-2xl border border-white/10 bg-black/20 p-4"><div className="flex items-center justify-between gap-2"><p className="text-xs uppercase tracking-wide text-white/40">Effective access preview</p><span className="text-[11px] text-white/45">{effectiveAccess.visible_to_count} visible</span></div><p className="mt-2 text-sm font-semibold text-white">{effectiveAccess.view_name}</p><p className="mt-1 text-xs text-white/45">scope: {effectiveAccess.share_scope} · owner: {effectiveAccess.owner_actor}</p><div className="mt-3 space-y-2">{visibleEffectiveEntries.map((entry) => <div key={entry.actor_id} className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/70"><span>{entry.actor_id}</span><span>{entry.reason || "visible"}</span></div>)}{!visibleEffectiveEntries.length ? <p className="text-sm text-white/45">No visible actors in current preview scope.</p> : null}</div></div> : null}
            <div className="space-y-3 rounded-2xl border border-white/10 bg-black/20 p-4">
              <input data-testid="saved-view-name-input" value={saveViewName} onChange={(e) => setSaveViewName(e.target.value)} placeholder="Name this view" className="w-full rounded-2xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white" />
              <label className="inline-flex items-center gap-2 text-xs text-white/60"><input data-testid="saved-view-shared-checkbox" type="checkbox" checked={saveViewShared} onChange={(e) => setSaveViewShared(e.target.checked)} />Shared view</label>
              <label className="space-y-1 text-xs text-white/55"><span>Share scope</span><select data-testid="saved-view-share-scope-select" value={saveViewShareScope} onChange={(e) => { setSaveViewShareScope(e.target.value); setSaveViewShared(e.target.value !== "private"); }} className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-white"><option value="private">private</option><option value="shared_all">shared_all</option><option value="team">team</option><option value="role">role</option></select></label>
              {saveViewShareScope === "team" ? <input value={saveViewTeamId} onChange={(e) => setSaveViewTeamId(e.target.value)} placeholder="Shared team id" className="w-full rounded-2xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white" /> : null}
              {saveViewShareScope === "role" ? <input value={saveViewAllowedRoles} onChange={(e) => setSaveViewAllowedRoles(e.target.value)} placeholder="team_lead,admin" className="w-full rounded-2xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white" /> : null}
              <button data-testid="saved-view-save-button" type="button" onClick={() => void handleSaveCurrentView()} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white hover:bg-white/10">Save current view</button>
              {editingViewId ? <div className="space-y-3 rounded-2xl border border-emerald-500/25 bg-emerald-500/10 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-emerald-100">Edit saved view</p>
                <input value={editViewName} onChange={(e) => setEditViewName(e.target.value)} placeholder="View name" className="w-full rounded-2xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white" />
                <textarea value={editViewDescription} onChange={(e) => setEditViewDescription(e.target.value)} placeholder="Optional description" className="min-h-[80px] w-full rounded-2xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white" />
                <label className="inline-flex items-center gap-2 text-xs text-white/60"><input type="checkbox" checked={editViewShared} onChange={(e) => setEditViewShared(e.target.checked)} />Shared view</label>
                <label className="space-y-1 text-xs text-white/55"><span>Share scope</span><select value={editViewShareScope} onChange={(e) => { setEditViewShareScope(e.target.value); setEditViewShared(e.target.value !== "private"); }} className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-white"><option value="private">private</option><option value="shared_all">shared_all</option><option value="team">team</option><option value="role">role</option></select></label>
                {editViewShareScope === "team" ? <input value={editViewTeamId} onChange={(e) => setEditViewTeamId(e.target.value)} placeholder="Shared team id" className="w-full rounded-2xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white" /> : null}
                {editViewShareScope === "role" ? <input value={editViewAllowedRoles} onChange={(e) => setEditViewAllowedRoles(e.target.value)} placeholder="team_lead,admin" className="w-full rounded-2xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white" /> : null}
                <div className="flex gap-2"><button type="button" onClick={() => void handleUpdateView()} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white hover:bg-white/10">Update view</button><button type="button" onClick={() => setEditingViewId(null)} className="rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-xs text-white/70">Cancel</button></div>
                <p className="text-[11px] text-white/45">Update applies current dashboard filters and segment.</p>
              </div> : null}
            </div>
            <div className="space-y-3">
              {savedViews.map((view) => (
                <div data-testid="saved-view-card" key={view.id} className={`rounded-2xl border p-4 ${view.id === selectedViewId ? "border-emerald-500/25 bg-emerald-500/10" : "border-white/10 bg-black/20"}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">{view.name}</p>
                      <p className="mt-1 text-xs text-white/45">owner: {view.owner_actor}{view.is_shared ? ` · ${(view as any).share_scope || "shared"}` : ""}</p>
                    </div>
                    <div className="flex gap-2">
                      <button data-testid="saved-view-apply-button" type="button" onClick={() => applySavedView(view)} className="rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white hover:bg-white/10">Apply</button>{view.owner_actor === actor ? <button data-testid="saved-view-edit-button" type="button" onClick={() => startEditView(view)} className="rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white hover:bg-white/10">Edit</button> : null}
                      {view.owner_actor === actor ? <button type="button" onClick={async () => { await deleteIncidentSavedView(view.id, actor); await loadSavedViews(); if (selectedViewId === view.id) syncUrl({ view: null }); pushToast("Saved view deleted", view.name, "success"); }} className="rounded-xl border border-rose-500/25 bg-rose-500/10 px-3 py-1.5 text-xs text-rose-100 hover:bg-rose-500/15">Delete</button> : null}
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-white/55">
                    <span className="rounded-full border border-white/10 px-2 py-1">segment: {view.filters.segment || "active"}</span>
                    <span className="rounded-full border border-white/10 px-2 py-1">provider: {view.filters.provider || "all"}</span>
                    <span className="rounded-full border border-white/10 px-2 py-1">workflow: {view.filters.workflow_status || "all"}</span>
                  </div>
                </div>
              ))}
              {!savedViews.length ? <div className="rounded-2xl border border-dashed border-white/10 p-4 text-sm text-white/45">No saved incident views yet.</div> : null}
            </div>
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-[0.7fr_1.3fr]">
          <div className="rounded-3xl border border-white/10 bg-white/5 p-5 space-y-4">
            <div>
              <p className="text-sm font-semibold text-white">Access & sharing policy</p>
              <p className="mt-1 text-xs text-white/45">RBAC scope used to gate shared views and bulk history visibility.</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-white/75">
              <p><span className="text-white/45">Actor:</span> {accessProfile?.actor_id || actor}</p>
              <p className="mt-2"><span className="text-white/45">Role:</span> {accessProfile?.role || "operator"}</p>
              <p className="mt-2"><span className="text-white/45">Team:</span> {accessProfile?.team_id || "—"}</p>
              <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-white/60">{Object.entries((accessProfile?.scopes || {}) as Record<string, unknown>).map(([key, value]) => <span key={key} className="rounded-full border border-white/10 px-2 py-1">{key}: {String(value)}</span>)}</div>
            </div>
          </div>
          <div data-testid="bulk-audit-panel" className="rounded-3xl border border-white/10 bg-white/5 p-5 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-white">Bulk action history & audit</p>
                <p className="mt-1 text-xs text-white/45">Recent apply and preview bulk runs with persisted results for team-lead review.</p>
              </div>
              <button type="button" onClick={() => void loadBulkAuditRuns()} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white hover:bg-white/10">Refresh audit</button>
            </div>
            <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
              <div className="space-y-3">
                {bulkAuditRuns.map((run) => <button data-testid="bulk-audit-run-button" key={run.id} type="button" onClick={() => void openBulkAuditRun(run.id)} className={`w-full rounded-2xl border p-4 text-left ${bulkAuditDetail?.run.id === run.id ? "border-emerald-500/25 bg-emerald-500/10" : "border-white/10 bg-black/20"}`}><div className="flex items-center justify-between gap-3"><span className="text-sm font-semibold text-white">{run.action_type}</span><span className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-white/65">{run.actor_role}</span></div><p className="mt-2 text-xs text-white/55">{run.actor} · {new Date(run.created_at).toLocaleString()}</p><p className="mt-2 text-xs text-white/45">{run.succeeded}/{run.attempted} succeeded</p></button>)}
                {!bulkAuditRuns.length ? <div className="rounded-2xl border border-dashed border-white/10 p-4 text-sm text-white/45">No bulk audit runs yet.</div> : null}
              </div>
              <div data-testid="bulk-audit-detail" className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <p className="text-xs uppercase tracking-wide text-white/40">Selected bulk run</p>
                {bulkAuditDetail ? <>
                  <div className="mt-3 grid gap-2 text-sm text-white/75 sm:grid-cols-2">
                    <span>Action: {bulkAuditDetail.run.action_type}</span><span>Actor: {bulkAuditDetail.run.actor}</span><span>Role: {bulkAuditDetail.run.actor_role}</span><span>Mode: {bulkAuditDetail.run.mode}</span><span>Attempted: {bulkAuditDetail.run.attempted}</span><span>Succeeded: {bulkAuditDetail.run.succeeded}</span>
                  </div>
                  <div className="mt-4 max-h-56 space-y-2 overflow-auto pr-1">{bulkAuditDetail.items.map((item) => <div key={`${bulkAuditDetail.run.id}_${item.incident_key}_${item.created_at}`} className="rounded-xl border border-white/10 bg-white/5 p-2 text-xs text-white/70"><div className="flex items-center justify-between gap-2"><span className="font-semibold text-white/85">{item.incident_key}</span><span className={`rounded-full border px-2 py-0.5 ${item.ok ? "border-emerald-500/25 text-emerald-100" : "border-rose-500/25 text-rose-100"}`}>{item.ok ? item.status || "ok" : item.error || "failed"}</span></div></div>)}</div>
                </> : <p className="mt-3 text-sm text-white/45">Select a bulk run to inspect persisted result items.</p>}
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-3xl border border-white/10 bg-white/5 p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-white">Render jobs snapshot</p>
              <p className="mt-1 text-xs text-white/45">Quick jump to a full job page when the incident drawer needs deeper runtime context.</p>
            </div>
            {error ? <span className="text-xs text-rose-300">{error}</span> : null}
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {jobs.map((job) => (
              <Link key={job.id} href={`/render-jobs/${job.id}`} className="rounded-2xl border border-white/10 bg-black/20 p-4 hover:border-white/20 hover:bg-black/30">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold text-white">{job.id}</span>
                  <span className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-white/65">{job.health_status || job.status}</span>
                </div>
                <p className="mt-2 text-sm text-white/65">provider: {job.provider}</p>
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-white/45">
                  <span>planned {job.planned_scene_count}</span>
                  <span>processing {job.processing_scene_count}</span>
                  <span>failed {job.failed_scene_count_snapshot}</span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      </DashboardShell>
    </>
  );
}
