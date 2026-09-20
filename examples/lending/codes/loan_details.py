loan = query_loan_details({"loan_id": inputs["loan_id"]})
result = {
    "loan_id": inputs["loan_id"],
    "loan": loan,
    "payments": loan.get("payments") or [],
    "collateral": loan.get("collateral") or [],
    "collection_records": loan.get("collection_records") or [],
}