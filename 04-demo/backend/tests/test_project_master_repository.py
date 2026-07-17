from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.contracts.project_master import (  # noqa: E402
    ProjectMasterComponent,
    ProjectMasterDiffEntry,
    ProjectMasterSnapshot,
    ProjectMasterStructure,
    ProjectMasterWorkpoint,
)
from app.project_master.repository import ProjectMasterRepository  # noqa: E402


def _snapshot() -> ProjectMasterSnapshot:
    return ProjectMasterSnapshot(
        workpoints=[
            ProjectMasterWorkpoint(
                workpoint_id="WP-B01",
                workpoint_name="一号桥",
                workpoint_type="bridge",
                start_mileage_m=100,
                end_mileage_m=200,
                schedule_support="bridge_supported",
                structures=[
                    ProjectMasterStructure(
                        structure_id="ST-L-P1",
                        workpoint_id="WP-B01",
                        structure_name="左幅1号墩",
                        structure_category="substructure",
                        structure_type="bridge_pier",
                        side="left",
                        section_code="WS-L",
                        components=[
                            ProjectMasterComponent(
                                component_id="CP-PILE",
                                structure_id="ST-L-P1",
                                component_name="桩基",
                                component_type="pile",
                                quantity=4,
                                unit="根",
                            )
                        ],
                    )
                ],
            )
        ]
    )


def _draft(repository: ProjectMasterRepository, *, fingerprint: str = "fingerprint-1"):
    batch = repository.create_import_batch(
        project_id="project-1",
        file_name="project.xlsx",
        file_sha256="file-sha",
        expected_current_version_id=None,
        created_by="tester",
    )
    version = repository.create_draft_version(
        batch_id=batch.batch_id,
        project_id="project-1",
        content_fingerprint=fingerprint,
        snapshot=_snapshot(),
        issues=[],
        diff_entries=[
            ProjectMasterDiffEntry(
                object_kind="workpoint",
                object_id="WP-B01",
                change_type="added",
                after_value={"workpoint_name": "一号桥"},
            )
        ],
        created_by="tester",
        base_version_id=None,
    )
    return batch, version


def test_schema_enables_foreign_keys_indexes_and_version(tmp_path: Path) -> None:
    path = tmp_path / "project-master.db"
    ProjectMasterRepository(path)
    connection = sqlite3.connect(path)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
    assert {row[1] for row in connection.execute("PRAGMA index_list(project_master_versions)")} >= {
        "uq_project_master_current"
    }
    assert connection.execute("SELECT COUNT(*) FROM workpoint_type_definitions").fetchone()[0] >= 9


def test_repository_persists_tree_and_restores_after_restart(tmp_path: Path) -> None:
    path = tmp_path / "project-master.db"
    repository = ProjectMasterRepository(path)
    _, version = _draft(repository)

    restored = ProjectMasterRepository(path)
    snapshot = restored.load_snapshot(version.version_id)

    assert snapshot.workpoints[0].workpoint_id == "WP-B01"
    assert snapshot.workpoints[0].structures[0].components[0].quantity == 4
    assert restored.get_version_detail(version.version_id).diff_counts.added == 1


def test_confirmation_keeps_single_current_and_immutable_history(tmp_path: Path) -> None:
    repository = ProjectMasterRepository(tmp_path / "project-master.db")
    _, first = _draft(repository)
    confirmed = repository.confirm_version(first.version_id, expected_current_version_id=None, confirmed_by="chief")

    assert confirmed.status == "confirmed"
    assert repository.get_current_version("project-1").version_id == first.version_id


def test_cancel_ready_batch_removes_only_draft_business_rows(tmp_path: Path) -> None:
    repository = ProjectMasterRepository(tmp_path / "project-master.db")
    batch, version = _draft(repository)

    cancelled = repository.cancel_import_batch(batch.batch_id, cancelled_by="tester", cancel_reason="重传")

    assert cancelled.status == "cancelled"
    assert cancelled.created_version_id is None
    assert cancelled.cancelled_version_id == version.version_id
    assert repository.list_versions("project-1")[1] == 0
