"use client";

import React, { useState } from "react";
import {
  scheduleExecutionPlan,
  pauseExecutionPlan,
  resumeExecutionPlan,
  cancelExecutionPlan,
  evaluateExecutionPlan,
  getExecutionPlanEvaluation,
  evaluateExecutionPlanPolicyPath,
  getExecutionPlanPolicyPath,
} from "@/src/lib/api";
import GovernanceSchedulePanel from "@/src/components/templates/GovernanceSchedulePanel";
import GovernanceOrchestrationControlPanel from "@/src/components/templates/GovernanceOrchestrationControlPanel";
import PostPlanEvaluationPanel from "@/src/components/templates/PostPlanEvaluationPanel";
import PolicyPromotionPathPanel from "@/src/components/templates/PolicyPromotionPathPanel";

const DEFAULT_ACTOR_ID = "supervisor_ui";

export default function GovernanceSchedulingPage() {
  const [planId, setPlanId] = useState("");
  const [evaluation, setEvaluation] = useState<any | null>(null);
  const [policyPath, setPolicyPath] = useState<any | null>(null);
  const [loadingEval, setLoadingEval] = useState(false);
  const [loadingPath, setLoadingPath] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh(planIdValue: string) {
    if (!planIdValue) return;
    try {
      const [evalRow, pathRow] = await Promise.all([
        getExecutionPlanEvaluation(planIdValue),
        getExecutionPlanPolicyPath(planIdValue),
      ]);
      setEvaluation(evalRow);
      setPolicyPath(pathRow);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh scheduling page");
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Governance scheduling</h1>
          <p className="mt-1 text-sm text-slate-500">
            Schedule execution plans, control orchestration lifecycle, and evaluate post-plan outcome.
          </p>
        </div>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <label className="block">
            <div className="mb-1.5 text-sm font-medium text-slate-800">Execution plan ID</div>
            <input
              value={planId}
              onChange={(e) => setPlanId(e.target.value)}
              placeholder="execution_plan_id"
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
            />
          </label>

          <button
            type="button"
            onClick={() => refresh(planId)}
            className="mt-4 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700"
          >
            Refresh data
          </button>
        </section>

        {error ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div>
        ) : null}

        <GovernanceSchedulePanel
          onSaveSchedule={async (payload) => {
            if (!planId) return;
            await scheduleExecutionPlan(planId, {
              scheduled_at: payload.scheduledAt || null,
              execution_window_start: payload.executionWindowStart || null,
              execution_window_end: payload.executionWindowEnd || null,
              allow_run_outside_window: payload.allowRunOutsideWindow,
            });
            await refresh(planId);
          }}
        />

        <GovernanceOrchestrationControlPanel
          onPause={async (reason) => {
            if (!planId) return;
            await pauseExecutionPlan(planId, DEFAULT_ACTOR_ID, reason);
            await refresh(planId);
          }}
          onResume={async () => {
            if (!planId) return;
            await resumeExecutionPlan(planId, DEFAULT_ACTOR_ID);
            await refresh(planId);
          }}
          onCancel={async (reason) => {
            if (!planId) return;
            await cancelExecutionPlan(planId, DEFAULT_ACTOR_ID, reason);
            await refresh(planId);
          }}
        />

        <PostPlanEvaluationPanel
          data={evaluation}
          loading={loadingEval}
          error={null}
          onEvaluate={async () => {
            if (!planId) return;
            setLoadingEval(true);
            try {
              await evaluateExecutionPlan(planId);
              await refresh(planId);
            } finally {
              setLoadingEval(false);
            }
          }}
        />

        <PolicyPromotionPathPanel
          data={policyPath}
          loading={loadingPath}
          error={null}
          onEvaluate={async () => {
            if (!planId) return;
            setLoadingPath(true);
            try {
              await evaluateExecutionPlanPolicyPath(planId);
              await refresh(planId);
            } finally {
              setLoadingPath(false);
            }
          }}
        />
      </div>
    </main>
  );
}
