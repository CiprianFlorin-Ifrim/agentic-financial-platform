# backend/agents/nexus_agent.py
# NEXUS Agent -- Deal & Scenario Persistence Layer.
# ADK LlmAgent responsible for saving deals to the database and
# retrieving past deals on request.
#
# This agent is invoked as an AgentTool by the FAO orchestrator -- it is
# never called directly from the router.

import json

from backend.config import LITE_MODEL
from google.adk.agents import LlmAgent

from backend.database  import save_deal, get_deals, get_deal_by_id


# -----------------------------------------------------------------------------
# Tools
# -----------------------------------------------------------------------------

def persist_deal(deal_json: str) -> dict:
    """
    Save the best scenario as a deal record in the NEXUS database.
    Returns the new deal id and a confirmation message.

    Args:
        deal_json: JSON string with keys:
                   session_id, scenario_id, loan_amount, tenor_years,
                   interest_rate, collateral_type, client_rating,
                   product_type, rwa_amount, capital_charge, nii,
                   return_on_rwa, score, reasoning.
    """
    try:
        d = json.loads(deal_json)
    except json.JSONDecodeError as exc:
        return {"error": f"Invalid JSON: {exc}"}

    try:
        deal_id = save_deal(
            session_id      = d.get("session_id",      "default"),
            scenario_id     = d["scenario_id"],
            loan_amount     = d["loan_amount"],
            tenor_years     = d["tenor_years"],
            interest_rate   = d["interest_rate"],
            collateral_type = d["collateral_type"],
            client_rating   = d["client_rating"],
            product_type    = d["product_type"],
            rwa_amount      = d.get("rwa_amount",      0.0),
            capital_charge  = d.get("capital_charge",  0.0),
            nii             = d.get("nii",             0.0),
            return_on_rwa   = d.get("return_on_rwa",   0.0),
            score           = d.get("score",           0.0),
            reasoning       = d.get("reasoning",       ""),
        )
        return {"deal_id": deal_id, "status": "saved", "scenario_id": d["scenario_id"]}
    except KeyError as exc:
        return {"error": f"Missing required field: {exc}"}


def fetch_recent_deals(session_id: str = "", limit: int = 5) -> dict:
    """
    Retrieve recent deals from NEXUS, optionally scoped to a session.
    Returns a list of deal records ordered by most recent first.

    Args:
        session_id: Optional session identifier to filter results.
                    Pass an empty string to retrieve across all sessions.
        limit:      Maximum number of records to return (default 5, max 20).
    """
    limit = min(int(limit), 20)
    deals = get_deals(session_id=session_id or None, limit=limit)
    return {"deals": deals, "count": len(deals)}


def fetch_deal(deal_id: int) -> dict:
    """
    Retrieve a single deal by its database id.

    Args:
        deal_id: Integer primary key of the deal record.
    """
    deal = get_deal_by_id(int(deal_id))
    if not deal:
        return {"error": f"Deal {deal_id} not found."}
    return {"deal": deal}


# -----------------------------------------------------------------------------
# Agent definition
# -----------------------------------------------------------------------------

nexus_agent = LlmAgent(
    name        = "nexus_agent",
    model       = LITE_MODEL,
    description = (
        "NEXUS -- Deal & Scenario Persistence Layer. Saves the best scenario "
        "as a deal record and retrieves past deals from the database on request."
    ),
    instruction = """
You are NEXUS, the deal persistence agent for the FAO Platform.

Your responsibilities:
  -- Save deal records to the database when instructed to persist a result.
  -- Retrieve recent deals or a specific deal when the user asks.

Saving a deal:
  Call persist_deal with a JSON string containing all required fields.
  Confirm with the deal id and scenario id on success.

Retrieving deals:
  Call fetch_recent_deals for a list. Call fetch_deal for a specific record.
  Format the results as a clean markdown table for the user.

Return all responses as JSON with a human_message key containing a brief,
plain-English confirmation or summary suitable for showing in the chat UI.

Always return valid JSON. Do not add prose outside the JSON block.
""",
    tools = [persist_deal, fetch_recent_deals, fetch_deal],
)
