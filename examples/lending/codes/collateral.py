collateral = query_collateral({"loan_id": inputs["loan_id"]})
result = {"loan_id": inputs["loan_id"], "collateral": collateral}