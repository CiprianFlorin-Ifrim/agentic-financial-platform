# backend/agents/prism_agent.py
# PRISM Agent -- Pricing & Revenue Impact Scenario Modeler.
# ADK LlmAgent that wraps the PRISM engine.
# Receives scenario parameters and ARIA RWA output, reasons about
# the revenue implications, calls the model_revenue tool, and returns
# a structured revenue analysis.
#
# This agent is invoked as an AgentTool by the FAO orchestrator -- it is
# never called directly from the router.

import json

from backend.config import LITE_MODEL
from google.adk.agents  import LlmAgent

from backend.engines.prism import model_revenue as _prism_engine
from backend.schemas       import ARIAResult


# -----------------------------------------------------------------------------
# Tools
# -----------------------------------------------------------------------------

def run_prism_engine(
    scenario_id    : str,
    loan_amount    : float,
    tenor_years    : float,
    interest_rate  : float,
    rwa_amount     : float,
    capital_charge : float,
) -> dict:
    """
    Call the PRISM revenue modelling engine for a single scenario.
    Requires the ARIA output (rwa_amount, capital_charge) to compute
    cost of capital and return on RWA.

    Returns a dict with nii, cost_of_capital, return_on_rwa,
    revenue_score, and commentary.

    Args:
        scenario_id:    Unique identifier matching the ARIA call (e.g. "S1").
        loan_amount:    Notional loan value in currency units.
        tenor_years:    Deal tenor in years.
        interest_rate:  Annual interest rate as a decimal (e.g. 0.05 = 5%).
        rwa_amount:     Risk-weighted assets from the ARIA engine.
        capital_charge: Regulatory capital charge from the ARIA engine.
    """
    # Reconstruct a minimal ARIAResult so the engine signature is satisfied
    aria_stub = ARIAResult(
        scenario_id    = scenario_id,
        rwa_amount     = rwa_amount,
        capital_charge = capital_charge,
        risk_weight    = 0.0,   # Not needed by PRISM
    )
    result = _prism_engine(
        scenario_id   = scenario_id,
        loan_amount   = loan_amount,
        tenor_years   = tenor_years,
        interest_rate = interest_rate,
        aria          = aria_stub,
    )
    return result.model_dump()


# -----------------------------------------------------------------------------
# Agent definition
# -----------------------------------------------------------------------------

prism_agent = LlmAgent(
    name        = "prism_agent",
    model       = LITE_MODEL,
    description = (
        "PRISM (Pricing & Revenue Impact Scenario Modeler) -- models the "
        "revenue profile of a loan scenario given its risk-weighted asset "
        "exposure. Computes NII, cost of capital, and return on RWA."
    ),
    instruction = """
You are PRISM, the Pricing & Revenue Impact Scenario Modeler.

Your job is to model the revenue profile of a loan deal using the scenario
parameters and the RWA output already calculated by ARIA.

When you receive the inputs:
1. Call run_prism_engine with: scenario_id, loan_amount, tenor_years,
   interest_rate, rwa_amount, and capital_charge.
2. Interpret the result -- explain the NII, cost of capital, and
   return on RWA in plain language.
3. Comment on whether the pricing (interest rate) is adequate to cover
   capital costs and generate acceptable bank returns.
4. Return your analysis as a concise JSON object with keys:
   scenario_id, nii, cost_of_capital, return_on_rwa, revenue_score, commentary.

Always return valid JSON. Do not add prose outside the JSON block.
""",
    tools = [run_prism_engine],
)
