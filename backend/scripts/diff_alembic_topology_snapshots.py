#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys

def _load_json(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_diff(before: dict, after: dict) -> dict:
    before_revs = set(before.get('revisions', {}).keys())
    after_revs = set(after.get('revisions', {}).keys())
    before_heads = set(before.get('heads', []))
    after_heads = set(after.get('heads', []))
    return {
        'before_git_sha': before.get('git_sha', ''),
        'after_git_sha': after.get('git_sha', ''),
        'before_heads': sorted(before_heads),
        'after_heads': sorted(after_heads),
        'added_revisions': sorted(after_revs - before_revs),
        'removed_revisions': sorted(before_revs - after_revs),
        'new_heads': sorted(after_heads - before_heads),
        'removed_heads': sorted(before_heads - after_heads),
    }

def main() -> int:
    if len(sys.argv) < 3:
        print('Usage: diff_alembic_topology_snapshots.py <before.json> <after.json> [output_json]')
        return 2
    before = _load_json(sys.argv[1]); after = _load_json(sys.argv[2])
    out = sys.argv[3] if len(sys.argv) > 3 else 'alembic_topology_diff.json'
    diff = build_diff(before, after)
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f: json.dump(diff, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f'Wrote diff JSON: {out}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
