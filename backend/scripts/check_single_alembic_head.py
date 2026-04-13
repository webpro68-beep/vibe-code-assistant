#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, Iterable, List, Set, Tuple

from alembic.config import Config
from alembic.script import ScriptDirectory


@dataclass
class RevisionNode:
    revision: str
    down_revisions: List[str]
    is_base: bool = False
    is_head: bool = False


@dataclass
class ValidationResult:
    ok: bool
    head_count: int
    heads: List[str]
    bases: List[str]
    branchpoints: Dict[str, List[str]]
    orphan_revisions: List[str]
    unreachable_from_head: List[str]
    unreachable_from_any_base: List[str]
    unexpected_branchpoints: Dict[str, List[str]]
    expected_bases_mismatch: Dict[str, List[str]]
    total_revisions: int
    topo_order_sample: List[str]
    message: str


def _stderr(msg: str) -> None:
    print(msg, file=sys.stderr)


def _parse_csv_env(name: str) -> Set[str]:
    raw = os.getenv(name, '').strip()
    if not raw:
        return set()
    return {item.strip() for item in raw.split(',') if item.strip()}


def _load_script_directory() -> ScriptDirectory:
    config_path = os.getenv('ALEMBIC_CONFIG', 'alembic.ini')
    cfg = Config(config_path)
    script_location = os.getenv('ALEMBIC_SCRIPT_LOCATION', '').strip()
    if script_location:
        cfg.set_main_option('script_location', script_location)
    return ScriptDirectory.from_config(cfg)


def _normalize_down_revisions(rev) -> List[str]:
    dr = rev.down_revision
    if dr is None:
        return []
    if isinstance(dr, (tuple, list)):
        return [x for x in dr if x]
    return [dr]


def _build_graph(script: ScriptDirectory) -> Tuple[Dict[str, RevisionNode], Dict[str, List[str]], Dict[str, List[str]]]:
    nodes: Dict[str, RevisionNode] = {}
    parents: Dict[str, List[str]] = {}
    children: Dict[str, List[str]] = defaultdict(list)
    revisions = list(script.walk_revisions(base='base', head='heads'))
    head_ids = {rev.revision for rev in script.get_revisions('heads')}
    base_ids = {rev.revision for rev in script.get_bases()}
    for rev in revisions:
        down_revs = _normalize_down_revisions(rev)
        nodes[rev.revision] = RevisionNode(
            revision=rev.revision,
            down_revisions=down_revs,
            is_base=rev.revision in base_ids or len(down_revs) == 0,
            is_head=rev.revision in head_ids,
        )
        parents[rev.revision] = down_revs
    for child, down_revs in parents.items():
        for parent in down_revs:
            children[parent].append(child)
    for key in children:
        children[key] = sorted(set(children[key]))
    return nodes, parents, children


def _collect_bases(nodes: Dict[str, RevisionNode]) -> List[str]:
    return sorted([rev_id for rev_id, node in nodes.items() if node.is_base])


def _collect_heads(nodes: Dict[str, RevisionNode]) -> List[str]:
    return sorted([rev_id for rev_id, node in nodes.items() if node.is_head])


def _reachable_from_starts(starts: Iterable[str], children: Dict[str, List[str]]) -> Set[str]:
    seen: Set[str] = set()
    queue = deque(starts)
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        for nxt in children.get(current, []):
            if nxt not in seen:
                queue.append(nxt)
    return seen


def _reverse_reachable_from_head(heads: Iterable[str], parents: Dict[str, List[str]]) -> Set[str]:
    seen: Set[str] = set()
    queue = deque(heads)
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        for prev in parents.get(current, []):
            if prev not in seen:
                queue.append(prev)
    return seen


def _topological_order(nodes: Dict[str, RevisionNode], parents: Dict[str, List[str]], children: Dict[str, List[str]]) -> List[str]:
    indegree = {rev_id: len(parents.get(rev_id, [])) for rev_id in nodes.keys()}
    queue = deque(sorted([rev_id for rev_id, degree in indegree.items() if degree == 0]))
    order: List[str] = []
    while queue:
        current = queue.popleft()
        order.append(current)
        for nxt in children.get(current, []):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    return order


def validate_graph() -> ValidationResult:
    script = _load_script_directory()
    nodes, parents, children = _build_graph(script)
    if not nodes:
        return ValidationResult(False,0,[],[],{},[],[],[],{}, {},0,[], 'No Alembic revisions found.')
    heads = _collect_heads(nodes)
    bases = _collect_bases(nodes)
    branchpoints = {rev_id: child_ids for rev_id, child_ids in children.items() if len(child_ids) > 1}
    allowed_branchpoints = _parse_csv_env('ALEMBIC_ALLOWED_BRANCHPOINTS')
    unexpected_branchpoints = {rev_id: child_ids for rev_id, child_ids in branchpoints.items() if rev_id not in allowed_branchpoints}
    reachable_from_bases = _reachable_from_starts(bases, children)
    reachable_reverse_from_head = _reverse_reachable_from_head(heads, parents)
    unreachable_from_any_base = sorted(set(nodes.keys()) - reachable_from_bases)
    unreachable_from_head = sorted(set(nodes.keys()) - reachable_reverse_from_head)
    orphan_revisions = sorted([rev_id for rev_id, node in nodes.items() if (not node.is_base and rev_id not in reachable_from_bases)])
    expected_bases = _parse_csv_env('ALEMBIC_EXPECTED_BASES')
    expected_bases_mismatch: Dict[str, List[str]] = {}
    if expected_bases:
        missing = sorted(expected_bases - set(bases))
        unexpected = sorted(set(bases) - expected_bases)
        if missing or unexpected:
            expected_bases_mismatch = {'missing_expected_bases': missing, 'unexpected_bases': unexpected}
    topo_order = _topological_order(nodes, parents, children)
    if len(topo_order) != len(nodes):
        return ValidationResult(False, len(heads), heads, bases, branchpoints, orphan_revisions, unreachable_from_head, unreachable_from_any_base, unexpected_branchpoints, expected_bases_mismatch, len(nodes), topo_order[:20], 'Topological sort did not cover all revisions. Graph may be inconsistent.')
    failures: List[str] = []
    if len(heads) != 1:
        failures.append(f'Expected exactly 1 head, found {len(heads)}: {heads}')
    if orphan_revisions:
        failures.append(f'Found orphan revisions not reachable from any base: {orphan_revisions}')
    if unreachable_from_any_base:
        failures.append(f'Found revisions unreachable from any base traversal: {unreachable_from_any_base}')
    if len(heads) == 1 and unreachable_from_head:
        failures.append(f'Found revisions that cannot reach the single head {heads[0]}: {unreachable_from_head}')
    if unexpected_branchpoints:
        failures.append(f'Found unexpected branch points: {json.dumps(unexpected_branchpoints, sort_keys=True)}')
    if expected_bases_mismatch:
        failures.append(f'Base revisions do not match expected set: {json.dumps(expected_bases_mismatch, sort_keys=True)}')
    ok = len(failures) == 0
    message = 'Graph validation passed.' if ok else ' | '.join(failures)
    return ValidationResult(ok, len(heads), heads, bases, branchpoints, orphan_revisions, unreachable_from_head, unreachable_from_any_base, unexpected_branchpoints, expected_bases_mismatch, len(nodes), topo_order[:20], message)


def _print_human_summary(result: ValidationResult) -> None:
    print('=== Alembic Lineage Validation Summary ===')
    print(f'ok: {result.ok}')
    print(f'total_revisions: {result.total_revisions}')
    print(f'head_count: {result.head_count}')
    print(f'heads: {result.heads}')
    print(f'bases: {result.bases}')
    print(f'branchpoints: {json.dumps(result.branchpoints, sort_keys=True)}')
    print(f'unexpected_branchpoints: {json.dumps(result.unexpected_branchpoints, sort_keys=True)}')
    print(f'orphan_revisions: {result.orphan_revisions}')
    print(f'unreachable_from_any_base: {result.unreachable_from_any_base}')
    print(f'unreachable_from_head: {result.unreachable_from_head}')
    print(f'expected_bases_mismatch: {json.dumps(result.expected_bases_mismatch, sort_keys=True)}')
    print(f'topo_order_sample: {result.topo_order_sample}')
    print(f'message: {result.message}')


def main() -> int:
    try:
        result = validate_graph()
        _print_human_summary(result)
        if os.getenv('GITHUB_ACTIONS') == 'true':
            if result.ok:
                print('::notice title=Alembic lineage validator::Graph validation passed')
            else:
                safe_msg = result.message.replace('
', ' ')
                print(f'::error title=Alembic lineage validator::{safe_msg}')
        return 0 if result.ok else 1
    except Exception as exc:
        _stderr('Alembic lineage validator crashed.')
        _stderr(f'{type(exc).__name__}: {exc}')
        if os.getenv('GITHUB_ACTIONS') == 'true':
            safe_msg = f'{type(exc).__name__}: {exc}'.replace('
', ' ')
            print(f'::error title=Alembic lineage validator crash::{safe_msg}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
