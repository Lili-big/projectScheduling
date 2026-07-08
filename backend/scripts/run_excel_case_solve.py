from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
BACKEND_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.bridge_import import import_bridge_parameters  # noqa: E402
from app.local_scenario_config import BUNDLED_SCENARIO_CONFIG_PATH, LOCAL_SCENARIO_CONFIG_PATH  # noqa: E402
from app.models import MinResourcesSolveRequest, ScenarioInput, ScenarioSolveResult  # noqa: E402
from app.scenario import generate_schedule_input_from_scenario, solve_min_resources_scenario, solve_scenario  # noqa: E402
from app.services.bridge_import_service import import_local_bridge_params, local_workbook_path  # noqa: E402
from app.services.process_library_service import default_scenario_with_process_library  # noqa: E402
from app.solver import _matched_hard_milestone_count, _min_resource_target_days  # noqa: E402


SolveMode = str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import the local bridge Excel case and run backend scheduling solves.",
    )
    parser.add_argument(
        "--mode",
        choices=["fixed-duration", "fixed-resource", "both"],
        default="fixed-duration",
        help="Solve mode to run. Default: fixed-duration.",
    )
    parser.add_argument(
        "--workbook",
        type=Path,
        default=None,
        help="Optional workbook path. Default: first non-temp .xlsx in the repo root.",
    )
    parser.add_argument(
        "--target-bridge",
        default=None,
        help="Optional bridge name passed to the Excel importer.",
    )
    parser.add_argument(
        "--fallback-target-days",
        type=int,
        default=None,
        help="Fallback target duration for fixed-duration solve when no hard milestone is matched.",
    )
    parser.add_argument(
        "--time-limit",
        type=float,
        default=None,
        help="Override ScenarioInput.time_limit_seconds for this run.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path. Default: logs/excel-case-solve-<timestamp>.json.",
    )
    parser.add_argument(
        "--no-output",
        action="store_true",
        help="Print summary only and do not write JSON.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Include full ScenarioSolveResult payloads in the JSON output.",
    )
    return parser.parse_args()


def resolve_workbook(path: Path | None) -> Path:
    if path is None:
        return local_workbook_path()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def summarize_base_config(scenario: ScenarioInput) -> dict[str, Any]:
    return {
        "base_scenario_source": "default_scenario_with_process_library",
        "bundled_config_path": str(BUNDLED_SCENARIO_CONFIG_PATH),
        "bundled_config_exists": BUNDLED_SCENARIO_CONFIG_PATH.exists(),
        "local_config_path": str(LOCAL_SCENARIO_CONFIG_PATH),
        "local_config_exists": LOCAL_SCENARIO_CONFIG_PATH.exists(),
        "process_library_count": len(scenario.process_library),
        "logic_rule_count": len(scenario.logic_rules),
        "upper_structure_logic_rule_count": len(scenario.upper_structure_logic_rules),
        "resource_pool_count": len(scenario.resource_pools),
        "milestone_count": len(scenario.milestones),
    }


def import_scenario(args: argparse.Namespace) -> tuple[ScenarioInput, dict[str, Any], Path, dict[str, Any]]:
    scenario = default_scenario_with_process_library()
    base_config = summarize_base_config(scenario)
    if args.time_limit is not None:
        scenario.time_limit_seconds = args.time_limit

    workbook = resolve_workbook(args.workbook)
    if args.workbook is None:
        imported = import_local_bridge_params(scenario)
    else:
        imported = import_bridge_parameters(
            file_name=workbook.name,
            content=workbook.read_bytes(),
            scenario=scenario,
            target_bridge=args.target_bridge,
        )

    imported_scenario = imported.scenario
    if args.time_limit is not None:
        imported_scenario.time_limit_seconds = args.time_limit
    return imported_scenario, imported.model_dump(mode="json"), workbook, base_config


def validation_counts(messages: list[Any]) -> dict[str, int]:
    return dict(Counter(getattr(message, "level", None) or message.get("level", "unknown") for message in messages))


def compact_validation(messages: list[Any], limit: int = 20) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for message in messages[:limit]:
        if hasattr(message, "model_dump"):
            compact.append(message.model_dump(mode="json"))
        else:
            compact.append(dict(message))
    return compact


def summarize_generated(scenario: ScenarioInput) -> dict[str, Any]:
    generated = generate_schedule_input_from_scenario(scenario, use_max_resources=True)
    schedule_input = generated.schedule_input
    return {
        "task_count": len(schedule_input.tasks),
        "resource_count": len(schedule_input.resources),
        "precedence_count": len(schedule_input.precedence_links),
        "validation_count": validation_counts(generated.validation),
        "validation_messages": compact_validation(generated.validation),
        "matched_hard_milestone_count": _matched_hard_milestone_count(schedule_input),
        "target_days": _min_resource_target_days(schedule_input, None),
        "resource_count_by_pool": dict(Counter(resource.pool_id for resource in schedule_input.resources)),
        "task_count_by_component": dict(Counter(task.component_type for task in schedule_input.tasks)),
    }


def run_solves(
    scenario: ScenarioInput,
    mode: SolveMode,
    fallback_target_days: int | None,
) -> dict[str, ScenarioSolveResult]:
    solves: dict[str, ScenarioSolveResult] = {}
    if mode in {"fixed-resource", "both"}:
        solves["fixed_resource"] = solve_scenario(scenario)
    if mode in {"fixed-duration", "both"}:
        solves["fixed_duration"] = solve_min_resources_scenario(
            MinResourcesSolveRequest(
                scenario=scenario,
                fallback_target_days=fallback_target_days,
            )
        )
    return solves


def summarize_result(solved: ScenarioSolveResult) -> dict[str, Any]:
    result = solved.result
    target = result.stats.get("target_achievement") or {}
    recommended = result.stats.get("recommended_resource_counts") or []
    recommendation_attempts = result.stats.get("resource_recommendation_attempts") or result.objective_breakdown.get(
        "resource_recommendation_attempts",
        [],
    )
    return {
        "status": result.status,
        "objective_days": result.objective_days,
        "plan_start_date": result.plan_start_date,
        "plan_finish_date": result.plan_finish_date,
        "task_count": len(result.tasks),
        "allocation_count": len(result.resource_allocations),
        "schedule_source": result.stats.get("schedule_source") or result.objective_breakdown.get("schedule_source"),
        "recommended_schedule_source": result.stats.get("recommended_schedule_source")
        or result.objective_breakdown.get("recommended_schedule_source"),
        "target_achievement": target,
        "resource_recommendation_status": result.stats.get("resource_recommendation_status")
        or result.objective_breakdown.get("resource_recommendation_status"),
        "resource_recommendation_message": result.stats.get("resource_recommendation_message")
        or result.objective_breakdown.get("resource_recommendation_message"),
        "resource_recommendation_attempt_count": result.stats.get("resource_recommendation_attempt_count")
        or result.objective_breakdown.get("resource_recommendation_attempt_count"),
        "resource_recommendation_attempt_limit": result.stats.get("resource_recommendation_attempt_limit")
        or result.objective_breakdown.get("resource_recommendation_attempt_limit"),
        "resource_recommendation_attempts": recommendation_attempts,
        "max_resource_precheck_mode": result.stats.get("max_resource_precheck_mode"),
        "capacity_precheck_status": result.stats.get("capacity_precheck_status"),
        "capacity_model_status": result.stats.get("capacity_model_status"),
        "global_capacity_model_status": result.stats.get("global_capacity_model_status"),
        "capacity_verification_status": result.stats.get("capacity_verification_status"),
        "recommended_resource_counts": [
            {
                "resource_pool_id": item.get("resource_pool_id"),
                "label": item.get("label"),
                "resource_type": item.get("resource_type"),
                "recommended_quantity": item.get("recommended_quantity"),
                "current_quantity": item.get("current_quantity"),
                "added_quantity": item.get("added_quantity"),
                "max_quantity": item.get("max_quantity"),
            }
            for item in recommended
        ],
        "milestone_results": [milestone.model_dump(mode="json") for milestone in result.milestone_results],
        "validation_count": validation_counts(result.validation),
        "validation_messages": compact_validation(result.validation),
    }


def default_output_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return REPO_ROOT / "logs" / f"excel-case-solve-{timestamp}.json"


def print_summary(payload: dict[str, Any]) -> None:
    print("=== Excel case solve summary ===")
    print(f"workbook: {payload['workbook']}")
    print(f"mode: {payload['mode']}")
    config = payload.get("scenario_config") or {}
    if config:
        local_status = "loaded" if config.get("local_config_exists") else "not found"
        print(f"base scenario: {config.get('base_scenario_source')}")
        print(f"local config: {config.get('local_config_path')} ({local_status})")
        print(
            "config counts: "
            f"{config.get('process_library_count')} processes, "
            f"{config.get('logic_rule_count')} lower logic rules, "
            f"{config.get('upper_structure_logic_rule_count')} upper logic rules, "
            f"{config.get('resource_pool_count')} resource pools, "
            f"{config.get('milestone_count')} milestones"
        )
    generated = payload["generated"]
    print(
        "generated: "
        f"{generated['task_count']} tasks, "
        f"{generated['resource_count']} resources, "
        f"{generated['precedence_count']} precedence links"
    )
    print(f"matched hard milestones: {generated['matched_hard_milestone_count']}")
    print(f"target days: {generated['target_days']}")
    for name, summary in payload["results"].items():
        target = summary.get("target_achievement") or {}
        print(f"--- {name} ---")
        print(f"status: {summary['status']}")
        print(f"schedule_source: {summary.get('schedule_source')}")
        print(f"target_status: {target.get('target_status')}")
        print(f"business_success: {target.get('business_success')}")
        print(f"objective_days: {summary.get('objective_days')}")
        print(f"plan_finish_date: {summary.get('plan_finish_date')}")
        print(f"tasks_out: {summary.get('task_count')}")
        if summary.get("max_resource_precheck_mode"):
            print(f"max_resource_precheck_mode: {summary.get('max_resource_precheck_mode')}")
            print(f"capacity_precheck_status: {summary.get('capacity_precheck_status')}")
        if summary.get("recommended_resource_counts"):
            compact = [
                f"{item['label']}={item['recommended_quantity']}"
                for item in summary["recommended_resource_counts"]
                if item.get("recommended_quantity") is not None
            ]
            print("recommended: " + ", ".join(compact))
        if summary.get("resource_recommendation_attempt_count"):
            print(
                "recommendation_attempts: "
                f"{summary.get('resource_recommendation_attempt_count')}/"
                f"{summary.get('resource_recommendation_attempt_limit')}"
            )
            for attempt in summary.get("resource_recommendation_attempts") or []:
                print(
                    "  "
                    f"attempt {attempt.get('attempt')}: "
                    f"lower={attempt.get('search_lower_bounds')}, "
                    f"candidate={attempt.get('candidate_quantities')}, "
                    f"full_status={attempt.get('full_objective_status')}, "
                    f"target={attempt.get('full_objective_target_status')}, "
                    f"success={attempt.get('business_success')}"
                )
        message = summary.get("resource_recommendation_message")
        if message:
            print(f"message: {message}")
    if payload.get("output_path"):
        print(f"json: {payload['output_path']}")


def main() -> int:
    args = parse_args()
    started_at = time.perf_counter()
    scenario, import_payload, workbook, base_config = import_scenario(args)
    generated_summary = summarize_generated(scenario)
    solved = run_solves(scenario, args.mode, args.fallback_target_days)

    payload: dict[str, Any] = {
        "workbook": str(workbook),
        "mode": args.mode,
        "time_limit_seconds": scenario.time_limit_seconds,
        "elapsed_seconds": round(time.perf_counter() - started_at, 3),
        "scenario_config": base_config,
        "import_summary": import_payload.get("summary"),
        "import_warnings": import_payload.get("warnings", []),
        "generated": generated_summary,
        "results": {
            name: summarize_result(result)
            for name, result in solved.items()
        },
    }
    if args.full:
        payload["full_results"] = {
            name: result.model_dump(mode="json")
            for name, result in solved.items()
        }

    if not args.no_output:
        output_path = args.output or default_output_path()
        if not output_path.is_absolute():
            output_path = REPO_ROOT / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        payload["output_path"] = str(output_path)

    print_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
