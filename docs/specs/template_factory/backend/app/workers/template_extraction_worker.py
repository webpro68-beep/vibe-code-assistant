from app.workers.celery_app import celery_app

@celery_app.task(name="app.workers.template_extraction_worker.run")
def run(extraction_id: str):
    return {"status": "queued", "extraction_id": extraction_id}
