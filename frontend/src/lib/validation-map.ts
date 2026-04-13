import { ValidationIssue } from "@/src/lib/api";
export function getSceneIssues(issues: ValidationIssue[], rowIndex: number): ValidationIssue[] { return issues.filter((issue) => issue.target_type === "scene" && issue.target_index === rowIndex); }
export function getSubtitleIssues(issues: ValidationIssue[], rowIndex: number): ValidationIssue[] { return issues.filter((issue) => issue.target_type === "subtitle" && issue.target_index === rowIndex); }
export function getPreviewIssues(issues: ValidationIssue[]): ValidationIssue[] { return issues.filter((issue) => issue.target_type === "preview"); }
export function getFieldIssues(issues: ValidationIssue[], targetType: "scene" | "subtitle" | "preview", targetIndex: number | null | undefined, field: string): ValidationIssue[] { return issues.filter((issue) => issue.target_type === targetType && (issue.target_index ?? null) === (targetIndex ?? null) && issue.field === field); }
