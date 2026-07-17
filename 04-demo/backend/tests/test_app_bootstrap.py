from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app.bootstrap as bootstrap  # noqa: E402
from asgi_client import json_request, request  # noqa: E402


def test_create_app_registers_all_api_operations_and_cors() -> None:
    app = bootstrap.create_app()
    operations = [
        (method, route.path)
        for route in app.routes
        if route.path.startswith("/api")
        for method in getattr(route, "methods", set())
        if method not in {"HEAD", "OPTIONS"}
    ]
    assert len(operations) == 57
    assert any(middleware.cls.__name__ == "CORSMiddleware" for middleware in app.user_middleware)
    status, payload = json_request(app, "GET", "/api/health")
    assert status == 200
    assert payload == {"status": "ok"}


def test_create_app_serves_assets_files_and_spa_fallback(tmp_path: Path, monkeypatch) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<main>scheduler</main>", encoding="utf-8")
    (dist / "robots.txt").write_text("demo", encoding="utf-8")
    (dist / "assets/app.js").write_text("export {};", encoding="utf-8")
    monkeypatch.setattr(bootstrap, "DIST_DIR", dist)

    app = bootstrap.create_app()
    assert request(app, "GET", "/assets/app.js")[0] == 200
    assert request(app, "GET", "/robots.txt")[2].decode("utf-8") == "demo"
    assert "scheduler" in request(app, "GET", "/workspace/deep-link")[2].decode("utf-8")
