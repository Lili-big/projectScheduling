from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.contracts import ResourcePool  # noqa: E402
from app.scenario_data import default_scenario, derive_resource_catalog  # noqa: E402
from app.services import ai_resource_explainer as explainer  # noqa: E402
from app.services import ai_workpoint_resource_initializer as initializer  # noqa: E402


def _two_workpoint_scenario(*, with_existing: bool = True):
    scenario = default_scenario()
    bridge = scenario.project.bridges[0]
    bridge_a = bridge.model_copy(update={"id": "WP-A", "name": "Bridge A"}, deep=True)
    bridge_b = bridge.model_copy(update={"id": "WP-B", "name": "Bridge B"}, deep=True)
    existing = []
    if with_existing:
        existing = [
            ResourcePool(
                id="existing-a-rotary",
                type="rotary_drill",
                label="Existing rotary drill",
                resource_mode="LIMITED",
                scope_mode="WORKPOINT_EXCLUSIVE",
                workpoint_id="WP-A",
                quantity=7,
                max_quantity=9,
                enabled=False,
                calendar_id="continuous",
                compatible_process_ids=["custom-process"],
                incremental_unit_cost=123,
            )
        ]
    return scenario.model_copy(
        update={
            "project_data_version_id": "pm-v1",
            "project": scenario.project.model_copy(update={"bridges": [bridge_a, bridge_b]}),
            "resource_pools": existing,
        }
    )


def _valid_batch(context):
    return [
        {
            "workpoint_id": item["workpoint_id"],
            "resources": (
                [
                    {
                        "resource_type": item["candidates"][0]["resource_type"],
                        "quantity": 2,
                        "max_quantity": 3,
                        "reason": "initial construction front",
                    }
                ]
                if item["candidates"]
                else []
            ),
        }
        for item in context["workpoints"]
    ]


def test_initializer_builds_stable_structure_context_and_only_missing_candidates(monkeypatch) -> None:
    scenario = _two_workpoint_scenario()
    before = [pool.model_dump(mode="json") for pool in scenario.resource_pools]
    calls = []

    def fake_generate(context, validation_errors=None):
        calls.append((context, validation_errors))
        return _valid_batch(context), explainer.ResourceAssistantLlmConfigStatus(
            provider="openai", model="test-model", endpoint_configured=True,
            api_key_configured=True, timeout_seconds=30, status="configured",
        )

    monkeypatch.setattr(initializer, "generate_workpoint_resource_initialization_payload", fake_generate)
    response = initializer.initialize_workpoint_resources(scenario)

    assert len(calls) == 1
    context = calls[0][0]
    assert [item["workpoint_id"] for item in context["workpoints"]] == ["WP-A", "WP-B"]
    assert all(item["structures"] for item in context["workpoints"])
    assert all(
        item["structures"] == sorted(
            item["structures"],
            key=lambda value: (
                value["structure_type"], value["component_type"], value["process_id"] or "",
                value["unit"], json.dumps(value["parameter_summary"], ensure_ascii=False, sort_keys=True),
            ),
        )
        for item in context["workpoints"]
    )
    candidates_a = [item["resource_type"] for item in context["workpoints"][0]["candidates"]]
    assert "rotary_drill" not in candidates_a
    assert "precast_beam_team" not in {item["resource_type"] for item in derive_resource_catalog(scenario)}
    assert response.summary.workpoint_count == 2
    assert response.summary.recommended_workpoint_count == 2
    assert response.summary.added_resource_count == 2
    assert all(pool.scope_mode == "WORKPOINT_EXCLUSIVE" for pool in response.resource_pools_to_add)
    assert all(pool.enabled and (pool.quantity or 0) > 0 for pool in response.resource_pools_to_add)
    assert [pool.model_dump(mode="json") for pool in scenario.resource_pools] == before


def test_initializer_retries_one_invalid_batch_then_applies_only_the_valid_batch(monkeypatch) -> None:
    scenario = _two_workpoint_scenario(with_existing=False)
    call_count = 0

    def fake_generate(context, validation_errors=None):
        nonlocal call_count
        call_count += 1
        batch = _valid_batch(context)
        if call_count == 1:
            batch[0]["resources"][0]["resource_type"] = "unknown_resource"
        assert (validation_errors is None) == (call_count == 1)
        return batch, explainer.ResourceAssistantLlmConfigStatus(
            provider="openai", model="test-model", endpoint_configured=True,
            api_key_configured=True, timeout_seconds=30, status="configured",
        )

    monkeypatch.setattr(initializer, "generate_workpoint_resource_initialization_payload", fake_generate)
    response = initializer.initialize_workpoint_resources(scenario)

    assert call_count == 2
    assert response.resource_pools_to_add
    assert all(pool.type != "unknown_resource" for pool in response.resource_pools_to_add)


@pytest.mark.parametrize(
    "invalid_mutation",
    [
        lambda batch: batch.pop(),
        lambda batch: batch.append({"workpoint_id": "WP-X", "resources": []}),
        lambda batch: batch[0]["resources"].append(batch[0]["resources"][0].copy()),
        lambda batch: batch[0]["resources"][0].update({"quantity": 0}),
        lambda batch: batch[0]["resources"][0].update({"quantity": 3, "max_quantity": 2}),
    ],
)
def test_initializer_rejects_an_invalid_batch_atomically_after_one_correction(monkeypatch, invalid_mutation) -> None:
    scenario = _two_workpoint_scenario(with_existing=False)
    before = scenario.model_dump(mode="json")["resource_pools"]

    def fake_generate(context, validation_errors=None):
        batch = _valid_batch(context)
        invalid_mutation(batch)
        return batch, explainer.ResourceAssistantLlmConfigStatus(
            provider="openai", model="test-model", endpoint_configured=True,
            api_key_configured=True, timeout_seconds=30, status="configured",
        )

    monkeypatch.setattr(initializer, "generate_workpoint_resource_initialization_payload", fake_generate)
    with pytest.raises(ValueError, match="remained invalid"):
        initializer.initialize_workpoint_resources(scenario)
    assert scenario.model_dump(mode="json")["resource_pools"] == before


def test_strict_openai_compatible_client_sends_one_json_request_without_leaking_key(monkeypatch) -> None:
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_PROVIDER", "openai")
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_ENDPOINT", "https://model.example/v1/chat/completions")
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_MODEL", "model-x")
    monkeypatch.setenv("AI_RESOURCE_ASSISTANT_API_KEY", "super-secret-key")
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            content = json.dumps({"workpoints": [{"workpoint_id": "WP-A", "resources": []}]})
            return json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode())
        captured["authorization"] = request.headers.get("Authorization")
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(explainer.urllib.request, "urlopen", fake_urlopen)
    result, status = explainer.generate_workpoint_resource_initialization_payload(
        {"workpoints": [{"workpoint_id": "WP-A", "structures": [], "candidates": []}]}
    )

    assert result == [{"workpoint_id": "WP-A", "resources": []}]
    assert captured["body"]["model"] == "model-x"
    assert captured["authorization"] == "Bearer super-secret-key"
    assert "super-secret-key" not in json.dumps(captured["body"])
    assert status.status == "configured"
