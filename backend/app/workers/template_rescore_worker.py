from app.core.celery_app import celery_app
from app.workers.template_worker_common import db_context
from app.services.template_runtime_scoring import score_template, evaluate_memory

@celery_app.task(bind=True, name="app.workers.template_rescore_worker.run", max_retries=2)
def run(self, template_id: str):
    with db_context() as db:
        score = score_template(db, template_id)
        memory = evaluate_memory(db, template_id)
        return {"template_id": template_id, "final_priority_score": float(score.final_priority_score), "state": memory.state}
