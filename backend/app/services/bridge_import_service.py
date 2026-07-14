from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from ..bridge_import import default_local_bridge_workbook, import_bridge_parameters
from ..models import ImportBridgeParamsResponse, ScenarioInput


def import_uploaded_bridge_params(
    fields: dict[str, str],
    files: dict[str, dict[str, bytes | str]],
) -> ImportBridgeParamsResponse:
    scenario_text = fields.get("scenario")
    uploaded = files.get("file")
    if not scenario_text:
        raise HTTPException(status_code=400, detail="multipart 瀛楁 scenario 涓嶈兘涓虹┖銆?")
    if uploaded is None:
        raise HTTPException(status_code=400, detail="multipart 瀛楁 file 涓嶈兘涓虹┖銆?")

    try:
        scenario = ScenarioInput.model_validate_json(scenario_text)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"scenario JSON 鏃犳硶瑙ｆ瀽: {exc}") from exc

    return import_bridge_parameters(
        file_name=str(uploaded["filename"]),
        content=uploaded["content"],
        scenario=scenario,
        target_bridge=fields.get("target_bridge") or fields.get("targetBridge") or None,
    )


def import_local_bridge_params(scenario: ScenarioInput) -> ImportBridgeParamsResponse:
    workbook_path = local_workbook_path()
    return import_bridge_parameters(
        file_name=workbook_path.name,
        content=workbook_path.read_bytes(),
        scenario=scenario,
        target_bridge=None,
    )


def local_workbook_path() -> Path:
    project_root = Path(__file__).resolve().parents[3]
    workbook = default_local_bridge_workbook(project_root)
    if workbook is None:
        raise HTTPException(status_code=404, detail="椤圭洰鐩綍涓嬫湭鎵惧埌鍙鍏ョ殑 Excel 宸ヤ綔绨裤€?")
    return workbook
