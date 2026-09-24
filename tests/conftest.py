from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'reem-test.db').as_posix()}")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("AI_API_KEY", "")
    from app.config import get_settings
    from app.db.database import reset_engine
    from app.services.cache import policy_cache
    from app.services.payment import payment_service
    get_settings.cache_clear()
    reset_engine()
    policy_cache.clear()
    payment_service.configure_failures(0)
    payment_service.paid_ids.clear()
    payment_service.breaker.reset()

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()
    reset_engine()
