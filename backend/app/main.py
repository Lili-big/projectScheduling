from __future__ import annotations

from email.parser import BytesParser
from email.policy import default
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .local_config import load_local_config
from .models import (
    DemoPayload,
    GeneratedScheduleInput,
    ImportBridgeParamsResponse,
    MinResourcesSolveRequest,
    ProcessNlRequest,
    ProcessNlResponse,
    ScheduleInput,
    ScenarioCompareRequest,
    ScenarioCompareResponse,
    ScenarioInput,
    ScenarioSolveResult,
    WbsRequest,
    WbsResponse,
)
from .bridge_import import BridgeImportConfigError, BridgeImportError, import_bridge_parameters
from .sample_data import (
    default_bridge,
    default_logic_rules,
    default_productivity_rules,
    default_resources,
)
from .scenario import compare_scenarios, generate_schedule_input_from_scenario, solve_min_resources_scenario, solve_scenario
from .scenario_data import default_scenario
from .solver import solve_schedule
from .process_nl import apply_process_natural_language
from .wbs import generate_wbs


load_local_config()

app = FastAPI(title="Bridge Lower-Structure CP-SAT Scheduler", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/demo", response_model=DemoPayload)
def demo() -> DemoPayload:
    bridge = default_bridge()
    productivity_rules = default_productivity_rules()
    logic_rules = default_logic_rules()
    resources = default_resources()
    wbs = generate_wbs(bridge, productivity_rules, logic_rules)
    return DemoPayload(
        bridge=bridge,
        productivity_rules=productivity_rules,
        logic_rules=logic_rules,
        resources=resources,
        wbs=wbs,
    )


@app.get("/api/demo-scenario", response_model=ScenarioInput)
def demo_scenario() -> ScenarioInput:
    return default_scenario()


@app.post("/api/generate-wbs", response_model=WbsResponse)
def generate_wbs_endpoint(request: WbsRequest) -> WbsResponse:
    return generate_wbs(request.bridge, request.productivity_rules, request.logic_rules)


@app.post("/api/solve")
def solve_endpoint(schedule_input: ScheduleInput):
    return solve_schedule(schedule_input)


@app.post("/api/generate-schedule-input", response_model=GeneratedScheduleInput)
def generate_schedule_input_endpoint(scenario: ScenarioInput) -> GeneratedScheduleInput:
    return generate_schedule_input_from_scenario(scenario)


@app.post("/api/solve-scenario", response_model=ScenarioSolveResult)
def solve_scenario_endpoint(scenario: ScenarioInput) -> ScenarioSolveResult:
    return solve_scenario(scenario)


@app.post("/api/solve-min-resources", response_model=ScenarioSolveResult)
def solve_min_resources_endpoint(request: MinResourcesSolveRequest) -> ScenarioSolveResult:
    return solve_min_resources_scenario(request)


@app.post("/api/compare-scenarios", response_model=ScenarioCompareResponse)
def compare_scenarios_endpoint(request: ScenarioCompareRequest) -> ScenarioCompareResponse:
    return compare_scenarios(request)


@app.post("/api/apply-process-natural-language", response_model=ProcessNlResponse)
def apply_process_natural_language_endpoint(request: ProcessNlRequest) -> ProcessNlResponse:
    return apply_process_natural_language(request.scenario, request.prompt)


@app.post("/api/import-bridge-params", response_model=ImportBridgeParamsResponse)
async def import_bridge_params_endpoint(request: Request) -> ImportBridgeParamsResponse:
    fields, files = await _parse_multipart_request(request)
    scenario_text = fields.get("scenario")
    uploaded = files.get("file")
    if not scenario_text:
        raise HTTPException(status_code=400, detail="multipart 字段 scenario 不能为空。")
    if uploaded is None:
        raise HTTPException(status_code=400, detail="multipart 字段 file 不能为空。")

    try:
        scenario = ScenarioInput.model_validate_json(scenario_text)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"scenario JSON 无法解析: {exc}") from exc

    try:
        return import_bridge_parameters(
            file_name=uploaded["filename"],
            content=uploaded["content"],
            scenario=scenario,
            target_bridge=fields.get("target_bridge") or fields.get("targetBridge") or None,
        )
    except BridgeImportConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BridgeImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/import-local-bridge-params", response_model=ImportBridgeParamsResponse)
def import_local_bridge_params_endpoint(scenario: ScenarioInput) -> ImportBridgeParamsResponse:
    workbook_path = _local_workbook_path()
    try:
        return import_bridge_parameters(
            file_name=workbook_path.name,
            content=workbook_path.read_bytes(),
            scenario=scenario,
            target_bridge=None,
        )
    except BridgeImportConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BridgeImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _local_workbook_path() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    workbooks = sorted(
        path for path in project_root.glob("*.xlsx")
        if not path.name.startswith("~$")
    )
    if not workbooks:
        raise HTTPException(status_code=404, detail="项目目录下未找到可导入的 Excel 工作簿。")
    return workbooks[0]


async def _parse_multipart_request(request: Request) -> tuple[dict[str, str], dict[str, dict[str, bytes | str]]]:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise HTTPException(status_code=415, detail="请使用 multipart/form-data 上传 Excel 和 scenario。")

    body = await request.body()
    mime_body = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
    message = BytesParser(policy=default).parsebytes(mime_body)
    if not message.is_multipart():
        raise HTTPException(status_code=400, detail="multipart 请求体格式不正确。")

    fields: dict[str, str] = {}
    files: dict[str, dict[str, bytes | str]] = {}
    for part in message.iter_parts():
        params = dict(part.get_params(header="content-disposition", unquote=True) or [])
        name = params.get("name")
        if not name:
            continue
        payload = part.get_payload(decode=True) or b""
        filename = params.get("filename")
        if filename:
            files[name] = {"filename": filename, "content": payload}
        else:
            charset = part.get_content_charset() or "utf-8"
            fields[name] = payload.decode(charset)
    return fields, files


DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        requested = DIST_DIR / full_path
        if full_path and requested.is_file():
            return FileResponse(requested)
        return FileResponse(DIST_DIR / "index.html")
