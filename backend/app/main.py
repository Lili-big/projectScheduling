from __future__ import annotations

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
    ProcessLibrarySaveRequest,
    ProcessNlRequest,
    ProcessNlResponse,
    ProcessTemplate,
    ResourceCostSolveRequest,
    ScheduleInput,
    ScenarioCompareRequest,
    ScenarioCompareResponse,
    ScenarioInput,
    ScenarioSolveResult,
    WbsRequest,
    WbsResponse,
)
from .api.multipart import parse_multipart_request
from .bridge_import import BridgeImportConfigError, BridgeImportError
from .sample_data import (
    default_bridge,
    default_logic_rules,
    default_productivity_rules,
    default_resources,
)
from .scenario import compare_scenarios, generate_schedule_input_from_scenario, solve_min_resources_scenario, solve_resource_cost_scenario, solve_scenario
from .solver import solve_schedule
from .process_nl import apply_process_natural_language
from .process_repository import ProcessRepositoryError
from .services.bridge_import_service import import_local_bridge_params, import_uploaded_bridge_params
from .services.process_library_service import default_scenario_with_process_library, get_process_library, persist_process_library
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
    try:
        return default_scenario_with_process_library()
    except ProcessRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/process-library", response_model=list[ProcessTemplate])
def get_process_library_endpoint() -> list[ProcessTemplate]:
    try:
        return get_process_library()
    except ProcessRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.put("/api/process-library", response_model=list[ProcessTemplate])
def save_process_library_endpoint(request: ProcessLibrarySaveRequest) -> list[ProcessTemplate]:
    try:
        return persist_process_library(request.process_library)
    except ProcessRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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


@app.post("/api/solve-resource-cost", response_model=ScenarioSolveResult)
def solve_resource_cost_endpoint(request: ResourceCostSolveRequest) -> ScenarioSolveResult:
    return solve_resource_cost_scenario(request)


@app.post("/api/compare-scenarios", response_model=ScenarioCompareResponse)
def compare_scenarios_endpoint(request: ScenarioCompareRequest) -> ScenarioCompareResponse:
    return compare_scenarios(request)


@app.post("/api/apply-process-natural-language", response_model=ProcessNlResponse)
def apply_process_natural_language_endpoint(request: ProcessNlRequest) -> ProcessNlResponse:
    return apply_process_natural_language(request.scenario, request.prompt)


@app.post("/api/import-bridge-params", response_model=ImportBridgeParamsResponse)
async def import_bridge_params_endpoint(request: Request) -> ImportBridgeParamsResponse:
    try:
        fields, files = await parse_multipart_request(request)
        return import_uploaded_bridge_params(fields, files)
    except BridgeImportConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BridgeImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/import-local-bridge-params", response_model=ImportBridgeParamsResponse)
def import_local_bridge_params_endpoint(scenario: ScenarioInput) -> ImportBridgeParamsResponse:
    try:
        return import_local_bridge_params(scenario)
    except BridgeImportConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BridgeImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        requested = DIST_DIR / full_path
        if full_path and requested.is_file():
            return FileResponse(requested)
        return FileResponse(DIST_DIR / "index.html")
