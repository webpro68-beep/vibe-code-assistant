from __future__ import annotations
import json
from pathlib import Path

PROJECT_STORAGE_DIR = Path("storage/projects")
PROJECT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

def _project_dir(project_id: str) -> Path:
    return PROJECT_STORAGE_DIR / project_id

def load_project(project_id: str) -> dict | None:
    path = _project_dir(project_id) / "project.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

def save_project(project: dict) -> dict:
    project_id = project["id"]
    pdir = _project_dir(project_id)
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "project.json").write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    return project

def update_project(project_id: str, **updates) -> dict | None:
    project = load_project(project_id)
    if project is None:
        return None
    project.update(updates)
    return save_project(project)

def list_projects() -> list[dict]:
    items = []
    for p in PROJECT_STORAGE_DIR.glob("*/project.json"):
        try:
            items.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    items.sort(key=lambda x: x.get("id", ""))
    return items
