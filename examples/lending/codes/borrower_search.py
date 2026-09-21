"""Borrower search utilities.

Provides functions to look up borrowers by name or city
and generate profile summaries.

Args:
    name: Borrower name to search (optional)
    city: City to search (optional)
"""

def get_borrower(name: str) -> dict:
    """Look up a single borrower by name.

    Args:
        name: Full name of the borrower to search

    Returns:
        borrower_id: Unique borrower identifier
        name: Borrower full name
        address: Street address
        city: City of residence
        credit_score: Credit score (300-850)
        monthly_income: Monthly income in IDR
    """
    return query_borrower({"name": name})

def get_borrowers_by_city(city: str, limit: int = 10) -> list:
    """Search borrowers in a specific city.

    Args:
        city: City name to filter by
        limit: Maximum results to return (default 10)

    Returns:
        borrower_id: Unique borrower identifier
        name: Borrower full name
        city: City of residence
        credit_score: Credit score (300-850)
        total_loans: Number of active loans
        total_outstanding: Total outstanding balance in IDR
    """
    return query_borrowers_by_city({"city": city, "limit": limit})

def get_profile_summary() -> dict:
    """Get borrower profile summary from inputs.

    Uses inputs['name'] or inputs['city'] to find a borrower.

    Returns:
        profile_summary: Borrower profile dict or empty dict if not found
    """
    name = inputs.get("name")
    city = inputs.get("city")
    profile = None
    if name:
        profile = get_borrower(name)
    elif city:
        borrowers = get_borrowers_by_city(city)
        if borrowers:
            profile = borrowers[0]
    if profile is None:
        profile = {}
    return {"profile_summary": profile}

result = get_profile_summary()
