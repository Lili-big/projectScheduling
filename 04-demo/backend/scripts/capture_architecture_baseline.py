"""Capture the public backend contract before/after architecture migrations.

The output is intentionally deterministic so it can be committed as a fixture and
compared without depending on timestamps or machine-specific paths.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = BACKEND_ROOT / "tests" / "fixtures" / "architecture" / "backend-baseline.json"
PUBLIC_MODULES = ("app.models", "app.scenario", "app.solver")


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted(_jsonable(item) for item in value)
    return value


def _digest(value: Any) -> str:
    encoded = json.dumps(_jsonable(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _model_dump(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


def _model_schema(model: type[BaseModel]) -> dict[str, Any]:
    if hasattr(model, "model_json_schema"):
        return model.model_json_schema()
    return model.schema()


def _route_manifest(app: Any) -> list[dict[str, Any]]:
    openapi = app.openapi()
    routes: list[dict[str, Any]] = []
    for path, operations in sorted(openapi.get("paths", {}).items()):
        if not path.startswith("/api"):
            continue
        for method, operation in sorted(operations.items()):
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            request_schema = (
                operation.get("requestBody", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema")
            )
            responses: dict[str, Any] = {}
            for status, response in sorted(operation.get("responses", {}).items()):
                content = response.get("content", {}) if isinstance(response, dict) else {}
                responses[status] = {
                    "description": response.get("description") if isinstance(response, dict) else None,
                    "json_schema": content.get("application/json", {}).get("schema"),
                }
            routes.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "operation_id": operation.get("operationId"),
                    "request_schema": request_schema,
                    "responses": responses,
                }
            )
    return routes


def _public_module_manifest(module_name: str) -> list[dict[str, str]]:
    module = importlib.import_module(module_name)
    exports: list[dict[str, str]] = []
    for name, value in inspect.getmembers(module):
        if name.startswith("_"):
            continue
        if inspect.isclass(value):
            kind = "class"
        elif inspect.isfunction(value):
            kind = "function"
        elif name.isupper():
            kind = "constant"
        else:
            continue
        exports.append({"name": name, "kind": kind})
    return exports


def _models_manifest() -> dict[str, Any]:
    module = importlib.import_module("app.models")
    schemas: dict[str, Any] = {}
    for name, value in inspect.getmembers(module, inspect.isclass):
        if value is BaseModel or not issubclass(value, BaseModel):
            continue
        schemas[name] = _model_schema(value)
    return schemas


def _requirements_manifest() -> dict[str, Any]:
    path = REPO_ROOT / "requirements.txt"
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    return {"path": "requirements.txt", "sha256": hashlib.sha256(raw).hexdigest(), "entries": lines}


def _scenario_manifest() -> dict[str, Any]:
    from app.scenario import generate_schedule_input_from_scenario
    from app.scenario_data import default_scenario

    scenario = default_scenario()
    generated = generate_schedule_input_from_scenario(scenario)
    scenario_data = _model_dump(scenario)
    generated_data = _model_dump(generated)
    tasks = generated_data.get("schedule_input", {}).get("tasks", [])
    return {
        "scenario_sha256": _digest(scenario_data),
        "generated_sha256": _digest(generated_data),
        "task_count": len(tasks),
        "resource_pool_count": len(scenario_data.get("resource_pools", [])),
        "milestone_count": len(scenario_data.get("milestones", [])),
    }


def capture() -> dict[str, Any]:
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    from app.main import app

    routes = _route_manifest(app)
    schemas = _models_manifest()
    return {
        "format_version": 1,
        "api": {"route_count": len(routes), "routes": routes},
        "models": {"count": len(schemas), "schemas": schemas},
        "python_imports": {name: _public_module_manifest(name) for name in PUBLIC_MODULES},
        "requirements": _requirements_manifest(),
        "fixed_scenario": _scenario_manifest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", type=Path, help="Compare the live contract with an existing fixture.")
    args = parser.parse_args()
    current = capture()
    if args.check:
        expected = json.loads(args.check.read_text(encoding="utf-8"))
        if current != expected:
            print(f"architecture baseline mismatch: {args.check}", file=sys.stderr)
            return 1
        print(f"architecture baseline matches {args.check}")
        return 0
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output.relative_to(REPO_ROOT)} ({len(current['api']['routes'])} API routes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
