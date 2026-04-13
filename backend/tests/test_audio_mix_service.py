from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.audio.audio_mix_service import ensure_default_mix_profile


def test_ensure_default_mix_profile_creates_once():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    first = ensure_default_mix_profile(session)
    second = ensure_default_mix_profile(session)
    assert first.id == second.id
    assert second.display_name == "Default cinematic mix"
