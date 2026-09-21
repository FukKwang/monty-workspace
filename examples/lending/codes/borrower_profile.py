"""Look up borrower profile by name.

Args:
    borrower_name: Full name of borrower to search

Returns:
    borrower_id: Unique borrower identifier
    name: Borrower full name
    address: Street address
    city: City of residence
    phone: Phone number
    email: Email address
    credit_score: Credit score (300-850)
    monthly_income: Monthly income in IDR
    employment_status: Employment status (employed, self_employed, unemployed)
"""
borrower = query_borrower({"name": inputs["borrower_name"]})

result = {
    "borrower_id": borrower.get("borrower_id") if borrower else None,
    "name": borrower.get("name") if borrower else None,
    "address": borrower.get("address") if borrower else None,
    "city": borrower.get("city") if borrower else None,
    "phone": borrower.get("phone") if borrower else None,
    "email": borrower.get("email") if borrower else None,
    "credit_score": borrower.get("credit_score") if borrower else None,
    "monthly_income": borrower.get("monthly_income") if borrower else None,
    "employment_status": borrower.get("employment_status") if borrower else None,
}
