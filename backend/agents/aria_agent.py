# backend/agents/aria_agent.py
# ARIA Agent -- Asset Risk & Impact Analyzer.
# ADK LlmAgent that wraps the ARIA engine.
# Receives one scenario dict, reasons about the risk profile,
# calls the calculate_rwa tool, and returns a structured commentary.
#
# This agent is invoked as an AgentTool by the FAO orchestrator -- it is
# never called directly from the router.

import json

from backend.config import LITE_MODEL
from google.adk.agents  import LlmAgent

from backend.engines.aria  import calculate_rwa as _aria_engine
from backend.schemas       import ARIAResult


# -----------------------------------------------------------------------------
# Tools
# -----------------------------------------------------------------------------

def run_aria_engine(
    scenario_id     : str,
    loan_amount     : float,
    tenor_years     : float,
    collateral_type : str,
    client_rating   : str,
    product_type    : str,
) -> dict:
    """
    Call the ARIA RWA calculation engine for a single scenario.
    Returns a dict containing rwa_amount, capital_charge, risk_weight
    and a plain-English commentary.

    Args:
        scenario_id:     Unique identifier for this scenario (e.g. "S1").
        loan_amount:     Notional loan value in currency units.
        tenor_years:     Deal tenor in years.
        collateral_type: One of: secured, unsecured, real_estate.
        client_rating:   Credit rating string: AAA, AA, A, BBB, BB, B, CCC.
        product_type:    One of: term_loan, revolving, bond.
    """
    result = _aria_engine(
        scenario_id     = scenario_id,
        loan_amount     = loan_amount,
        tenor_years     = tenor_years,
        collateral_type = collateral_type,
        client_rating   = client_rating,
        product_type    = product_type,
    )
    return result.model_dump()


# -----------------------------------------------------------------------------
# Agent definition
# -----------------------------------------------------------------------------

aria_agent = LlmAgent(
    name        = "aria_agent",
    model       = LITE_MODEL,
    description = (
        "ARIA (Asset Risk & Impact Analyzer) -- calculates Risk-Weighted Assets "
        "and regulatory capital charges for a loan scenario using Basel III rules."
    ),
    instruction = """
You are ARIA, the Asset Risk & Impact Analyzer.

Your job is to assess the capital risk of a single loan scenario.

When you receive scenario parameters:
1. Call run_aria_engine with all the scenario fields.
2. Interpret the result -- explain in plain language what the RWA and capital
   charge mean for this deal.
3. Flag anything unusual (e.g. very high risk weight due to low rating, or
   beneficial collateral offset).
4. Return your analysis as a concise JSON object with keys:
   scenario_id, rwa_amount, capital_charge, risk_weight, commentary.

Always return valid JSON. Do not add prose outside the JSON block.
""",
    tools = [run_aria_engine],
)
