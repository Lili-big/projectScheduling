from __future__ import annotations

import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.scenario_data import default_scenario  # noqa: E402
from app.services.ai_parameter_ai_client import AiParameterAiClient, AiParameterAiPayload  # noqa: E402
from app.services.ai_parameter_assistant import parse_ai_parameter_assistant  # noqa: E402
from app.services.ai_parameter_store import AiParameterStore  # noqa: E402


def test_image_suggestions_are_low_confidence_and_need_manual_review() -> None:
    scenario = default_scenario()
    response = parse_ai_parameter_assistant(
        {"scenario": scenario.model_dump_json()},
        {"file": {"filename": "资源截图.png", "content": b"fake-image-bytes"}},
        client=FakeImageAiClient(),
        store=AiParameterStore(),
    )

    assert response.suggestions[0].confidence_label == "Low"
    assert response.suggestions[0].status == "needs_manual_input"
    assert response.material_summaries[0].kind == "image"
    assert not hasattr(response.material_summaries[0], "content_base64")


class FakeImageAiClient(AiParameterAiClient):
    def understand(self, *, scenario, materials):  # type: ignore[no-untyped-def]
        assert materials[0].ai_payload()["mime_type"] == "image/png"
        assert materials[0].ai_payload()["content_base64"] == base64.b64encode(b"fake-image-bytes").decode("ascii")
        return AiParameterAiPayload(
            suggestions=[
                {
                    "category": "resource_pool",
                    "target_ref": {"resource_type": scenario.resource_pools[0].type},
                    "parameter_key": "resource.quantity",
                    "proposed_value": 2,
                    "unit": "台",
                    "confidence_score": 95,
                    "source_refs": [{"material_id": "mat_file_001", "excerpt": "旋挖钻 2 台"}],
                }
            ]
        )
