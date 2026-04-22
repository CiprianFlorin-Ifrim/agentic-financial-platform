# backend/engines/prism.py
# PRISM -- Pricing & Revenue Impact Scenario Modeler.
# Mock revenue modelling engine.
# Takes scenario parameters plus ARIA RWA output and returns revenue metrics
# including NII, cost of capital, and return on RWA.
#
# This is a deterministic mock -- no external calls are made.
# In a real system this would call the actual PRISM service.

from backend.schemas import ARIAResult, PRISMResult


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

# Hurdle rate -- cost of equity capital (used to price capital charge)
_COST_OF_EQUITY: float = 0.12         # 12%

# Operating cost ratio applied to gross revenue
_OPERATING_COST_RATIO: float = 0.20   # 20% of NII


# -----------------------------------------------------------------------------
# Public interface
# -----------------------------------------------------------------------------

def model_revenue(
    scenario_id   : str,
    loan_amount   : float,
    tenor_years   : float,
    interest_rate : float,
    aria          : ARIAResult,
) -> PRISMResult:
    """
    Model the revenue profile for one scenario using ARIA's RWA output.

    Metrics:
        NII               = loan_amount * interest_rate * tenor_years
        Cost of capital   = capital_charge * cost_of_equity * tenor_years
        Operating costs   = NII * operating_cost_ratio
        Net revenue       = NII - cost_of_capital - operating_costs
        Return on RWA     = net_revenue / RWA  (annualised)
        Revenue score     = return_on_rwa / (interest_rate * 100)
                            -- normalises return relative to rate charged,
                               a higher score = better bank / client balance
    """
    nii              = loan_amount * interest_rate * tenor_years
    cost_of_capital  = aria.capital_charge * _COST_OF_EQUITY * tenor_years
    operating_costs  = nii * _OPERATING_COST_RATIO
    net_revenue      = nii - cost_of_capital - operating_costs

    # Avoid division by zero on degenerate RWA values
    return_on_rwa    = (net_revenue / aria.rwa_amount) if aria.rwa_amount > 0 else 0.0

    # Revenue score: penalises high client rates while rewarding bank return
    # Range is roughly 0--1 for typical deal parameters
    revenue_score    = return_on_rwa / (interest_rate * 100) if interest_rate > 0 else 0.0

    commentary = (
        f"NII over {tenor_years}y at {interest_rate:.2%}: {nii:,.0f}. "
        f"Cost of capital ({_COST_OF_EQUITY:.0%} hurdle): {cost_of_capital:,.0f}. "
        f"Operating costs ({_OPERATING_COST_RATIO:.0%} of NII): {operating_costs:,.0f}. "
        f"Net revenue: {net_revenue:,.0f}. "
        f"Return on RWA (annualised): {return_on_rwa:.4f}. "
        f"Revenue score: {revenue_score:.4f}."
    )

    return PRISMResult(
        scenario_id     = scenario_id,
        nii             = round(nii, 2),
        cost_of_capital = round(cost_of_capital, 2),
        return_on_rwa   = round(return_on_rwa, 6),
        revenue_score   = round(revenue_score, 6),
        commentary      = commentary,
    )
