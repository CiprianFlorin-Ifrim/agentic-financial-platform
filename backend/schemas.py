# backend/schemas.py
# Pydantic v2 request and response schemas for the CSE Platform API.
# All models are used for validation and serialisation across routers.

from __future__ import annotations
from typing     import Any
from pydantic   import BaseModel, Field


# -----------------------------------------------------------------------------
# Chat / Assistant
# -----------------------------------------------------------------------------

class ChatMessage(BaseModel):
    """A single turn in a conversation history."""
    role    : str   # "user" | "assistant"
    content : str


class ChatRequest(BaseModel):
    """
    Payload sent to POST /assistant/chat.
    When a CSV file accompanies the request the endpoint receives FormData;
    this model covers the JSON-only path (no file).
    """
    message      : str
    chat_history : list[ChatMessage] = Field(default_factory=list)
    session_id   : str               = Field(default="default")


# -----------------------------------------------------------------------------
# Scenario (CSV row)
# -----------------------------------------------------------------------------

class Scenario(BaseModel):
    """A single deal scenario parsed from the uploaded CSV / Excel file."""
    scenario_id     : str
    loan_amount     : float
    tenor_years     : float
    interest_rate   : float                  # Decimal, e.g. 0.045 = 4.5%
    collateral_type : str                    # "secured" | "unsecured" | "real_estate"
    client_rating   : str                    # "AAA" | "AA" | "A" | "BBB" | "BB" | "B" | "CCC"
    product_type    : str                    # "term_loan" | "revolving" | "bond"


# -----------------------------------------------------------------------------
# Engine outputs
# -----------------------------------------------------------------------------

class ARIAResult(BaseModel):
    """Risk-weighted asset output produced by the ARIA engine."""
    scenario_id    : str
    rwa_amount     : float
    capital_charge : float
    risk_weight    : float
    commentary     : str = ""


class PRISMResult(BaseModel):
    """Revenue model output produced by the PRISM engine."""
    scenario_id      : str
    nii              : float           # Net interest income
    cost_of_capital  : float
    return_on_rwa    : float
    revenue_score    : float
    commentary       : str = ""


class ScoredScenario(BaseModel):
    """Combined ARIA + PRISM result with final composite score."""
    scenario         : Scenario
    aria             : ARIAResult
    prism            : PRISMResult
    composite_score  : float
    is_best          : bool = False
    reasoning        : str  = ""


# -----------------------------------------------------------------------------
# Deals  (NEXUS)
# -----------------------------------------------------------------------------

class DealResponse(BaseModel):
    """A saved deal record returned from the NEXUS database layer."""
    id              : int
    session_id      : str
    scenario_id     : str
    loan_amount     : float
    tenor_years     : float
    interest_rate   : float
    collateral_type : str
    client_rating   : str
    product_type    : str
    rwa_amount      : float | None
    capital_charge  : float | None
    nii             : float | None
    return_on_rwa   : float | None
    score           : float | None
    reasoning       : str   | None
    created_at      : str
