#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List
from alembic.config import Config
from alembic.script import ScriptDirectory

@dataclass
class RevisionRecord:
    revision: str
    down_revisions: List[str]
    doc: str
    is_head: bool
    is_base: bool
    file_path: str

def _load_script_directory() -> ScriptDirectory:
    config_path = os.getenv('ALEMBIC_CONFIG', 'alembic.ini')
    cfg = Config(config_path)
    script_location = os.getenv('ALEMBIC_SCRIPT_LOCATION', '').strip()
    if script_location:
        cfg.set_main_option('script_location', script_location)
    return ScriptDirectory.from_config(cfg)

def _normalize_down_revisions(rev) -> List[str]:
    dr = rev.down_revision
    if dr is None: return []
    if isinstance(dr, (tuple, list)): return [x for x in dr if x]
    return [dr]

def _topological_order(nodes, parents, children):
    indegree = {node_id: len(parents.get(node_id, [])) for node_id in nodes}
    queue = deque(sorted([node_id for node_id, d in indegree.items() if d == 0]))
    order = []
    while queue:
        current = queue.popleft(); order.append(current)
        for nxt in children.get(current, []):
            indegree[nxt] -= 1
            if indegree[nxt] == 0: queue.append(nxt)
    return order

def build_snapshot() -> dict:
    script = _load_script_directory()
    revisions = list(script.walk_revisions(base='base', head='heads'))
    head_ids = {rev.revision for rev in script.get_revisions('heads')}
    base_ids = {rev.revision for rev in script.get_bases()}
    nodes, parents, children = {}, {}, defaultdict(list)
    for rev in revisions:
        down_revisions = _normalize_down_revisions(rev)
        record = RevisionRecord(revision=rev.revision, down_revisions=down_revisions, doc=(rev.doc or '').strip(), is_head=rev.revision in head_ids, is_base=(rev.revision in base_ids) or len(down_revisions) == 0, file_path=getattr(rev,'path','') or '')
        nodes[rev.revision]=record; parents[rev.revision]=down_revisions
    for child, parent_ids in parents.items():
        for parent in parent_ids: children[parent].append(child)
    for parent in list(children.keys()): children[parent]=sorted(set(children[parent]))
    topo_order=_topological_order(nodes, parents, children)
    branchpoints={node_id: child_ids for node_id, child_ids in children.items() if len(child_ids) > 1}
    merge_nodes={node_id: parent_ids for node_id, parent_ids in parents.items() if len(parent_ids) > 1}
    return {'schema_version':1,'generated_at_utc':datetime.now(timezone.utc).isoformat(),'git_sha':os.getenv('GITHUB_SHA','').strip(),'git_ref':os.getenv('GITHUB_REF','').strip(),'git_event_name':os.getenv('GITHUB_EVENT_NAME','').strip(),'total_revisions':len(nodes),'heads':sorted(head_ids),'bases':sorted([node_id for node_id, node in nodes.items() if node.is_base]),'branchpoints':branchpoints,'merge_nodes':merge_nodes,'topological_order':topo_order,'revisions':{node_id: asdict(record) for node_id, record in sorted(nodes.items(), key=lambda item: item[0])},'edges':sorted([{'from_revision': parent, 'to_revision': child} for child, parent_ids in parents.items() for parent in parent_ids], key=lambda x: (x['from_revision'], x['to_revision']))}

def main() -> int:
    output_path = sys.argv[1] if len(sys.argv) > 1 else 'alembic_topology_snapshot.json'
    snapshot = build_snapshot(); os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path,'w',encoding='utf-8') as f: json.dump(snapshot, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f'Wrote topology snapshot to {output_path}')
    print(f"heads={snapshot['heads']}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
