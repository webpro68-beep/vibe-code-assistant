#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path

shard = os.getenv("ARTIFACT_SHARD", "default")
artifacts_dir = Path("artifacts/ci") / shard
artifacts_dir.mkdir(parents=True, exist_ok=True)
report_path = artifacts_dir / "fail_fast_report.md"

def run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    except subprocess.CalledProcessError as exc:
        return exc.output

sections = []
sections.append(f"# Fail-fast report — {shard}\n")
sections.append("## docker compose ps\n```\n" + run(["docker", "compose", "ps", "-a"]) + "\n```\n")
sections.append("## api logs\n```\n" + run(["docker", "compose", "logs", "--no-color", "--tail=300", "api"]) + "\n```\n")
sections.append("## worker logs\n```\n" + run(["docker", "compose", "logs", "--no-color", "--tail=300", "worker"]) + "\n```\n")
sections.append("## frontend logs\n```\n" + run(["docker", "compose", "logs", "--no-color", "--tail=300", "frontend"]) + "\n```\n")
sections.append("## edge-relay logs\n```\n" + run(["docker", "compose", "logs", "--no-color", "--tail=300", "edge-relay"]) + "\n```\n")

playwright_json = Path("artifacts/playwright") / shard / "results.json"
if playwright_json.exists():
    try:
        data = json.loads(playwright_json.read_text(encoding="utf-8"))
        payload = json.dumps(data, indent=2)
        sections.append("## Playwright JSON summary\n```json\n" + payload[:50000] + "\n```\n")
    except Exception as exc:
        sections.append(f"## Playwright JSON summary\nCould not parse results.json: {exc}\n")
else:
    sections.append(f"## Playwright JSON summary\nNo results.json found for shard `{shard}`.\n")

report_path.write_text("\n".join(sections), encoding="utf-8")
print(report_path)
