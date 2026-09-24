"""Start FastAPI + Flask together."""

from __future__ import annotations

import threading
import time

import uvicorn

from app.config import get_settings


def _api() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level="info",
    )


def _ui() -> None:
    from flask_ui.app import create_app

    settings = get_settings()
    app = create_app()
    app.run(host=settings.flask_host, port=settings.flask_port, debug=False, use_reloader=False)


if __name__ == "__main__":
    settings = get_settings()
    api_thread = threading.Thread(target=_api, daemon=True)
    api_thread.start()
    time.sleep(1.2)
    print(f"FastAPI  http://{settings.api_host}:{settings.api_port}/docs")
    print(f"Flask UI http://{settings.flask_host}:{settings.flask_port}/")
    _ui()
