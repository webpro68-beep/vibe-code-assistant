from app.workers.celery_app import celery_app

@celery_app.task(name="app.workers.template_batch_worker.run")
def run(template_clone_job_id: str):
    return {"status": "queued", "template_clone_job_id": template_clone_job_id}
