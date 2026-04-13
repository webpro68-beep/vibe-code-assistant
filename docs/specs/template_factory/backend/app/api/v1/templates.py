from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import get_db
from app.repositories.template_factory_repo import TemplateFactoryRepository
from app.schemas.template_factory import (
    TemplateExtractRequest, TemplateGenerateRequest, TemplateBatchGenerateRequest,
    TemplatePackCreate, TemplateVersionCreate,
)
from app.services.template_extraction_service import TemplateExtractionService
from app.services.template_library_service import TemplateLibraryService
from app.services.template_generation_service import TemplateGenerationService
from app.services.template_batch_service import TemplateBatchService
from app.services.template_analytics_service import TemplateAnalyticsService

router = APIRouter(prefix="/templates", tags=["templates"])

@router.post("/extract")
def extract_template(payload: TemplateExtractRequest, db=Depends(get_db)):
    repo = TemplateFactoryRepository(db)
    extraction = TemplateExtractionService(repo).queue_extraction(payload.source_project_id, payload.auto_publish)
    return {"id": str(extraction.id), "status": extraction.status}

@router.get("/extractions/{extraction_id}")
def get_extraction(extraction_id: str, db=Depends(get_db)):
    repo = TemplateFactoryRepository(db)
    extraction = repo.get_extraction(extraction_id)
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found")
    return extraction

@router.get("")
def list_templates(status: str | None = None, db=Depends(get_db)):
    repo = TemplateFactoryRepository(db)
    rows = TemplateLibraryService(repo).list_templates(status=status)
    return {"items": rows}

@router.post("")
def create_template(payload: TemplatePackCreate, db=Depends(get_db)):
    repo = TemplateFactoryRepository(db)
    return TemplateLibraryService(repo).create_template(payload.model_dump())

@router.get("/{template_id}")
def get_template(template_id: str, db=Depends(get_db)):
    repo = TemplateFactoryRepository(db)
    pack = repo.get_template_pack(template_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Template not found")
    version = repo.get_active_version(template_id)
    components = repo.list_components(version.id) if version else []
    return {"template": pack, "active_version": version, "components": components}

@router.post("/{template_id}/publish")
def publish_template(template_id: str, db=Depends(get_db)):
    repo = TemplateFactoryRepository(db)
    pack = repo.get_template_pack(template_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Template not found")
    pack.status = "published"
    repo.db.commit()
    return {"status": "published"}

@router.post("/{template_id}/archive")
def archive_template(template_id: str, db=Depends(get_db)):
    repo = TemplateFactoryRepository(db)
    pack = repo.get_template_pack(template_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Template not found")
    pack.status = "archived"
    repo.db.commit()
    return {"status": "archived"}

@router.post("/{template_id}/versions")
def create_version(template_id: str, payload: TemplateVersionCreate, db=Depends(get_db)):
    repo = TemplateFactoryRepository(db)
    return TemplateLibraryService(repo).create_version(template_id, payload.model_dump())

@router.post("/{template_id}/versions/{version_id}/activate")
def activate_version(template_id: str, version_id: str, db=Depends(get_db)):
    repo = TemplateFactoryRepository(db)
    repo.activate_template_version(template_id, version_id)
    return {"status": "activated"}

@router.post("/{template_id}/generate")
def generate_template(template_id: str, payload: TemplateGenerateRequest, db=Depends(get_db)):
    repo = TemplateFactoryRepository(db)
    run = TemplateGenerationService(repo).generate(template_id, payload.model_dump())
    return {"template_usage_run_id": str(run.id), "project_id": str(run.project_id), "status": run.status}

@router.post("/{template_id}/batch-generate")
def batch_generate(template_id: str, payload: TemplateBatchGenerateRequest, db=Depends(get_db)):
    repo = TemplateFactoryRepository(db)
    clone_job = TemplateBatchService(repo).queue_batch(template_id, payload.model_dump())
    return {"template_clone_job_id": str(clone_job.id), "status": clone_job.status, "count": len(payload.items)}

@router.get("/clone-jobs/{clone_job_id}")
def get_clone_job(clone_job_id: str, db=Depends(get_db)):
    repo = TemplateFactoryRepository(db)
    job = repo.get_clone_job(clone_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Clone job not found")
    return job

@router.get("/{template_id}/analytics")
def get_analytics(template_id: str, db=Depends(get_db)):
    return TemplateAnalyticsService().get_template_analytics(template_id)
