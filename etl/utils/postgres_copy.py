from __future__ import annotations

from io import StringIO

import pandas as pd
from sqlalchemy import Engine, text


def quote_ident(identifier: str) -> str:
    """Returns a safely double-quoted SQL identifier."""
    return '"' + identifier.replace('"', '""') + '"'


# Keep private alias for internal use
_quote_ident = quote_ident


def _qualified_table_name(schema: str | None, table: str) -> str:
    quoted_table = quote_ident(table)
    if schema:
        return f"{quote_ident(schema)}.{quoted_table}"
    return quoted_table


def copy_dataframe_to_staging(
    engine: Engine,
    dataframe: pd.DataFrame,
    staging_table: str,
    schema: str | None = None,
) -> int:
    if dataframe.empty:
        return 0

    table_name = _qualified_table_name(schema, staging_table)
    columns = [_quote_ident(col) for col in dataframe.columns]
    csv_buffer = StringIO()

    dataframe.to_csv(
        csv_buffer,
        index=False,
        header=False,
        sep=",",
        na_rep="",
    )
    csv_buffer.seek(0)

    copy_sql = (
        f"COPY {table_name} ({', '.join(columns)}) "
        "FROM STDIN WITH (FORMAT CSV, DELIMITER ',', NULL '')"
    )

    raw_connection = engine.raw_connection()
    try:
        with raw_connection.cursor() as cursor:
            # Truncate staging before each load so stale data from a previous
            # failed run never mixes with the current batch.
            cursor.execute(f"TRUNCATE TABLE {table_name}")
            cursor.copy_expert(copy_sql, csv_buffer)
        raw_connection.commit()
    except Exception:
        raw_connection.rollback()
        raise
    finally:
        raw_connection.close()

    return len(dataframe)


def upsert_from_staging(
    engine: Engine,
    staging_table: str,
    target_table: str,
    insert_columns: list[str],
    conflict_columns: list[str],
    schema: str | None = None,
    conflict_expressions: list[str] | None = None,
) -> None:
    if not insert_columns:
        raise ValueError("insert_columns cannot be empty")
    if not conflict_columns:
        raise ValueError("conflict_columns cannot be empty")

    update_columns = [col for col in insert_columns if col not in conflict_columns]

    qualified_staging = _qualified_table_name(schema, staging_table)
    qualified_target = _qualified_table_name(schema, target_table)
    insert_cols_sql = ", ".join(_quote_ident(col) for col in insert_columns)

    if conflict_expressions:
        conflict_target_sql = ", ".join(conflict_expressions)
        distinct_on_sql = conflict_target_sql
    else:
        conflict_target_sql = ", ".join(_quote_ident(col) for col in conflict_columns)
        distinct_on_sql = conflict_target_sql

    if update_columns:
        update_set_sql = ", ".join(
            f"{_quote_ident(col)} = EXCLUDED.{_quote_ident(col)}" for col in update_columns
        )
        on_conflict_sql = f"DO UPDATE SET {update_set_sql}"
    else:
        on_conflict_sql = "DO NOTHING"

    upsert_sql = f"""
        INSERT INTO {qualified_target} ({insert_cols_sql})
        SELECT DISTINCT ON ({distinct_on_sql}) {insert_cols_sql}
        FROM {qualified_staging}
        ORDER BY {distinct_on_sql}
        ON CONFLICT ({conflict_target_sql})
        {on_conflict_sql}
    """

    truncate_sql = f"TRUNCATE TABLE {qualified_staging}"

    with engine.begin() as connection:
        connection.execute(text(upsert_sql))
        connection.execute(text(truncate_sql))
