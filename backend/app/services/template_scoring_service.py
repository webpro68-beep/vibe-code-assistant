class TemplateScoringService:
    def score_extraction(self, source_project: dict, extracted: dict) -> dict:
        return {
            "reusability_score": 90.0,
            "performance_score": 80.0,
            "signals": {
                "has_style": bool(extracted.get("style")),
                "has_blueprint": bool(extracted.get("scene_blueprint")),
                "has_components": len(extracted.get("components", [])),
            },
        }
