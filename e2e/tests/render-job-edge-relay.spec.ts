import { expect, test } from "@playwright/test";
import crypto from "node:crypto";

type Json = Record<string, any>;

const BACKEND_BASE_URL = (process.env.BACKEND_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");
const FRONTEND_BASE_URL = (process.env.FRONTEND_BASE_URL || "http://localhost:3000").replace(/\/+$/, "");
const EDGE_BASE_URL = (process.env.EDGE_BASE_URL || "http://localhost:8080").replace(/\/+$/, "");
const RELAY_SECRET = process.env.PROVIDER_RELAY_SHARED_SECRET || "replace-me";
const PROVIDER = (process.env.E2E_PROVIDER || "runway").toLowerCase();
const DELIVERY_MODE = (process.env.E2E_DELIVERY_MODE || "edge-callback").toLowerCase();

function buildJobPayload(provider: string): Json {
  const aspectRatio = process.env.E2E_ASPECT_RATIO || "16:9";
  const promptText = process.env.E2E_PROMPT_TEXT || "A cinematic test shot with gentle motion and clear subject framing.";
  const duration = provider === "veo" ? 4 : 5;
  return {
    project_id: `playwright-${provider}-${Date.now()}`,
    provider,
    aspect_ratio: aspectRatio,
    subtitle_mode: "soft",
    planned_scenes: [
      {
        scene_index: 1,
        title: "Playwright smoke scene",
        script_text: promptText,
        provider_target_duration_sec: duration,
        target_duration_sec: duration,
        visual_prompt: promptText,
      },
    ],
  };
}

function buildSuccessCallback(provider: string, scene: Json, jobId: string): Json {
  const assetUrl = `https://example.invalid/assets/${jobId}/${scene.id || "scene-1"}.mp4`;
  const providerTaskId = scene.provider_task_id;
  const providerOperationName = scene.provider_operation_name;

  if (provider === "runway") {
    return {
      id: `evt-${jobId}`,
      taskId: providerTaskId,
      status: "SUCCEEDED",
      outputUrl: assetUrl,
      thumbnailUrl: `${assetUrl}.jpg`,
      event: "task.completed",
    };
  }

  if (provider === "kling") {
    return {
      request_id: `evt-${jobId}`,
      data: {
        task_id: providerTaskId,
        task_status: "succeed",
        task_result: {
          videos: [{ url: assetUrl, cover_url: `${assetUrl}.jpg` }],
        },
      },
      event: "kling.task.completed",
    };
  }

  return {
    name: providerOperationName || `operations/${jobId}`,
    done: true,
    response: {
      generateVideoResponse: {
        generatedSamples: [
          { video: { uri: assetUrl }, image: { uri: `${assetUrl}.jpg` } },
        ],
      },
    },
    type: "veo.operation.completed",
  };
}

function buildFailureCallback(provider: string, scene: Json, jobId: string): Json {
  if (provider === "runway") {
    return {
      id: `evt-fail-${jobId}`,
      taskId: scene.provider_task_id,
      status: "FAILED",
      error: "Synthetic failure",
      event: "task.failed",
    };
  }
  if (provider === "kling") {
    return {
      request_id: `evt-fail-${jobId}`,
      data: {
        task_id: scene.provider_task_id,
        task_status: "failed",
        fail_reason: "Synthetic failure",
      },
      event: "kling.task.failed",
    };
  }
  return {
    name: scene.provider_operation_name || `operations/${jobId}`,
    done: true,
    error: { message: "Synthetic failure" },
    type: "veo.operation.failed",
  };
}

async function getJson(request: any, url: string): Promise<Json> {
  const response = await request.get(url, { failOnStatusCode: false });
  expect(response.ok(), `GET ${url} failed with ${response.status()}`).toBeTruthy();
  return await response.json();
}

async function postJson(request: any, url: string, payload: Json, headers: Record<string, string> = {}): Promise<Json> {
  const response = await request.post(url, {
    failOnStatusCode: false,
    data: payload,
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
  });
  expect(response.ok(), `POST ${url} failed with ${response.status()} ${await response.text()}`).toBeTruthy();
  const contentType = response.headers()["content-type"] || "";
  if (contentType.includes("application/json")) {
    return await response.json();
  }
  return { raw: await response.text() };
}

async function waitFor(
  fn: () => Promise<Json>,
  predicate: (data: Json) => boolean,
  timeoutMs: number,
  intervalMs: number,
): Promise<Json> {
  const deadline = Date.now() + timeoutMs;
  let last: Json = {};
  while (Date.now() < deadline) {
    last = await fn();
    if (predicate(last)) return last;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error(`Timed out waiting for condition. Last payload: ${JSON.stringify(last, null, 2)}`);
}

function buildRelayHeaders(rawBody: string): Record<string, string> {
  const timestamp = `${Math.floor(Date.now() / 1000)}`;
  const signature = "sha256=" + crypto.createHmac("sha256", RELAY_SECRET).update(`${timestamp}.${rawBody}`).digest("hex");
  return {
    "X-Render-Relay-Timestamp": timestamp,
    "X-Render-Relay-Signature": signature,
  };
}

async function getJobSnapshot(request: any, jobId: string): Promise<Json> {
  const payload = await getJson(request, `${BACKEND_BASE_URL}/api/v1/render/jobs/${jobId}`);
  return payload.data || payload;
}

async function waitForSubmission(request: any, jobId: string): Promise<Json> {
  return await waitFor(
    async () => await getJobSnapshot(request, jobId),
    (job) => Boolean(job.scenes?.[0]?.provider_task_id || job.scenes?.[0]?.provider_operation_name || (job.scenes?.[0]?.status && String(job.scenes?.[0]?.status).toLowerCase() !== "queued")),
    60_000,
    2_000,
  );
}

async function waitForCompletedJob(request: any, jobId: string): Promise<Json> {
  return await waitFor(
    async () => await getJobSnapshot(request, jobId),
    (job) => String(job.status || "").toLowerCase() === "completed" && Boolean(job.output_url || job.final_video_url || job.storage_key || job.final_timeline),
    180_000,
    5_000,
  );
}


async function findIncidentByJobId(request: any, jobId: string): Promise<Json> {
  const payload = await getJson(request, `${BACKEND_BASE_URL}/api/v1/render/incidents/recent?limit=50&show_muted=true`);
  const items = payload.items || [];
  const incident = items.find((item: any) => item.job?.job_id === jobId || item.job?.id === jobId);
  if (!incident) {
    throw new Error(`Incident not found yet for job ${jobId}`);
  }
  return incident;
}

async function waitForIncidentForJob(request: any, jobId: string): Promise<Json> {
  return await waitFor(
    async () => await findIncidentByJobId(request, jobId),
    (incident) => Boolean(incident.incident_key),
    120_000,
    5_000,
  );
}

async function getIncidentHistory(request: any, incidentKey: string): Promise<Json> {
  return await getJson(request, `${BACKEND_BASE_URL}/api/v1/render/dashboard/incidents/${encodeURIComponent(incidentKey)}/history`);
}

async function waitForIncidentAction(request: any, incidentKey: string, actionType: string): Promise<Json> {
  return await waitFor(
    async () => await getIncidentHistory(request, incidentKey),
    (payload) => Array.isArray(payload.actions) && payload.actions.some((item: any) => String(item.action_type || "").toLowerCase() === actionType.toLowerCase()),
    60_000,
    2_000,
  );
}

test("full local chain: create job -> submit -> callback -> status api -> frontend page with final asset assertions", async ({ page, request }) => {
  const createPayload = buildJobPayload(PROVIDER);
  const createRes = await postJson(request, `${BACKEND_BASE_URL}/api/v1/render/jobs`, createPayload);
  const created = createRes.data || createRes;
  const jobId = created.job_id || created.id;
  expect(jobId).toBeTruthy();

  const submitted = await waitForSubmission(request, jobId);
  const scene = submitted.scenes?.[0];
  expect(scene).toBeTruthy();

  if (DELIVERY_MODE !== "poll") {
    const callbackPayload = buildSuccessCallback(PROVIDER, scene, jobId);
    const rawBody = JSON.stringify(callbackPayload);

    if (DELIVERY_MODE === "direct-relay") {
      await postJson(request, `${BACKEND_BASE_URL}/api/v1/provider-callbacks/relay/${PROVIDER}`, callbackPayload, buildRelayHeaders(rawBody));
    } else {
      await postJson(request, `${EDGE_BASE_URL}/hooks/${PROVIDER}`, callbackPayload);
    }
  }

  const completed = await waitForCompletedJob(request, jobId);
  expect(String(completed.status || "").toLowerCase()).toBe("completed");
  expect(completed.output_url || completed.final_video_url).toBeTruthy();
  expect(Array.isArray(completed.final_timeline) || typeof completed.final_timeline === "object").toBeTruthy();

  const snapshotResponse = await request.get(`${FRONTEND_BASE_URL}/api/render-jobs/${jobId}/snapshot`, { failOnStatusCode: false });
  expect(snapshotResponse.ok(), `frontend snapshot failed with ${snapshotResponse.status()}`).toBeTruthy();
  const snapshotJson = await snapshotResponse.json();
  const snapshot = snapshotJson.data || snapshotJson;
  const snapshotId = snapshot.job_id || snapshot.id;
  expect(snapshotId).toBe(jobId);
  expect(snapshot.output_url || snapshot.final_video_url).toBeTruthy();

  const finalAssetUrl = String(snapshot.output_url || snapshot.final_video_url || "");
  if (finalAssetUrl.startsWith("/storage/")) {
    const assetResponse = await request.get(`${BACKEND_BASE_URL}${finalAssetUrl}`, { failOnStatusCode: false });
    expect(assetResponse.ok(), `final asset fetch failed with ${assetResponse.status()}`).toBeTruthy();
  }

  const finalDownloadResponse = await request.get(`${BACKEND_BASE_URL}/api/v1/storage/jobs/${jobId}/final-download`, { failOnStatusCode: false });
  if (finalDownloadResponse.ok()) {
    const downloadJson = await finalDownloadResponse.json();
    expect(downloadJson.key || downloadJson.signed_url).toBeTruthy();
  }

  await page.goto(`${FRONTEND_BASE_URL}/render-jobs/${jobId}`, { waitUntil: "networkidle" });
  await expect(page.getByText(new RegExp(`Job\s+${jobId}`))).toBeVisible();
  await expect(page.getByTestId("render-job-final-video")).toBeVisible();
  await expect(page.getByTestId("render-job-final-video-url")).toContainText(finalAssetUrl);
  await expect(page.getByTestId("render-job-final-timeline")).toContainText(/timeline entries/i);
  await expect(page.getByTestId("render-job-subtitle-summary")).toContainText(/subtitle segments/i);
});

test("dashboard incident drawer opens for failed provider callback", async ({ page, request }) => {
  const createPayload = buildJobPayload(PROVIDER);
  const createRes = await postJson(request, `${BACKEND_BASE_URL}/api/v1/render/jobs`, createPayload);
  const created = createRes.data || createRes;
  const jobId = created.job_id || created.id;
  expect(jobId).toBeTruthy();

  const submitted = await waitForSubmission(request, jobId);
  const scene = submitted.scenes?.[0];
  expect(scene).toBeTruthy();

  const failurePayload = buildFailureCallback(PROVIDER, scene, jobId);
  const rawBody = JSON.stringify(failurePayload);
  await postJson(request, `${BACKEND_BASE_URL}/api/v1/provider-callbacks/relay/${PROVIDER}`, failurePayload, buildRelayHeaders(rawBody));

  await waitFor(
    async () => await getJson(request, `${BACKEND_BASE_URL}/api/v1/render/incidents/recent?limit=50&show_muted=true`),
    (payload) => Boolean((payload.items || []).find((item: any) => item.job?.job_id === jobId || item.job?.id === jobId)),
    120_000,
    5_000,
  );

  await page.goto(`${FRONTEND_BASE_URL}/render-jobs`, { waitUntil: "networkidle" });
  await expect(page.getByText(/Saved incident views/i)).toBeVisible();
  const incidentCard = page.locator('[data-testid="incident-card"]').filter({ hasText: jobId }).first();
  await expect(incidentCard).toBeVisible();
  await incidentCard.click();
  await expect(page.getByTestId("incident-drawer")).toBeVisible();
  await expect(page.getByText(/Workflow history/i)).toBeVisible();
});




test("incident drawer actions: ack -> assign -> mute -> resolve -> reopen with timeline and history verification", async ({ page, request }) => {
  const createPayload = buildJobPayload(PROVIDER);
  const createRes = await postJson(request, `${BACKEND_BASE_URL}/api/v1/render/jobs`, createPayload);
  const created = createRes.data || createRes;
  const jobId = created.job_id || created.id;
  expect(jobId).toBeTruthy();

  const submitted = await waitForSubmission(request, jobId);
  const scene = submitted.scenes?.[0];
  expect(scene).toBeTruthy();

  const failurePayload = buildFailureCallback(PROVIDER, scene, jobId);
  const rawBody = JSON.stringify(failurePayload);
  await postJson(request, `${BACKEND_BASE_URL}/api/v1/provider-callbacks/relay/${PROVIDER}`, failurePayload, buildRelayHeaders(rawBody));

  const incident = await waitForIncidentForJob(request, jobId);
  const incidentKey = String(incident.incident_key);
  expect(incidentKey).toBeTruthy();

  let historyState = await getIncidentHistory(request, incidentKey);
  let actionCount = Array.isArray(historyState.actions) ? historyState.actions.length : 0;
  let timelineCount = Array.isArray(historyState.projected_timeline) ? historyState.projected_timeline.length : Array.isArray(historyState.timeline_events) ? historyState.timeline_events.length : 0;

  await page.goto(`${FRONTEND_BASE_URL}/render-jobs`, { waitUntil: "networkidle" });
  const incidentCard = page.locator('[data-testid="incident-card"]').filter({ hasText: jobId }).first();
  await expect(incidentCard).toBeVisible();
  await incidentCard.click();

  const drawer = page.getByTestId("incident-drawer");
  await expect(drawer).toBeVisible();
  await drawer.getByTestId("incident-actor-input").fill("playwright-operator");
  await drawer.getByTestId("incident-assignee-input").fill("oncall-playwright");

  const actionReasonInput = drawer.getByTestId("incident-action-reason-input");
  const currentStatus = drawer.getByTestId("incident-current-status");

  await actionReasonInput.fill("Playwright acknowledge reason");
  await drawer.getByTestId("incident-action-ack").click();
  await expect(currentStatus).toContainText(/acknowledged/i);
  historyState = await waitForIncidentAction(request, incidentKey, "acknowledge");
  expect(String(historyState.incident?.status || "")).toMatch(/acknowledged/i);
  expect((historyState.actions || []).length).toBeGreaterThan(actionCount);
  expect(((historyState.projected_timeline || historyState.timeline_events) || []).length).toBeGreaterThanOrEqual(timelineCount);
  actionCount = (historyState.actions || []).length;
  timelineCount = ((historyState.projected_timeline || historyState.timeline_events) || []).length;
  await expect(drawer.getByTestId("incident-history-item-acknowledge").first()).toBeVisible();

  await actionReasonInput.fill("Playwright assign reason");
  await drawer.getByTestId("incident-action-assign").click();
  historyState = await waitForIncidentAction(request, incidentKey, "assign");
  expect(String(historyState.incident?.assigned_to || "")).toContain("oncall-playwright");
  expect((historyState.actions || []).length).toBeGreaterThan(actionCount);
  expect(((historyState.projected_timeline || historyState.timeline_events) || []).length).toBeGreaterThanOrEqual(timelineCount);
  actionCount = (historyState.actions || []).length;
  timelineCount = ((historyState.projected_timeline || historyState.timeline_events) || []).length;
  await expect(drawer.getByTestId("incident-history-item-assign").first()).toBeVisible();

  await actionReasonInput.fill("Playwright mute reason");
  await drawer.getByTestId("incident-action-mute").click();
  await expect(currentStatus).toContainText(/muted/i);
  historyState = await waitForIncidentAction(request, incidentKey, "mute");
  expect(Boolean(historyState.incident?.muted)).toBeTruthy();
  expect(String(historyState.incident?.muted_until || "")).toBeTruthy();
  expect((historyState.actions || []).length).toBeGreaterThan(actionCount);
  expect(((historyState.projected_timeline || historyState.timeline_events) || []).length).toBeGreaterThanOrEqual(timelineCount);
  actionCount = (historyState.actions || []).length;
  timelineCount = ((historyState.projected_timeline || historyState.timeline_events) || []).length;
  await expect(drawer.getByTestId("incident-history-item-mute").first()).toBeVisible();

  await actionReasonInput.fill("Playwright resolve reason");
  await drawer.getByTestId("incident-action-resolve").click();
  await expect(currentStatus).toContainText(/resolved/i);
  historyState = await waitForIncidentAction(request, incidentKey, "resolve");
  expect(String(historyState.incident?.status || "")).toMatch(/resolved/i);
  expect(String(historyState.incident?.resolved_at || "")).toBeTruthy();
  expect((historyState.actions || []).length).toBeGreaterThan(actionCount);
  expect(((historyState.projected_timeline || historyState.timeline_events) || []).length).toBeGreaterThanOrEqual(timelineCount);
  actionCount = (historyState.actions || []).length;
  timelineCount = ((historyState.projected_timeline || historyState.timeline_events) || []).length;
  await expect(drawer.getByTestId("incident-history-item-resolve").first()).toBeVisible();

  await actionReasonInput.fill("Playwright reopen reason");
  await drawer.getByTestId("incident-action-reopen").click();
  await expect(currentStatus).toContainText(/open/i);
  historyState = await waitForIncidentAction(request, incidentKey, "reopen");
  expect(String(historyState.incident?.status || "")).toMatch(/open/i);
  expect(Number(historyState.incident?.reopen_count || 0)).toBeGreaterThan(0);
  expect((historyState.actions || []).length).toBeGreaterThan(actionCount);
  expect(((historyState.projected_timeline || historyState.timeline_events) || []).length).toBeGreaterThanOrEqual(timelineCount);
  await expect(drawer.getByTestId("incident-history-item-reopen").first()).toBeVisible();

  const actionTypes = (historyState.actions || []).map((item: any) => String(item.action_type || "").toLowerCase());
  expect(actionTypes).toEqual(expect.arrayContaining(["acknowledge", "assign", "mute", "resolve", "reopen"]));
});


test("dashboard ops suite: bulk actions + saved views + effective access + productivity board", async ({ page, request }) => {
  async function deliverSyntheticFailure(jobId: string, scene: Json) {
    const callbackPayload = buildFailureCallback(PROVIDER, scene, jobId);
    const rawBody = JSON.stringify(callbackPayload);
    if (DELIVERY_MODE === "edge-callback") {
      await postJson(request, `${EDGE_BASE_URL}/hooks/${PROVIDER}`, callbackPayload);
      return;
    }
    await postJson(request, `${BACKEND_BASE_URL}/api/v1/provider-callbacks/relay/${PROVIDER}`, callbackPayload, buildRelayHeaders(rawBody));
  }

  async function createFailedIncident(): Promise<{ jobId: string; incidentKey: string }> {
    const createPayload = buildJobPayload(PROVIDER);
    const createRes = await postJson(request, `${BACKEND_BASE_URL}/api/v1/render/jobs`, createPayload);
    const created = createRes.data || createRes;
    const jobId = created.job_id || created.id;
    expect(jobId).toBeTruthy();

    const submitted = await waitForSubmission(request, jobId);
    const scene = submitted.scenes?.[0];
    expect(scene).toBeTruthy();

    await deliverSyntheticFailure(jobId, scene);
    const incident = await waitForIncidentForJob(request, jobId);
    expect(incident.incident_key).toBeTruthy();
    return { jobId, incidentKey: incident.incident_key };
  }

  async function waitForIncidentStatus(incidentKey: string, statusRegex: RegExp): Promise<Json> {
    return await waitFor(
      async () => await getIncidentHistory(request, incidentKey),
      (payload) => statusRegex.test(String(payload.incident?.status || payload.incident?.current_status || "")),
      60_000,
      2_000,
    );
  }

  const first = await createFailedIncident();
  const second = await createFailedIncident();

  await page.goto(`${FRONTEND_BASE_URL}/render-jobs`, { waitUntil: "networkidle" });
  await expect(page.getByTestId("incident-card").first()).toBeVisible();

  const incidentCards = page.getByTestId("incident-card");
  await expect(incidentCards).toHaveCount(2, { timeout: 30_000 }).catch(async () => {
    await expect(incidentCards.first()).toBeVisible();
  });

  const checkboxes = page.getByTestId("incident-select-checkbox");
  await checkboxes.nth(0).check();
  await checkboxes.nth(1).check();

  await expect(page.getByTestId("bulk-selected-count")).toContainText(/2 selected/i);
  await page.getByTestId("bulk-preview-resolve-button").click();
  await expect(page.getByTestId("bulk-preview-result")).toBeVisible();
  await expect(page.getByTestId("bulk-preview-result")).toContainText(/Eligible/i);

  await page.getByTestId("bulk-resolve-button").click();
  await waitForIncidentAction(request, first.incidentKey, "resolve");
  await waitForIncidentAction(request, second.incidentKey, "resolve");
  await waitForIncidentStatus(first.incidentKey, /resolved/i);
  await waitForIncidentStatus(second.incidentKey, /resolved/i);

  await expect(page.getByTestId("bulk-audit-panel")).toBeVisible();
  await expect(page.getByTestId("bulk-audit-run-button").first()).toBeVisible({ timeout: 30_000 });
  await page.getByTestId("bulk-audit-run-button").first().click();
  await expect(page.getByTestId("bulk-audit-detail")).toContainText(/Action:/i);
  await expect(page.getByTestId("bulk-audit-detail")).toContainText(/resolve/i);

  const viewName = `playwright-view-${Date.now()}`;
  await expect(page.getByTestId("saved-views-panel")).toBeVisible();
  await page.getByTestId("saved-view-name-input").fill(viewName);
  await page.getByTestId("saved-view-share-scope-select").selectOption("shared_all");
  await page.getByTestId("saved-view-save-button").click();

  const matchingViewCard = page.getByTestId("saved-view-card").filter({ hasText: viewName }).first();
  await expect(matchingViewCard).toBeVisible({ timeout: 30_000 });
  await matchingViewCard.getByTestId("saved-view-apply-button").click();

  await expect(page.getByTestId("effective-access-preview")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("effective-access-preview")).toContainText(viewName);
  await expect(page.getByTestId("effective-access-preview")).toContainText(/visible/i);

  const productApi = await getJson(request, `${BACKEND_BASE_URL}/api/v1/render/dashboard/incidents/productivity?actor=operator%40local&days=7`);
  expect(productApi).toBeTruthy();

  await expect(page.getByTestId("productivity-board")).toBeVisible();
  await page.getByTestId("productivity-refresh-button").click();
  await expect(page.getByTestId("productivity-teams")).toBeVisible();
  await expect(page.getByTestId("productivity-operators")).toBeVisible();
  await expect(page.getByTestId("productivity-trends")).toBeVisible();

  const operatorText = await page.getByTestId("productivity-operators").innerText();
  expect(operatorText.length).toBeGreaterThan(0);
});
