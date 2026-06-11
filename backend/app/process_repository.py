from __future__ import annotations

import os
from typing import Any

from .models import ProcessTemplate
from .process_library_defaults import upgrade_process_library


PROCESS_RELATIONSHIP_TABLE = "process_relationships"

_POOL: Any | None = None


class ProcessRepositoryError(RuntimeError):
    pass


def load_process_library(fallback: list[ProcessTemplate]) -> list[ProcessTemplate]:
    database_configured = bool(_database_url())
    pool = _get_pool(required=database_configured)
    if pool is None:
        return upgrade_process_library(fallback, fallback)

    try:
        with pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    select
                      process_id,
                      component_type,
                      process_name,
                      method_id,
                      duration_method,
                      quantity_source,
                      productivity_value,
                      productivity_unit,
                      resource_type,
                      productivity_options,
                      applicability,
                      is_default
                    from public.{PROCESS_RELATIONSHIP_TABLE}
                    order by display_order, process_id
                    """
                )
                rows = cursor.fetchall()
    except Exception as exc:
        if database_configured:
            raise ProcessRepositoryError(f"读取 Supabase 工艺关系表失败：{exc}") from exc
        return fallback

    if not rows:
        try:
            save_process_library(fallback)
            return load_process_library(fallback)
        except ProcessRepositoryError:
            return fallback

    return upgrade_process_library([_process_from_row(row) for row in rows], fallback)


def save_process_library(process_library: list[ProcessTemplate]) -> list[ProcessTemplate]:
    if not process_library:
        raise ProcessRepositoryError("工艺关系表保存内容不能为空。")

    pool = _get_pool(required=True)
    if pool is None:
        raise ProcessRepositoryError("未配置 Supabase PostgreSQL session pool 连接串。")

    upgraded_process_library = upgrade_process_library(process_library)
    process_ids = [process.id for process in upgraded_process_library]
    rows = [_process_to_row(process, index) for index, process in enumerate(upgraded_process_library)]

    try:
        with pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    f"""
                    insert into public.{PROCESS_RELATIONSHIP_TABLE} (
                      process_id,
                      component_type,
                      process_name,
                      method_id,
                      duration_method,
                      quantity_source,
                      productivity_value,
                      productivity_unit,
                      resource_type,
                      productivity_options,
                      applicability,
                      is_default,
                      display_order
                    ) values (
                      %(process_id)s,
                      %(component_type)s,
                      %(process_name)s,
                      %(method_id)s,
                      %(duration_method)s,
                      %(quantity_source)s,
                      %(productivity_value)s,
                      %(productivity_unit)s,
                      %(resource_type)s,
                      %(productivity_options)s,
                      %(applicability)s,
                      %(is_default)s,
                      %(display_order)s
                    )
                    on conflict (process_id) do update set
                      component_type = excluded.component_type,
                      process_name = excluded.process_name,
                      method_id = excluded.method_id,
                      duration_method = excluded.duration_method,
                      quantity_source = excluded.quantity_source,
                      productivity_value = excluded.productivity_value,
                      productivity_unit = excluded.productivity_unit,
                      resource_type = excluded.resource_type,
                      productivity_options = excluded.productivity_options,
                      applicability = excluded.applicability,
                      is_default = excluded.is_default,
                      display_order = excluded.display_order
                    """,
                    rows,
                )
                cursor.execute(
                    f"delete from public.{PROCESS_RELATIONSHIP_TABLE} where not (process_id = any(%s))",
                    (process_ids,),
                )
            connection.commit()
    except Exception as exc:
        raise ProcessRepositoryError(f"写入 Supabase 工艺关系表失败：{exc}") from exc

    return load_process_library(process_library)


def _get_pool(*, required: bool) -> Any | None:
    global _POOL

    if _POOL is not None:
        return _POOL

    database_url = _database_url()
    if not database_url:
        return None

    try:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
    except ImportError as exc:
        if required:
            raise ProcessRepositoryError("缺少 psycopg 连接池依赖，请先安装 requirements.txt。") from exc
        return None

    try:
        max_size = max(1, int(os.getenv("SUPABASE_POSTGRES_POOL_SIZE", "5")))
        _POOL = ConnectionPool(
            conninfo=database_url,
            min_size=0,
            max_size=max_size,
            kwargs={"row_factory": dict_row},
        )
        return _POOL
    except Exception as exc:
        if required:
            raise ProcessRepositoryError(f"Supabase PostgreSQL session pool 初始化失败：{exc}") from exc
        return None


def _database_url() -> str | None:
    for key in ("SUPABASE_POSTGRES_SESSION_POOL_URL", "SUPABASE_DB_URL", "DATABASE_URL"):
        value = os.getenv(key)
        if value:
            return value.strip()
    return None


def _process_from_row(row: dict[str, Any]) -> ProcessTemplate:
    return ProcessTemplate.model_validate(
        {
            "id": row["process_id"],
            "component_type": row["component_type"],
            "process_name": row["process_name"],
            "method_id": row["method_id"],
            "duration_method": row["duration_method"],
            "quantity_source": row["quantity_source"],
            "productivity_value": float(row["productivity_value"]),
            "productivity_unit": row["productivity_unit"],
            "resource_type": row["resource_type"],
            "productivity_options": row["productivity_options"] or [],
            "applicability": row["applicability"] or {},
            "is_default": row["is_default"],
        }
    )


def _process_to_row(process: ProcessTemplate, index: int) -> dict[str, Any]:
    from psycopg.types.json import Jsonb

    process = process.ensure_default_productivity_option()
    return {
        "process_id": process.id,
        "component_type": process.component_type,
        "process_name": process.process_name,
        "method_id": process.method_id,
        "duration_method": process.duration_method,
        "quantity_source": process.quantity_source,
        "productivity_value": process.productivity_value,
        "productivity_unit": process.productivity_unit,
        "resource_type": process.resource_type,
        "productivity_options": Jsonb([option.model_dump(mode="json") for option in process.productivity_options]),
        "applicability": Jsonb(process.applicability),
        "is_default": process.is_default,
        "display_order": (index + 1) * 10,
    }
