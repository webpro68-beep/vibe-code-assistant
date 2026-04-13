from app.workers.celery_app import celery_app

@celery_app.task(name="app.workers.template_generation_worker.run")
def run(template_usage_run_id: str):
    return {"status": "queued", "template_usage_run_id": template_usage_run_id}
