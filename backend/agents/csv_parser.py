# backend/agents/csv_parser.py
# CSV / Excel scenario parser.
# Reads an uploaded file and returns a validated list of Scenario objects.
# Called by the CSE orchestrator before the agent pipeline starts.
#
# Supported formats: .csv, .xlsx, .xls
# Required columns (case-insensitive):
#   scenario_id, loan_amount, tenor_years, interest_rate,
#   collateral_type, client_rating, product_type

from __future__ import annotations

import io
import pandas as pd

from backend.schemas import Scenario


# -----------------------------------------------------------------------------
# Column normalisation
# -----------------------------------------------------------------------------

_REQUIRED_COLUMNS = {
    "scenario_id",
    "loan_amount",
    "tenor_years",
    "interest_rate",
    "collateral_type",
    "client_rating",
    "product_type",
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace and lowercase all column names."""
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


# -----------------------------------------------------------------------------
# Public interface
# -----------------------------------------------------------------------------

def parse_scenarios(file_bytes: bytes, filename: str) -> list[Scenario]:
    """
    Parse a CSV or Excel file into a list of validated Scenario objects.

    Raises ValueError if required columns are missing or no valid rows found.
    """
    ext = filename.rsplit(".", 1)[-1].lower()
    buf = io.BytesIO(file_bytes)

    if ext == "csv":
        df = pd.read_csv(buf)
    elif ext in ("xlsx", "xls"):
        df = pd.read_excel(buf)
    else:
        raise ValueError(f"Unsupported file type: .{ext}")

    df = _normalise_columns(df)

    missing = _REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns: {', '.join(sorted(missing))}. "
            f"Found: {', '.join(df.columns.tolist())}."
        )

    scenarios: list[Scenario] = []
    errors:    list[str]      = []

    for idx, row in df.iterrows():
        try:
            s = Scenario(
                scenario_id     = str(row["scenario_id"]).strip(),
                loan_amount     = float(row["loan_amount"]),
                tenor_years     = float(row["tenor_years"]),
                interest_rate   = float(row["interest_rate"]),
                collateral_type = str(row["collateral_type"]).strip().lower(),
                client_rating   = str(row["client_rating"]).strip().upper(),
                product_type    = str(row["product_type"]).strip().lower(),
            )
            scenarios.append(s)
        except (ValueError, KeyError) as exc:
            errors.append(f"Row {idx + 2}: {exc}")

    if not scenarios:
        detail = "; ".join(errors) if errors else "No data rows found."
        raise ValueError(f"Could not parse any valid scenarios. {detail}")

    return scenarios
