borrower = query_borrower({"name": inputs["borrower_name"]})
loans = query_loans({"borrower_id": borrower["borrower_id"]})

result = {
    "borrower_name": inputs["borrower_name"],
    "borrower_id": borrower.get("borrower_id"),
    "borrower": borrower,
    "loans": loans,
}