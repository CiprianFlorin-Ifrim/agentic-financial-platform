# backend/agents/apex_agent.py
# APEX Agent -- Assessment & Pricing EXpert.
# ADK LlmAgent responsible for evaluating all scored scenarios and selecting
# the best one based on a composite scoring function.
#
# "Best" is defined as the scenario that maximises bank return (return_on_rwa)
# while keeping the client cost (interest_rate) as low as possible.
#
# This agent is invoked as an AgentTool by the FAO orchestrator -- it is
# never called directly from the router.

import json

from backend.config import LITE_MODEL
from google.adk.agents import LlmAgent


# -----------------------------------------------------------------------------
# Tools
# -----------------------------------------------------------------------------

def compute_composite_scores(scenarios_json: str) -> dict:
    """
    Compute composite scores for a list of evaluated scenarios and return
    the ranked list with the best scenario flagged.

    The composite score weights:
        60%  -- return_on_rwa  (higher = better for bank)
        40%  -- inverse of interest_rate  (lower rate = better for client)

    Args:
        scenarios_json: JSON string -- a list of dicts, each containing:
                        scenario_id, interest_rate, rwa_amount, capital_charge,
                        nii, return_on_rwa, revenue_score.
                        Example:
                        [{"scenario_id":"S1","interest_rate":0.05,
                          "return_on_rwa":0.021,"revenue_score":0.42, ...}]
    """
    try:
        scenarios = json.loads(scenarios_json)
    except json.JSONDecodeError as exc:
        return {"error": f"Invalid JSON: {exc}"}

    if not scenarios:
        return {"error": "No scenarios provided."}

    # Normalise each metric to [0, 1] across the scenario set before weighting
    rors   = [s.get("return_on_rwa", 0)   for s in scenarios]
    rates  = [s.get("interest_rate", 0.1) for s in scenarios]

    max_ror  = max(rors)  if max(rors)  > 0 else 1
    min_rate = min(rates) if min(rates) > 0 else 0.001
    max_rate = max(rates) if max(rates) > 0 else 1

    scored = []
    for s in scenarios:
        norm_ror  = s.get("return_on_rwa", 0) / max_ror
        # Lower rate is better -- invert normalisation
        rate_range = max_rate - min_rate
        norm_rate  = (
            (max_rate - s.get("interest_rate", max_rate)) / rate_range
            if rate_range > 0 else 1.0
        )
        composite = 0.60 * norm_ror + 0.40 * norm_rate
        scored.append({**s, "composite_score": round(composite, 4)})

    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    scored[0]["is_best"] = True
    for s in scored[1:]:
        s["is_best"] = False

    return {"ranked_scenarios": scored, "best_scenario_id": scored[0]["scenario_id"]}


# -----------------------------------------------------------------------------
# Agent definition
# -----------------------------------------------------------------------------

apex_agent = LlmAgent(
    name        = "apex_agent",
    model       = LITE_MODEL,
    description = (
        "APEX (Assessment & Pricing EXpert) -- evaluates all scenario results "
        "from ARIA and PRISM, computes composite scores, identifies the best "
        "deal for both the bank and the client, and provides a clear recommendation."
    ),
    instruction = """
You are APEX, the Assessment & Pricing EXpert for the FAO Platform.

Your job is to evaluate a set of fully-scored deal scenarios and select
the best one. "Best" means the optimal balance between:
  -- Maximum return on RWA for the bank.
  -- Minimum interest rate burden for the client.

When you receive scenario data:
1. Call compute_composite_scores with a JSON array of all scenarios.
   Each item must include: scenario_id, interest_rate, return_on_rwa, revenue_score.
2. Review the ranked output.
3. Write a clear recommendation explaining:
   a. Which scenario is best and why.
   b. What trade-offs were made (e.g. a slightly higher rate that significantly
      improves RWA efficiency).
   c. Any scenarios worth flagging as risky or suboptimal.

Return your output as JSON with keys:
  best_scenario_id, ranked_scenarios, recommendation (a 2-3 sentence plain-English
  summary suitable for presenting to the end user).

Always return valid JSON. Do not add prose outside the JSON block.
""",
    tools = [compute_composite_scores],
)
