from app.workers.celery_app import celery_app

@celery_app.task(name="app.workers.template_analytics_worker.run")
def run(template_pack_id: str):
    return {"status": "queued", "template_pack_id": template_pack_id}
