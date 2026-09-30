from __future__ import annotations

import json
import sqlite3

from .definitions import (
    COMPONENT_TYPES,
    DEFINITION_VERSION,
    PARAMETER_DEFINITIONS,
    STRUCTURE_TYPES,
    WORKPOINT_TYPES,
)


SCHEMA_VERSION = 3

PROGRESS_DDL = """
CREATE TABLE IF NOT EXISTS pavement_progress_revisions (
    project_id TEXT PRIMARY KEY,
    revision INTEGER NOT NULL CHECK(revision >= 0),
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pavement_daily_progress (
    project_id TEXT NOT NULL,
    component_id TEXT NOT NULL,
    progress_date TEXT NOT NULL,
    completed_length_m TEXT NOT NULL,
    source_version_id TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(project_id, component_id, progress_date),
    FOREIGN KEY(source_version_id, component_id)
        REFERENCES components(version_id, component_id) ON DELETE RESTRICT
);
"""


DDL = """
CREATE TABLE IF NOT EXISTS import_batches (
    batch_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    status TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_sha256 TEXT NOT NULL,
    content_fingerprint TEXT,
    expected_current_version_id TEXT,
    created_version_id TEXT,
    existing_version_id TEXT,
    cancelled_version_id TEXT,
    counts_json TEXT NOT NULL DEFAULT '{}',
    diff_counts_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    completed_at TEXT,
    cancelled_at TEXT,
    cancelled_by TEXT,
    cancel_reason TEXT,
    failure_message TEXT,
    FOREIGN KEY(created_version_id) REFERENCES project_master_versions(version_id) ON DELETE SET NULL,
    FOREIGN KEY(existing_version_id) REFERENCES project_master_versions(version_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS project_master_versions (
    version_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    version_no INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('draft','confirmed','superseded')),
    content_fingerprint TEXT NOT NULL,
    source_batch_id TEXT NOT NULL UNIQUE,
    base_version_id TEXT,
    summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    confirmed_at TEXT,
    confirmed_by TEXT,
    UNIQUE(project_id, version_no),
    UNIQUE(project_id, content_fingerprint),
    FOREIGN KEY(source_batch_id) REFERENCES import_batches(batch_id) ON DELETE RESTRICT,
    FOREIGN KEY(base_version_id) REFERENCES project_master_versions(version_id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_project_master_current
ON project_master_versions(project_id) WHERE status = 'confirmed';

CREATE TABLE IF NOT EXISTS workpoints (
    version_id TEXT NOT NULL,
    workpoint_id TEXT NOT NULL,
    workpoint_name TEXT NOT NULL,
    workpoint_type TEXT NOT NULL,
    alignment_code TEXT,
    start_mileage_m REAL,
    end_mileage_m REAL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    schedule_support TEXT NOT NULL,
    remark TEXT,
    PRIMARY KEY(version_id, workpoint_id),
    FOREIGN KEY(version_id) REFERENCES project_master_versions(version_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS route_placements (
    version_id TEXT NOT NULL,
    placement_id TEXT NOT NULL,
    workpoint_id TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('left','right')),
    mileage_prefix TEXT NOT NULL,
    start_mileage_m REAL,
    end_mileage_m REAL,
    spatial_group_id TEXT NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(version_id, placement_id),
    UNIQUE(version_id, workpoint_id, side),
    FOREIGN KEY(version_id, workpoint_id) REFERENCES workpoints(version_id, workpoint_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS structures (
    version_id TEXT NOT NULL,
    structure_id TEXT NOT NULL,
    workpoint_id TEXT NOT NULL,
    structure_name TEXT NOT NULL,
    structure_category TEXT NOT NULL,
    structure_type TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('left','right','shared','none')),
    section_code TEXT,
    section_name TEXT,
    control_level TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    remark TEXT,
    PRIMARY KEY(version_id, structure_id),
    FOREIGN KEY(version_id, workpoint_id) REFERENCES workpoints(version_id, workpoint_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS components (
    version_id TEXT NOT NULL,
    component_id TEXT NOT NULL,
    structure_id TEXT NOT NULL,
    component_name TEXT NOT NULL,
    component_type TEXT NOT NULL,
    quantity REAL NOT NULL CHECK(quantity >= 0),
    unit TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
    sort_order INTEGER NOT NULL DEFAULT 0,
    remark TEXT,
    PRIMARY KEY(version_id, component_id),
    FOREIGN KEY(version_id, structure_id) REFERENCES structures(version_id, structure_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS structure_parameters (
    version_id TEXT NOT NULL,
    structure_id TEXT NOT NULL,
    parameter_code TEXT NOT NULL,
    value_type TEXT NOT NULL,
    value_json TEXT NOT NULL,
    unit TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(version_id, structure_id, parameter_code),
    FOREIGN KEY(version_id, structure_id) REFERENCES structures(version_id, structure_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS component_parameters (
    version_id TEXT NOT NULL,
    component_id TEXT NOT NULL,
    parameter_code TEXT NOT NULL,
    value_type TEXT NOT NULL,
    value_json TEXT NOT NULL,
    unit TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(version_id, component_id, parameter_code),
    FOREIGN KEY(version_id, component_id) REFERENCES components(version_id, component_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS import_issues (
    issue_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('error','warning')),
    issue_code TEXT NOT NULL,
    sheet_name TEXT NOT NULL,
    row_no INTEGER,
    field_name TEXT,
    object_kind TEXT,
    object_id TEXT,
    message TEXT NOT NULL,
    suggestion TEXT,
    FOREIGN KEY(batch_id) REFERENCES import_batches(batch_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS source_evidence (
    evidence_id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL,
    object_kind TEXT NOT NULL,
    object_id TEXT NOT NULL,
    parameter_code TEXT,
    batch_id TEXT NOT NULL,
    sheet_name TEXT NOT NULL,
    row_no INTEGER NOT NULL,
    column_name TEXT,
    FOREIGN KEY(version_id) REFERENCES project_master_versions(version_id) ON DELETE CASCADE,
    FOREIGN KEY(batch_id) REFERENCES import_batches(batch_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS version_diff_entries (
    diff_id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL,
    base_version_id TEXT,
    object_kind TEXT NOT NULL,
    object_id TEXT NOT NULL,
    change_type TEXT NOT NULL,
    field_name TEXT,
    before_value_json TEXT,
    after_value_json TEXT,
    blocking_reference INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(version_id) REFERENCES project_master_versions(version_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workpoint_type_definitions (
    type_code TEXT PRIMARY KEY, display_name TEXT NOT NULL, schedule_support TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1, definition_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS structure_type_definitions (
    type_code TEXT PRIMARY KEY, category TEXT NOT NULL, definition_json TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1, definition_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS component_type_definitions (
    type_code TEXT PRIMARY KEY, display_name TEXT NOT NULL, definition_json TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1, definition_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS parameter_definitions (
    owner_kind TEXT NOT NULL, parameter_code TEXT NOT NULL, definition_json TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1, definition_version TEXT NOT NULL,
    PRIMARY KEY(owner_kind, parameter_code)
);

CREATE INDEX IF NOT EXISTS ix_workpoints_version_type_order
ON workpoints(version_id, workpoint_type, sort_order);
CREATE INDEX IF NOT EXISTS ix_route_placements_version_side_order
ON route_placements(version_id, side, display_order, placement_id);
CREATE INDEX IF NOT EXISTS ix_structures_version_workpoint_side_order
ON structures(version_id, workpoint_id, side, sort_order);
CREATE INDEX IF NOT EXISTS ix_components_version_structure_order
ON components(version_id, structure_id, sort_order);
CREATE INDEX IF NOT EXISTS ix_import_issues_batch_severity_location
ON import_issues(batch_id, severity, sheet_name, row_no);
CREATE INDEX IF NOT EXISTS ix_version_diff_change_kind
ON version_diff_entries(version_id, change_type, object_kind);
"""


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = ON")
    current = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if current > SCHEMA_VERSION:
        raise RuntimeError(f"项目主数据数据库版本 {current} 高于当前支持版本 {SCHEMA_VERSION}。")
    if current < SCHEMA_VERSION:
        try:
            connection.executescript("BEGIN IMMEDIATE;\n" + (DDL if current < 2 else "") + PROGRESS_DDL)
            if current < 2:
                _seed_definitions(connection)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def _seed_definitions(connection: sqlite3.Connection) -> None:
    for code, definition in WORKPOINT_TYPES.items():
        connection.execute(
            "INSERT OR REPLACE INTO workpoint_type_definitions VALUES (?,?,?,?,?)",
            (code, definition["display_name"], definition["schedule_support"], 1, DEFINITION_VERSION),
        )
    for code, definition in STRUCTURE_TYPES.items():
        connection.execute(
            "INSERT OR REPLACE INTO structure_type_definitions VALUES (?,?,?,?,?)",
            (code, definition["category"], json.dumps(definition, ensure_ascii=False), 1, DEFINITION_VERSION),
        )
    for code, definition in COMPONENT_TYPES.items():
        connection.execute(
            "INSERT OR REPLACE INTO component_type_definitions VALUES (?,?,?,?,?)",
            (code, definition["display_name"], json.dumps(definition, ensure_ascii=False), 1, DEFINITION_VERSION),
        )
    for (owner_kind, code), definition in PARAMETER_DEFINITIONS.items():
        connection.execute(
            "INSERT OR REPLACE INTO parameter_definitions VALUES (?,?,?,?,?)",
            (owner_kind, code, json.dumps(definition, ensure_ascii=False), 1, DEFINITION_VERSION),
        )
