#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

artifacts_root = Path("artifacts/playwright")
report_path = Path("artifacts/ci/quarantine_report.md")
report_path.parent.mkdir(parents=True, exist_ok=True)

lines = ["# Flaky test quarantine report", ""]
found = False

for results_json in sorted(artifacts_root.rglob("results.json")):
    found = True
    lines.append(f"## {results_json.parent.name}")
    try:
        data = json.loads(results_json.read_text(encoding="utf-8"))
        lines.append("```json")
        lines.append(json.dumps(data, indent=2)[:20000])
        lines.append("```")
    except Exception as exc:
        lines.append(f"Could not parse {results_json}: {exc}")
    lines.append("")

if not found:
    lines.append("No Playwright JSON reports were found.")

lines.append("## Interpretation guide")
lines.append("- Failures that disappear on replay may indicate flakiness.")
lines.append("- Failures that reproduce across all repeats are more likely deterministic regressions.")
lines.append("- Use this report together with screenshots, traces, and videos from the shard artifact.")

report_path.write_text("\n".join(lines), encoding="utf-8")
print(report_path)
