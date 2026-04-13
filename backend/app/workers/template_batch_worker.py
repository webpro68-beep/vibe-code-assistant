from app.core.celery_app import celery_app
from app.workers.template_worker_common import db_context

@celery_app.task(bind=True, name="app.workers.template_batch_worker.run", max_retries=2)
def run(self, template_clone_job_id: str):
    with db_context() as db:
        return {"status": "queued", "template_clone_job_id": template_clone_job_id}
