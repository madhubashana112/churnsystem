"""
Turning a model's JSON into domain objects.

This lives beside the three sector cores for the same reason batching lives in
the use case: the cores are near-duplicates by design, so parsing written into
each of them would mean fixing every model-output quirk three times.

A language model produces this JSON, so a malformed entry is a routine event
rather than an exceptional one, and the handling matches the rest of the
codebase: recover what is recoverable, reject what is not. An unreadable entry
is dropped with a warning instead of discarding its batch -- at the configured
batch size that would cost up to ten scored accounts, and half of a capped Qwen
run. A response that yields nothing usable for a non-empty batch raises, so the
caller falls back to the local engine rather than reporting a run with no
accounts in it.
"""
import json
import logging
from typing import Any, Dict, List, Sequence, Tuple

from churn_platform.domain.models.churn_prediction import ChurnPrediction
from churn_platform.domain.models.customer_features import CustomerFeatures
from churn_platform.domain.models.retention_playbook import RetentionPlaybook

logger = logging.getLogger(__name__)

# What goes wrong when JSON of the wrong shape is indexed, unpacked or validated.
# pydantic's ValidationError is a ValueError, so it is covered here.
MALFORMED = (AttributeError, KeyError, TypeError, ValueError)

Scored = Tuple[ChurnPrediction, RetentionPlaybook]


def build_user_prompt(features: Sequence[CustomerFeatures]) -> str:
    payload = json.dumps([f.model_dump() for f in features], default=str)
    return f"Analyze these customer features:\n{payload}"


def parse_predictions(
    response: Any,
    requested: Sequence[CustomerFeatures],
    sector_fields: Sequence[str] = (),
) -> List[Scored]:
    """
    Read the scored entities out of a model response.

    `sector_fields` names the optional fields this sector adds to the shared
    prediction shape -- the root cause for Telecom, the dormancy type for
    FinTech -- which are lifted from the response when present.
    """
    entries = _entries(response)
    known = {f.entity_id for f in requested}

    results: List[Scored] = []
    unreadable = 0
    unrequested = 0

    for entry in entries:
        try:
            prediction, playbook = _scored_entity(entry, sector_fields)
        except MALFORMED as exc:
            unreadable += 1
            logger.warning("Dropping an unreadable prediction entry: %s", exc)
            continue

        # An id that was never sent is a hallucinated account. Keeping it would
        # put an entity with drivers but no features on the dashboard and count
        # it as scored.
        if known and prediction.entity_id not in known:
            unrequested += 1
            logger.warning(
                "Dropping a prediction for %r, which was not in the batch.",
                prediction.entity_id,
            )
            continue

        results.append((prediction, playbook))

    dropped = unreadable + unrequested
    if requested and not results:
        raise ValueError(
            f"The model returned no usable predictions for {len(requested)} "
            f"entities ({len(entries)} entries, {dropped} unusable)."
        )
    if dropped:
        logger.warning(
            "Scored %d of %d entities; %d unreadable, %d not in the batch.",
            len(results), len(requested), unreadable, unrequested,
        )
    return results


def _entries(response: Any) -> List[Any]:
    if not isinstance(response, dict):
        return []
    entries = response.get("predictions")
    return list(entries) if isinstance(entries, list) else []


def _scored_entity(entry: Any, sector_fields: Sequence[str]) -> Scored:
    block: Dict[str, Any] = entry["churn_prediction"]
    prediction = ChurnPrediction(
        entity_id=entry["entity_id"],
        churn_probability=block["churn_probability"],
        risk_tier=block["risk_tier"],
        **{field: block.get(field) for field in sector_fields},
    )
    return prediction, RetentionPlaybook(**entry["retention_playbook"])
