from app.core.celery_app import celery_app
from app.workers.template_worker_common import db_context

@celery_app.task(bind=True, name="app.workers.template_generation_worker.run", max_retries=3)
def run(self, template_usage_run_id: str):
    with db_context() as db:
        return {"status": "queued", "template_usage_run_id": template_usage_run_id}
