from app.core.celery_app import celery_app
from app.workers.template_worker_common import db_context
from app.repositories.template_factory_repo import TemplateFactoryRepository
from app.services.template_extraction_service import TemplateExtractionService

@celery_app.task(bind=True, name="app.workers.template_extraction_worker.run", max_retries=3)
def run(self, extraction_id: str):
    with db_context() as db:
        repo = TemplateFactoryRepository(db)
        extraction = repo.get_extraction(extraction_id)
        if extraction is None:
            return {"status": "missing", "extraction_id": extraction_id}
                result = TemplateExtractionService(repo).perform_extraction(extraction_id)
        return {"status": "completed", "extraction_id": extraction_id, "template_pack_id": str(result["template_pack"].id)}
