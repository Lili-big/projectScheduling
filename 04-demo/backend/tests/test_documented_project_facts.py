from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "04-demo/backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402


README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
AGENT = (REPO_ROOT / "agent.md").read_text(encoding="utf-8")


def test_documented_modules_and_commands_exist() -> None:
    required_paths = [
        "04-demo/backend/app/main.py",
        "04-demo/backend/app/models.py",
        "04-demo/backend/app/scenario.py",
        "04-demo/backend/app/solver.py",
        "04-demo/backend/app/girder_planning",
        "04-demo/backend/app/services/plan_control_repository.py",
        "04-demo/frontend/src/app/App.tsx",
        "04-demo/frontend/src/features/girderPlanning",
        "04-demo/frontend/src/features/planControl",
        "04-demo/tools/demo-api-mirror/api.mts",
        "00-governance/architecture/module-map.md",
    ]
    for relative_path in required_paths:
        assert (REPO_ROOT / relative_path).exists(), relative_path
    for documented_path in (
        "04-demo/backend/app/main.py",
        "04-demo/backend/app/models.py",
        "04-demo/backend/app/scenario.py",
        "04-demo/backend/app/solver.py",
        "04-demo/tools/demo-api-mirror/api.mts",
        "00-governance/architecture/module-map.md",
    ):
        assert documented_path in AGENT or documented_path in README

    scripts = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))["scripts"]
    assert {"build", "frontend:dev", "frontend:preview", "verify:architecture"} <= set(scripts)
    assert "uvicorn app.main:app" in README
    assert "pytest 04-demo\\backend\\tests" in README


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
    client = (REPO_ROOT / "04-demo/frontend/src/api/client.ts").read_text(encoding="utf-8")
    bootstrap = (REPO_ROOT / "04-demo/backend/app/bootstrap.py").read_text(encoding="utf-8")
    netlify = (REPO_ROOT / "netlify.toml").read_text(encoding="utf-8")

    assert "BRIDGE_IMPORT_LLM_PROVIDER" in template
    assert "PROCESS_NL_LLM_PROVIDER" in template
    assert "AI_RESOURCE_ASSISTANT_PROVIDER" in template
    assert "VITE_API_BASE_URL" in client and "VITE_API_BASE_URL" in README
    assert "SCHEDULER_CORS_ORIGINS" in bootstrap and "SCHEDULER_CORS_ORIGINS" in README
    assert 'publish = "04-demo/frontend/dist"' in netlify
    assert "静态前端" in README and "不是正式 FastAPI 后端" in AGENT


def test_041_partial_status_is_not_presented_as_complete() -> None:
    tasks = (REPO_ROOT / "03-requirements/specs/041-girder-scheduling-integration/tasks.md").read_text(encoding="utf-8")
    completed = len(re.findall(r"^\s*- \[(?:x|X)\]\s+T\d+", tasks, flags=re.MULTILINE))
    total = len(re.findall(r"^\s*- \[(?: |x|X)\]\s+T\d+", tasks, flags=re.MULTILINE))
    assert (completed, total) == (74, 95)
    assert "74/95" in README
    assert re.search(r"21\s*项.*未完成", README)
    assert "74/95" not in AGENT
