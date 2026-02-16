from __future__ import annotations

import pandas as pd

_INVALID_DATE_TOKENS = {"", "None", "nan", "<NA>", "NaT"}


def normalize_date_columns(chunk: pd.DataFrame, date_columns: list[str]) -> pd.DataFrame:
    for col in date_columns:
        series = chunk[col].astype(str).str.strip()
        parsed = pd.to_datetime(series, format="%Y%m%d", errors="coerce")

        mask = parsed.isna() & ~series.isin(_INVALID_DATE_TOKENS)
        if mask.any():
            parsed[mask] = pd.to_datetime(series[mask], errors="coerce", dayfirst=False)

        valid = parsed.notna() & (parsed.dt.year >= 1900) & (parsed.dt.year <= 2100)
        chunk[col] = parsed.dt.strftime("%Y-%m-%d").where(valid, None)

    return chunk
