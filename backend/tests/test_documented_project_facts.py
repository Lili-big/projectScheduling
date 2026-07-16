from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402


README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
AGENT = (REPO_ROOT / "agent.md").read_text(encoding="utf-8")


def test_documented_modules_and_commands_exist() -> None:
    required_paths = [
        "backend/app/main.py",
        "backend/app/models.py",
        "backend/app/scenario.py",
        "backend/app/solver.py",
        "backend/app/girder_planning",
        "backend/app/services/plan_control_repository.py",
        "frontend/src/app/App.tsx",
        "frontend/src/features/girderPlanning",
        "frontend/src/features/planControl",
        "tools/demo-api-mirror/api.mts",
        "docs/architecture/module-map.md",
    ]
    for relative_path in required_paths:
        assert (REPO_ROOT / relative_path).exists(), relative_path
    for documented_path in (
        "backend/app/main.py",
        "backend/app/models.py",
        "backend/app/scenario.py",
        "backend/app/solver.py",
        "tools/demo-api-mirror/api.mts",
        "docs/architecture/module-map.md",
    ):
        assert documented_path in AGENT or documented_path in README

    scripts = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))["scripts"]
    assert {"build", "frontend:dev", "frontend:preview", "verify:architecture"} <= set(scripts)
    assert "uvicorn app.main:app" in README
    assert "pytest backend\\tests" in README


def test_documented_api_paths_are_live_and_route_count_is_current() -> None:
    implemented = {route.path for route in app.routes if route.path.startswith("/api")}
    operations = {
        (method, route.path)
        for route in app.routes
        if route.path.startswith("/api")
        for method in getattr(route, "methods", set())
        if method not in {"HEAD", "OPTIONS"}
    }
    documented = set(re.findall(r"`(?:GET|POST|PUT|PATCH|DELETE)\s+(/api/[^`\s]+)`", README + AGENT))
    assert len(operations) == 57
    assert documented <= implemented
    assert {
        "/api/demo-scenario",
        "/api/generate-schedule-input",
        "/api/solve-scenario",
        "/api/solve-min-resources",
        "/api/solve-resource-cost",
        "/api/compare-scenarios",
    } <= documented


def test_documented_environment_and_deployment_boundaries_match_configuration() -> None:
    template = (REPO_ROOT / ".local.env.example").read_text(encoding="utf-8")
    client = (REPO_ROOT / "frontend/src/api/client.ts").read_text(encoding="utf-8")
    bootstrap = (REPO_ROOT / "backend/app/bootstrap.py").read_text(encoding="utf-8")
    netlify = (REPO_ROOT / "netlify.toml").read_text(encoding="utf-8")

    assert "BRIDGE_IMPORT_LLM_PROVIDER" in template
    assert "PROCESS_NL_LLM_PROVIDER" in template
    assert "AI_RESOURCE_ASSISTANT_PROVIDER" in template
    assert "VITE_API_BASE_URL" in client and "VITE_API_BASE_URL" in README
    assert "SCHEDULER_CORS_ORIGINS" in bootstrap and "SCHEDULER_CORS_ORIGINS" in README
    assert 'publish = "frontend/dist"' in netlify
    assert "静态前端" in README and "不是正式 FastAPI 后端" in AGENT


def test_041_partial_status_is_not_presented_as_complete() -> None:
    tasks = (REPO_ROOT / "specs/041-girder-scheduling-integration/tasks.md").read_text(encoding="utf-8")
    completed = len(re.findall(r"^\s*- \[(?:x|X)\]\s+T\d+", tasks, flags=re.MULTILINE))
    total = len(re.findall(r"^\s*- \[(?: |x|X)\]\s+T\d+", tasks, flags=re.MULTILINE))
    assert (completed, total) == (74, 95)
    assert "74/95" in README and "74/95" in AGENT
    assert re.search(r"21\s*项.*未完成", README)
    assert re.search(r"21\s*项.*未完成", AGENT)
