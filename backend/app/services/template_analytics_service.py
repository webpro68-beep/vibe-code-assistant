class TemplateAnalyticsService:
    def get_template_analytics(self, template_pack_id):
        return {
            "template_pack_id": str(template_pack_id),
            "usage_count": 0,
            "render_success_rate": 0.0,
            "upload_success_rate": 0.0,
            "avg_retry_count": 0.0,
            "avg_generation_duration_sec": 0.0,
            "trend_json": {},
        }
