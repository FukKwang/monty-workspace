def get_borrower(name):
    return query_borrower({"name": name})

def get_borrowers_by_city(city):
    return query_borrowers_by_city({"city": city, "limit": 10})

def get_profile_summary():
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