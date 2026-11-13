"""Encaje sin LLM. Explica con una frase hecha a partir de los campos, no de un modelo."""

EU27 = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE",
}

_ENTITY = {
    "foundation": "ngo",
    "ngo": "ngo",
    "sme": "sme",
    "large_company": "large_company",
    "research": "research",
    "university": "research",
    "public_body": "public_body",
}


def explain_fit(opp, profile: dict | None) -> dict | None:
    if not profile:
        return None
    reasons: list[str] = []
    level = "possible"

    country = (profile.get("country") or "").upper()
    if country and opp.eligible_countries:
        allowed = set(opp.eligible_countries)
        in_group = country in allowed or ("EU27" in allowed and country in EU27) or "EU" in allowed
        if not in_group and opp.country and opp.country != country:
            level = "likely_ineligible"
            reasons.append(f"Does not list {country} as eligible.")
        elif in_group:
            reasons.append(f"Open to organisations in {country}.")
    elif country:
        reasons.append("Eligible countries are not specified.")

    entity = _ENTITY.get(profile.get("entity_type") or "")
    if entity and opp.eligible_entity_types:
        if entity not in opp.eligible_entity_types:
            level = "likely_ineligible"
            reasons.append(f"Entity type {profile.get('entity_type')} is not listed.")
        else:
            label = profile.get("entity_type").replace("_", " ")
            reasons.append(f"Open to a {label}.")

    wanted = set(profile.get("subsectors") or [])
    overlap = wanted & set(opp.subsectors)
    if overlap:
        reasons.append("Subsector matches yours.")
        if level == "possible":
            level = "strong"
    elif wanted and opp.subsectors:
        reasons.append("Subsector does not overlap your profile.")
        if level == "strong":
            level = "possible"

    trl = profile.get("trl")
    if trl and opp.trl_min and opp.trl_max:
        if opp.trl_min <= trl <= opp.trl_max:
            reasons.append(f"TRL {trl} sits inside {opp.trl_min}–{opp.trl_max}.")
        else:
            reasons.append(f"TRL {trl} is outside {opp.trl_min}–{opp.trl_max}.")
            if level == "strong":
                level = "check"

    if opp.consortium_required:
        countries = opp.consortium_min_countries or 0
        if countries >= 2:
            reasons.append(f"Needs a {countries}-country consortium.")
            if level == "strong":
                level = "check"
        else:
            reasons.append("A consortium is required.")

    if level == "possible" and not reasons:
        level = "check"
        reasons.append("Not enough eligibility data to score this.")

    return {"level": level, "line": " · ".join(reasons)}
