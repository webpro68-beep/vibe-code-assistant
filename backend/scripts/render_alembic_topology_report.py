#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from html import escape

def _load_json(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main() -> int:
    if len(sys.argv) < 3:
        print('Usage: render_alembic_topology_report.py <snapshot.json> <output.html>')
        return 2
    snapshot = _load_json(sys.argv[1])
    html = f"""<!doctype html><html><head><meta charset='utf-8'><title>Alembic Topology Report</title><style>body{{font-family:Arial,sans-serif;margin:32px}}pre{{background:#f6f8fa;padding:16px;overflow:auto}}.k{{font-weight:bold}}</style></head><body><h1>Alembic Topology Report</h1><p><span class='k'>Heads:</span> {escape(json.dumps(snapshot.get('heads', [])))}</p><p><span class='k'>Bases:</span> {escape(json.dumps(snapshot.get('bases', [])))}</p><p><span class='k'>Total revisions:</span> {snapshot.get('total_revisions', 0)}</p><h2>Raw Snapshot</h2><pre>{escape(json.dumps(snapshot, ensure_ascii=False, indent=2))}</pre></body></html>"""
    with open(sys.argv[2], 'w', encoding='utf-8') as f: f.write(html)
    print(f'Wrote HTML report: {sys.argv[2]}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
