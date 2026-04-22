# backend/routers/deals.py
# Deals router.
# REST endpoints for querying the NEXUS deal database directly.
# These are used by the frontend for non-chat queries (e.g. listing deals
# in a table, fetching a specific deal by id).
#
# Routes:
#   GET  /deals            -- list recent deals (optional ?session_id=&limit=)
#   GET  /deals/{deal_id}  -- fetch a single deal by id

from fastapi        import APIRouter, HTTPException, Query
from backend.database import get_deals, get_deal_by_id
from backend.schemas  import DealResponse


# -----------------------------------------------------------------------------
# Router
# -----------------------------------------------------------------------------

router = APIRouter()


# -----------------------------------------------------------------------------
# List deals
# -----------------------------------------------------------------------------

@router.get("/", response_model=list[DealResponse])
def list_deals(
    session_id : str = Query(default="",  description="Filter by session id"),
    limit      : int = Query(default=20,  description="Maximum number of records", le=100),
):
    """Return recent deals from NEXUS, newest first."""
    return get_deals(session_id=session_id or None, limit=limit)


# -----------------------------------------------------------------------------
# Single deal
# -----------------------------------------------------------------------------

@router.get("/{deal_id}", response_model=DealResponse)
def get_deal(deal_id: int):
    """Return a single deal record by its database id."""
    deal = get_deal_by_id(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found.")
    return deal
