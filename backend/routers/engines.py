# backend/routers/engines.py
# Engines router.
# Exposes the ARIA and PRISM mock engines as HTTP endpoints.
# Agents can call these over HTTP; the endpoints can also be hit
# directly via the Swagger UI for manual testing.
#
# Routes:
#   POST /engines/aria   -- calculate RWA for one scenario
#   POST /engines/prism  -- model revenue for one scenario

from fastapi         import APIRouter, HTTPException
from pydantic        import BaseModel

from backend.engines.aria  import calculate_rwa
from backend.engines.prism import model_revenue
from backend.schemas       import ARIAResult, PRISMResult


# -----------------------------------------------------------------------------
# Router
# -----------------------------------------------------------------------------

router = APIRouter()


# -----------------------------------------------------------------------------
# Request bodies
# -----------------------------------------------------------------------------

class ARIARequest(BaseModel):
    """Input payload for the ARIA RWA calculation engine."""
    scenario_id     : str
    loan_amount     : float
    tenor_years     : float
    collateral_type : str
    client_rating   : str
    product_type    : str


class PRISMRequest(BaseModel):
    """
    Input payload for the PRISM revenue modelling engine.
    Requires rwa_amount and capital_charge from a prior ARIA call.
    """
    scenario_id    : str
    loan_amount    : float
    tenor_years    : float
    interest_rate  : float
    rwa_amount     : float
    capital_charge : float


# -----------------------------------------------------------------------------
# ARIA endpoint
# -----------------------------------------------------------------------------

@router.post("/aria", response_model=ARIAResult)
def run_aria(req: ARIARequest):
    """
    Calculate risk-weighted assets and capital charge for a single scenario.

    Uses simplified Basel III standardised approach:
      - Rating-based risk weight
      - Collateral modifier (secured / unsecured / real_estate)
      - Product-type modifier (term_loan / revolving / bond)
      - Tenor scaling (+2% per year above year 1)
    """
    try:
        return calculate_rwa(
            scenario_id     = req.scenario_id,
            loan_amount     = req.loan_amount,
            tenor_years     = req.tenor_years,
            collateral_type = req.collateral_type,
            client_rating   = req.client_rating,
            product_type    = req.product_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# -----------------------------------------------------------------------------
# PRISM endpoint
# -----------------------------------------------------------------------------

@router.post("/prism", response_model=PRISMResult)
def run_prism(req: PRISMRequest):
    """
    Model the revenue profile for a single scenario.

    Computes:
      - NII (loan_amount * interest_rate * tenor_years)
      - Cost of capital (capital_charge * 12% hurdle * tenor_years)
      - Operating costs (20% of NII)
      - Return on RWA (net_revenue / rwa_amount, annualised)
      - Revenue score (return_on_rwa normalised by interest rate)
    """
    from backend.schemas import ARIAResult as _AR

    aria_stub = _AR(
        scenario_id    = req.scenario_id,
        rwa_amount     = req.rwa_amount,
        capital_charge = req.capital_charge,
        risk_weight    = 0.0,
    )
    try:
        return model_revenue(
            scenario_id   = req.scenario_id,
            loan_amount   = req.loan_amount,
            tenor_years   = req.tenor_years,
            interest_rate = req.interest_rate,
            aria          = aria_stub,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))
