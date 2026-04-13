"use client";

import { ValidationIssue } from "@/src/lib/api";

export default function ValidationPanel({
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
      <h3 className="text-lg font-semibold text-rose-200">
        Validation issues found
      </h3>
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