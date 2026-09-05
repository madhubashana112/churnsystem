"""
Sector KPI feeds for the dashboards.

These are computed at analysis time from the synthesized features, because the
prediction payload alone cannot express them: revenue at risk needs the invoice
amounts, tower concentration needs the call records. Storing them on the
snapshot keeps the dashboard a pure renderer and avoids shipping every entity's
full feature vector to the browser.
"""
from statistics import mean
from typing import Any, Dict, List, Optional

from churn_platform.domain.models.customer_features import CustomerFeatures

AT_RISK_TIERS = {"CRITICAL", "HIGH", "MEDIUM"}
DORMANT_DAYS = 30


def _num(value: Any) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _pick(features: Dict[str, Any], *suffixes: str) -> Optional[float]:
    """
    First numeric feature whose name ends with one of the given suffixes.

    Feature names are prefixed by their source table, which varies with what the
    tenant uploaded, so KPIs match on the meaningful tail rather than a fixed key.
    """
    for suffix in suffixes:
        for name, value in features.items():
            if name.endswith(suffix):
                number = _num(value)
                if number is not None:
                    return number
    return None


def _mean(values: List[float]) -> float:
    return round(mean(values), 3) if values else 0.0


def compute(sector: str, features: List[CustomerFeatures], predictions: List[dict]) -> Dict[str, Any]:
    """KPI cards for one sector: a list of {label, value, unit, hint}."""
    canonical = (sector or "").strip().lower()
    by_id = {f.entity_id: f.features for f in features}

    at_risk_ids, tiers = [], {}
    for item in predictions:
        pred = item.get("prediction", {})
        entity = str(pred.get("entity_id"))
        tier = str(pred.get("risk_tier", "")).upper()
        tiers[entity] = tier
        if tier in AT_RISK_TIERS:
            at_risk_ids.append(entity)

    handler = {
        "saas": _saas,
        "telecom": _telecom,
        "fintech": _fintech,
    }.get(canonical)

    if handler is None:
        return {"sector": sector, "cards": []}

    return {"sector": sector, "cards": handler(by_id, at_risk_ids, tiers)}


def _saas(by_id, at_risk_ids, tiers) -> List[dict]:
    # Revenue exposed: the recurring amount attached to accounts at risk.
    at_risk_revenue = 0.0
    for entity in at_risk_ids:
        amount = _pick(by_id.get(entity, {}), "_amount_avg", "_amount_sum")
        seats = _pick(by_id.get(entity, {}), "seats")
        if amount:
            at_risk_revenue += amount * (seats or 1)

    velocities = [v for e in by_id if (v := _pick(by_id[e], "_activity_velocity")) is not None]
    at_risk_velocity = [v for e in at_risk_ids if (v := _pick(by_id.get(e, {}), "_activity_velocity")) is not None]
    dropped_off = sum(1 for e in by_id if (_pick(by_id[e], "_events_7d") or 0) == 0)

    return [
        {"label": "MRR at risk", "value": round(at_risk_revenue, 2), "unit": "currency",
         "hint": f"Across {len(at_risk_ids)} at-risk accounts"},
        {"label": "Login velocity", "value": _mean(at_risk_velocity), "unit": "ratio",
         "hint": f"At-risk cohort vs {_mean(velocities)} overall"},
        {"label": "Feature drop-off", "value": dropped_off, "unit": "count",
         "hint": "Accounts with no activity in the last 7 days"},
    ]


def _telecom(by_id, at_risk_ids, tiers) -> List[dict]:
    drop_rates = [v for e in by_id if (v := _pick(by_id[e], "_failure_rate")) is not None]
    at_risk_drops = [v for e in at_risk_ids if (v := _pick(by_id.get(e, {}), "_failure_rate")) is not None]
    port_outs = sum(1 for e in by_id if (_pick(by_id[e], "_mnp_port_out") or 0) > 0)

    # Region is a dimension column carried straight through from the base table.
    regions: Dict[str, List[int]] = {}
    for entity, features in by_id.items():
        region = features.get("region")
        if isinstance(region, str):
            regions.setdefault(region, []).append(1 if tiers.get(entity) in AT_RISK_TIERS else 0)
    worst_region, worst_share = "-", 0.0
    for region, flags in regions.items():
        share = sum(flags) / len(flags)
        if share > worst_share:
            worst_region, worst_share = region, share

    return [
        {"label": "Dropped-call rate", "value": _mean(at_risk_drops), "unit": "rate",
         "hint": f"At-risk cohort vs {_mean(drop_rates)} overall"},
        {"label": "Port-out enquiries", "value": port_outs, "unit": "count",
         "hint": "Subscribers who raised an MNP request"},
        {"label": "Worst region", "value": worst_region, "unit": "text",
         "hint": f"{round(worst_share * 100)}% of its subscribers are at risk"},
    ]


def _fintech(by_id, at_risk_ids, tiers) -> List[dict]:
    drains = [v for e in at_risk_ids if (v := _pick(by_id.get(e, {}), "balance_drain_ratio")) is not None]
    all_drains = [v for e in by_id if (v := _pick(by_id[e], "balance_drain_ratio")) is not None]
    dormant = sum(
        1 for e in by_id
        if (r := _pick(by_id[e], "_recency_days")) is not None and r > DORMANT_DAYS
    )
    streaks = sum(1 for e in by_id if (_pick(by_id[e], "p2p_failure_streak") or 0) >= 3)

    return [
        {"label": "Liquidity drain", "value": _mean(drains), "unit": "rate",
         "hint": f"At-risk cohort vs {_mean(all_drains)} overall"},
        {"label": "Dormant accounts", "value": dormant, "unit": "count",
         "hint": f"No transaction in over {DORMANT_DAYS} days"},
        {"label": "P2P failure streaks", "value": streaks, "unit": "count",
         "hint": "Accounts with 3+ consecutive failed transfers"},
    ]
