from app.core.celery_app import celery_app
from app.workers.template_worker_common import db_context
from app.services.template_feedback_loop import process_project_completion_feedback

@celery_app.task(bind=True, name="app.workers.template_feedback_worker.run", max_retries=2)
def run(self, project_id: str):
    with db_context() as db:
        return process_project_completion_feedback(db, project_id)
