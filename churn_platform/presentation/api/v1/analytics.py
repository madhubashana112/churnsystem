from collections import Counter
from statistics import mean, median
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query, Response

from churn_platform.presentation.api.dependencies import get_analysis_repo, get_tenant_repo

router = APIRouter(prefix="/analytics", tags=["Analytics"])

TIERS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


def _tier_of(prediction: Dict[str, Any]) -> str:
    tier = str(prediction.get("risk_tier") or "").strip().upper()
    return tier if tier in TIERS else "MEDIUM"


def _drivers_of(prediction: Dict[str, Any]) -> List[str]:
    """Each sector core explains itself under a different key."""
    drivers = prediction.get("primary_drivers") or []
    for fallback in ("root_cause", "dormancy_type"):
        value = prediction.get(fallback)
        if not drivers and value:
            drivers = [str(value)]
    return [str(d) for d in drivers]


def _summarise(predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
    preds = [item.get("prediction", {}) for item in predictions]
    books = [item.get("playbook") or {} for item in predictions]

    probabilities = [float(p.get("churn_probability") or 0.0) for p in preds]
    tiers = [_tier_of(p) for p in preds]
    tier_counts = Counter(tiers)

    driver_counts = Counter(d for p in preds for d in _drivers_of(p))

    return {
        "total_scored": len(preds),
        "at_risk": sum(1 for t in tiers if t != "LOW"),
        "tier_counts": {tier: tier_counts.get(tier, 0) for tier in TIERS},
        "avg_churn_probability": round(mean(probabilities), 4) if probabilities else 0.0,
        "median_churn_probability": round(median(probabilities), 4) if probabilities else 0.0,
        "max_churn_probability": round(max(probabilities), 4) if probabilities else 0.0,
        "probability_bands": _bands(probabilities),
        "top_drivers": [
            {"driver": driver, "count": count} for driver, count in driver_counts.most_common(6)
        ],
        "channel_mix": [
            {"channel": channel, "count": count}
            for channel, count in Counter(b.get("channel") for b in books if b.get("channel")).most_common()
        ],
        "action_mix": [
            {"action_type": action, "count": count}
            for action, count in Counter(b.get("action_type") for b in books if b.get("action_type")).most_common()
        ],
    }


def _bands(probabilities: List[float]) -> List[Dict[str, Any]]:
    labels = ["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"]
    counts = [0] * 5
    for value in probabilities:
        counts[min(int(value * 5), 4)] += 1
    return [{"band": label, "count": count} for label, count in zip(labels, counts)]


async def _require_snapshot(tenant_id: str):
    """
    The snapshot, or None when the tenant is known but has not run anything yet.
    A missing tenant is an error; an empty workspace is not.
    """
    if not await get_tenant_repo().get(tenant_id):
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return await get_analysis_repo().get_latest(tenant_id)


@router.get("/metrics")
async def get_metrics(tenant_id: str = Query(..., description="Tenant to summarise")):
    """Aggregate view of the most recent analysis run, or 204 if there is none."""
    snapshot = await _require_snapshot(tenant_id)
    if snapshot is None:
        return Response(status_code=204)
    return {
        "status": "ok",
        "created_at": snapshot.created_at.isoformat(),
        "source": snapshot.source,
        "engine": snapshot.engine,
        "engine_reason": snapshot.engine_reason,
        "source_files": [f.model_dump() for f in snapshot.source_files],
        "sector_kpis": snapshot.sector_kpis,
        "metrics": _summarise(snapshot.predictions),
    }


@router.get("/latest")
async def get_latest_analysis(tenant_id: str = Query(..., description="Tenant to load")):
    """The full stored result, so the dashboard survives a page refresh."""
    snapshot = await _require_snapshot(tenant_id)
    if snapshot is None:
        return Response(status_code=204)
    return {
        "schema_mapping": snapshot.schema_mapping.model_dump(),
        "predictions": snapshot.predictions,
        "source_files": [f.model_dump() for f in snapshot.source_files],
        "created_at": snapshot.created_at.isoformat(),
        "source": snapshot.source,
        "engine": snapshot.engine,
        "engine_reason": snapshot.engine_reason,
        "entities_scored": len(snapshot.predictions),
        "sector_kpis": snapshot.sector_kpis,
        "metrics": _summarise(snapshot.predictions),
    }
