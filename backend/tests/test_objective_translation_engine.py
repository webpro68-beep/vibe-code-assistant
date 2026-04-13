from app.services.strategy.objective_translation_engine import ObjectiveTranslationEngine


def test_launch_mode_prioritizes_launch_deadline():
    engine = ObjectiveTranslationEngine()
    profile = engine.translate(
        "launch_mode",
        [{"signal_type": "launch_calendar", "title": "Major launch", "is_active": True}],
    )
    assert profile["objective_stack"][1] == "launch_deadline"
    assert any("Launch signal active" in item for item in profile["rationale"])
