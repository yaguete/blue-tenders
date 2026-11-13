"""Aplica reglas de programa solo en campos vacíos. Nunca toca un plazo."""

from app.catalog import basins_for_nuts, rule_for
from app.models.opportunity import Fact, FactOrigin, Opportunity

_FILL = (
    "consortium_required",
    "consortium_min_partners",
    "consortium_min_countries",
    "cofunding_min",
    "cofunding_max",
)


def apply_programme_rules(opp: Opportunity) -> Opportunity:
    rule = rule_for(opp.programme_id, opp.type_of_action)
    if rule is None:
        return opp
    for field in _FILL:
        if getattr(opp, field) is not None:
            continue
        value = getattr(rule, field)
        if value is None:
            continue
        setattr(opp, field, value)
        opp.facts.append(
            Fact(
                field=field,
                value=value,
                origin=FactOrigin.programme_rule,
                confidence=0.7,
                quote=rule.legal_basis,
                model=rule.id,
            )
        )
    if not opp.eligible_entity_types and rule.eligible_entity_types:
        opp.eligible_entity_types = list(rule.eligible_entity_types)
        opp.facts.append(
            Fact(
                field="eligible_entity_types",
                value=opp.eligible_entity_types,
                origin=FactOrigin.programme_rule,
                confidence=0.7,
                quote=rule.legal_basis,
                model=rule.id,
            )
        )
    if not opp.eligible_countries and rule.eligible_countries:
        opp.eligible_countries = list(rule.eligible_countries)
        opp.facts.append(
            Fact(
                field="eligible_countries",
                value=opp.eligible_countries,
                origin=FactOrigin.programme_rule,
                confidence=0.7,
                model=rule.id,
            )
        )
    return opp


def apply_sea_basins(opp: Opportunity) -> Opportunity:
    if opp.sea_basins:
        return opp
    basins = basins_for_nuts(opp.nuts or ([opp.region] if opp.region else []))
    if not basins:
        return opp
    opp.sea_basins = basins
    opp.facts.append(
        Fact(
            field="sea_basins",
            value=basins,
            origin=FactOrigin.programme_rule,
            confidence=0.6,
            model="nuts-prefix",
        )
    )
    return opp
