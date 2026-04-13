import { ValidationIssue } from "@/src/lib/api";

export function buildFieldKey(
  targetType: "scene" | "subtitle" | "preview",
  targetIndex: number | null | undefined,
  field: string | null | undefined,
): string {
  return `${targetType}:${targetIndex ?? "root"}:${field ?? "root"}`;
}

export function issueToFieldKey(issue: ValidationIssue): string {
  return buildFieldKey(issue.target_type, issue.target_index, issue.field);
}