# backend/engines/aria.py
# ARIA -- Asset Risk & Impact Analyzer.
# Mock RWA calculation engine.
# Accepts scenario parameters and returns risk-weighted asset exposure
# and regulatory capital charge based on simplified Basel III rules.
#
# This is a deterministic mock -- no external calls are made.
# In a real system this would call the actual ARIA service.

from backend.schemas import ARIAResult


# -----------------------------------------------------------------------------
# Risk weight tables  (simplified Basel III standardised approach)
# -----------------------------------------------------------------------------

# Credit risk weights by client rating
_RATING_WEIGHTS: dict[str, float] = {
    "AAA": 0.20,
    "AA" : 0.20,
    "A"  : 0.50,
    "BBB": 1.00,
    "BB" : 1.00,
    "B"  : 1.50,
    "CCC": 1.50,
}

# Collateral modifier -- reduces effective risk weight when security is held
_COLLATERAL_MODIFIER: dict[str, float] = {
    "secured"      : 0.70,
    "unsecured"    : 1.00,
    "real_estate"  : 0.50,
}

# Product-type modifier
_PRODUCT_MODIFIER: dict[str, float] = {
    "term_loan"  : 1.00,
    "revolving"  : 1.10,    # Higher due to drawdown uncertainty
    "bond"       : 0.90,
}

# Basel III minimum capital ratio
_MIN_CAPITAL_RATIO: float = 0.08


# -----------------------------------------------------------------------------
# Public interface
# -----------------------------------------------------------------------------

def calculate_rwa(
    scenario_id     : str,
    loan_amount     : float,
    tenor_years     : float,
    collateral_type : str,
    client_rating   : str,
    product_type    : str,
) -> ARIAResult:
    """
    Calculate risk-weighted assets and capital charge for one scenario.

    RWA formula:
        RWA = loan_amount
              * rating_weight
              * collateral_modifier
              * product_modifier

    Capital charge = RWA * 0.08  (Basel III minimum)
    """
    rating     = client_rating.upper().strip()
    collateral = collateral_type.lower().strip()
    product    = product_type.lower().strip()

    # Fall back to a conservative weight if an unknown value is supplied
    rw         = _RATING_WEIGHTS.get(rating, 1.50)
    coll_mod   = _COLLATERAL_MODIFIER.get(collateral, 1.00)
    prod_mod   = _PRODUCT_MODIFIER.get(product, 1.00)

    # Tenor scaling -- longer tenors carry marginally more risk (simplified)
    tenor_mod  = 1.0 + (tenor_years - 1) * 0.02

    risk_weight    = rw * coll_mod * prod_mod * tenor_mod
    rwa_amount     = loan_amount * risk_weight
    capital_charge = rwa_amount * _MIN_CAPITAL_RATIO

    commentary = (
        f"Rating {rating} carries a base weight of {rw:.0%}. "
        f"Collateral ({collateral_type}) applies a {coll_mod:.2f}x modifier. "
        f"Product type ({product_type}) applies a {prod_mod:.2f}x modifier. "
        f"Tenor ({tenor_years}y) adds a {tenor_mod:.3f}x scaling. "
        f"Effective risk weight: {risk_weight:.3f}. "
        f"RWA: {rwa_amount:,.0f}. "
        f"Capital charge at 8%: {capital_charge:,.0f}."
    )

    return ARIAResult(
        scenario_id    = scenario_id,
        rwa_amount     = round(rwa_amount, 2),
        capital_charge = round(capital_charge, 2),
        risk_weight    = round(risk_weight, 4),
        commentary     = commentary,
    )
