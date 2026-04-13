from app.core.celery_app import celery_app
from app.workers.template_worker_common import db_context
from app.services.template_analytics_service import TemplateAnalyticsService

@celery_app.task(bind=True, name="app.workers.template_analytics_worker.run", max_retries=1)
def run(self, template_pack_id: str):
    with db_context() as db:
        return {"status": "completed", "analytics": TemplateAnalyticsService().get_template_analytics(template_pack_id)}
