from __future__ import annotations
import uuid
from sqlalchemy.orm import Session
from app.models.veo_workspace import CharacterReferencePack, CharacterReferenceImage, VeoBatchRun, VeoBatchItem
from app.services.project_workspace_service import load_project, save_project
from app.services.script_preview_builder import build_preview_payload_from_text

def create_character_reference_pack(db: Session, payload: dict) -> CharacterReferencePack:
    row = CharacterReferencePack(
        id=uuid.uuid4(),
        pack_name=payload["pack_name"],
        owner_project_id=payload.get("owner_project_id"),
        identity_summary=payload.get("identity_summary"),
        appearance_lock_json=payload.get("appearance_lock_json") or {},
        prompt_lock_tokens=payload.get("prompt_lock_tokens") or [],
        negative_drift_tokens=payload.get("negative_drift_tokens") or [],
        metadata_json=payload.get("metadata_json") or {},
    )
    db.add(row); db.commit(); db.refresh(row)
    for image in payload.get("images", []):
        db.add(CharacterReferenceImage(
            id=uuid.uuid4(),
            character_pack_id=row.id,
            image_role=image.get("image_role", "hero"),
            image_url=image["image_url"],
            storage_key=image.get("storage_key"),
            metadata_json=image.get("metadata_json") or {},
        ))
    db.commit()
    return row

def list_character_reference_packs(db: Session) -> list[dict]:
    packs = db.query(CharacterReferencePack).all()
    items = []
    for pack in packs:
        images = db.query(CharacterReferenceImage).filter(CharacterReferenceImage.character_pack_id == pack.id).all()
        items.append({
            "id": str(pack.id),
            "pack_name": pack.pack_name,
            "owner_project_id": str(pack.owner_project_id) if pack.owner_project_id else None,
            "identity_summary": pack.identity_summary,
            "appearance_lock_json": pack.appearance_lock_json,
            "prompt_lock_tokens": pack.prompt_lock_tokens,
            "negative_drift_tokens": pack.negative_drift_tokens,
            "images": [
                {"id": str(img.id), "image_role": img.image_role, "image_url": img.image_url, "storage_key": img.storage_key, "metadata_json": img.metadata_json}
                for img in images
            ],
        })
    return items

def attach_veo_config_to_project(project_id: str, payload: dict) -> dict:
    project = load_project(project_id)
    if project is None:
        raise ValueError("Project not found")
    project["provider"] = "veo"
    project["provider_label"] = "Veo 3.1"
    project["veo_config"] = {
        "provider_model": payload.get("provider_model", "veo-3.1-generate-001"),
        "veo_mode": payload.get("veo_mode", "text_to_video"),
        "character_reference_pack_id": payload.get("character_reference_pack_id"),
        "apply_character_lock_to_all_scenes": bool(payload.get("apply_character_lock_to_all_scenes", False)),
        "use_preview_reference_mode": bool(payload.get("use_preview_reference_mode", False)),
        "sound_generation": bool(payload.get("sound_generation", False)),
    }
    if payload.get("scene_inputs"):
        scene_map = {int(s["scene_index"]): s for s in payload["scene_inputs"]}
        for scene in project.get("scenes", []):
            cfg = scene_map.get(int(scene.get("scene_index")))
            if not cfg:
                continue
            scene["provider_mode"] = payload.get("veo_mode", "text_to_video")
            scene["start_image_url"] = cfg.get("start_image_url")
            scene["end_image_url"] = cfg.get("end_image_url")
            scene["character_reference_image_urls"] = cfg.get("character_reference_image_urls") or []
    save_project(project)
    return project

def create_veo_batch_run(db: Session, payload: dict) -> dict:
    batch = VeoBatchRun(
        id=uuid.uuid4(),
        batch_name=payload["batch_name"],
        provider_model=payload.get("provider_model", "veo-3.1-generate-001"),
        veo_mode=payload.get("veo_mode", "text_to_video"),
        aspect_ratio=payload.get("aspect_ratio", "9:16"),
        target_platform=payload.get("target_platform", "shorts"),
        status="queued",
        total_scripts=len(payload.get("scripts", [])),
        request_payload_json=payload,
    )
    db.add(batch); db.commit(); db.refresh(batch)

    created_projects = []
    for idx, item in enumerate(payload.get("scripts", []), start=1):
        preview = build_preview_payload_from_text(
            script_text=item["script_text"],
            aspect_ratio=batch.aspect_ratio,
            target_platform=batch.target_platform,
            style_preset=item.get("style_preset"),
            source_mode="script_upload",
        )
        project_id = str(uuid.uuid4())
        project = {
            "id": project_id,
            "name": item.get("name") or f"{batch.batch_name} #{idx}",
            "idea": item.get("idea") or "Batch Veo project",
            "target_platform": batch.target_platform,
            "format": batch.aspect_ratio,
            "style_preset": item.get("style_preset"),
            "status": "ready_to_render",
            "source_mode": "script_upload",
            "script_text": preview["script_text"],
            "scenes": preview["scenes"],
            "subtitle_segments": preview["subtitle_segments"],
            "original_filename": None,
            "is_template_source": True,
            "template_extracted": False,
            "template_extract_queued": False,
            "template_source_locked": False,
            "provider": "veo",
            "provider_label": "Veo 3.1",
            "veo_config": {
                "provider_model": batch.provider_model,
                "veo_mode": batch.veo_mode,
                "character_reference_pack_id": payload.get("character_reference_pack_id"),
                "apply_character_lock_to_all_scenes": bool(payload.get("apply_character_lock_to_all_scenes", False)),
                "use_preview_reference_mode": bool(payload.get("use_preview_reference_mode", False)),
                "sound_generation": bool(payload.get("sound_generation", False)),
            },
        }
        if payload.get("scene_inputs"):
            scene_input_list = payload["scene_inputs"]
            for scene in project["scenes"]:
                source = next((x for x in scene_input_list if int(x.get("scene_index", -1)) == int(scene["scene_index"])), None)
                if source:
                    scene["provider_mode"] = batch.veo_mode
                    scene["start_image_url"] = source.get("start_image_url")
                    scene["end_image_url"] = source.get("end_image_url")
                    scene["character_reference_image_urls"] = source.get("character_reference_image_urls") or []
        save_project(project)
        db.add(VeoBatchItem(
            id=uuid.uuid4(),
            veo_batch_run_id=batch.id,
            project_id=project_id,
            script_label=item.get("name") or f"script-{idx}",
            script_text=item["script_text"],
            status="ready_to_render",
            result_json={"project_id": project_id},
        ))
        created_projects.append({"project_id": project_id, "name": project["name"]})
    db.commit()
    return {
        "veo_batch_run_id": str(batch.id),
        "status": batch.status,
        "total_scripts": batch.total_scripts,
        "projects": created_projects,
    }

def get_veo_batch_run(db: Session, batch_id: str) -> dict | None:
    batch = db.query(VeoBatchRun).filter(VeoBatchRun.id == batch_id).first()
    if batch is None:
        return None
    items = db.query(VeoBatchItem).filter(VeoBatchItem.veo_batch_run_id == batch.id).all()
    return {
        "id": str(batch.id),
        "batch_name": batch.batch_name,
        "provider_model": batch.provider_model,
        "veo_mode": batch.veo_mode,
        "aspect_ratio": batch.aspect_ratio,
        "target_platform": batch.target_platform,
        "status": batch.status,
        "total_scripts": batch.total_scripts,
        "completed_scripts": batch.completed_scripts,
        "failed_scripts": batch.failed_scripts,
        "items": [
            {
                "id": str(i.id),
                "project_id": str(i.project_id) if i.project_id else None,
                "script_label": i.script_label,
                "status": i.status,
                "result_json": i.result_json,
            }
            for i in items
        ],
    }
