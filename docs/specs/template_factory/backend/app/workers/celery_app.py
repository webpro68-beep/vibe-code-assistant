from celery import Celery
celery_app = Celery("template_factory")
celery_app.conf.broker_url = "redis://localhost:6379/0"
celery_app.conf.result_backend = "redis://localhost:6379/1"
