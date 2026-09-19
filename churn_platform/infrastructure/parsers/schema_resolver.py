import json
import logging
from collections import Counter
from typing import Any, Dict, List

from churn_platform.domain.interfaces.i_schema_resolver import ISchemaResolver
from churn_platform.domain.models.schema_mapping import SchemaMapping, TableClassification
from churn_platform.infrastructure.ai.qwen_gateway import QwenGateway
from churn_platform.infrastructure.ai.prompts.schema_resolver_prompts import (
    SCHEMA_RESOLVER_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

# Indexing, unpacking or validating JSON of the wrong shape. pydantic's
# ValidationError is a ValueError, so it is covered here.
MALFORMED = (AttributeError, KeyError, TypeError, ValueError)


class AISchemaResolver(ISchemaResolver):
    def __init__(self, gateway: QwenGateway):
        self.gateway = gateway

    async def resolve(self, file_samples: Dict[str, str]) -> SchemaMapping:
        user_prompt = f"Analyze these file samples:\n{json.dumps(file_samples, indent=2)}"
        response = await self.gateway.generate_json(SCHEMA_RESOLVER_SYSTEM_PROMPT, user_prompt)
        return _mapping_from(response)


def _mapping_from(response: Any) -> SchemaMapping:
    """
    Read a schema mapping out of a model response.

    One unclassifiable table must not lose the others: the rest of the upload
    is still analysable without it, and dropping it costs that file rather than
    the run. A response with no usable table at all raises, so the caller falls
    back to the heuristic resolver.
    """
    if not isinstance(response, dict):
        raise ValueError(f"The model returned {type(response).__name__}, not a schema object.")

    entries = response.get("tables")
    entries = entries if isinstance(entries, list) else []

    tables: List[TableClassification] = []
    for entry in entries:
        try:
            tables.append(TableClassification(**entry))
        except MALFORMED as exc:
            logger.warning("Dropping an unreadable table classification: %s", exc)

    if not tables:
        raise ValueError(
            f"The model classified none of the tables ({len(entries)} entries returned)."
        )
    if len(tables) < len(entries):
        logger.warning("Classified %d of %d tables.", len(tables), len(entries))

    return SchemaMapping(primary_entity_key=_primary_key(response, tables), tables=tables)


def _primary_key(response: Dict[str, Any], tables: List[TableClassification]) -> str:
    """
    The join key for the whole upload.

    When the model fills in each table but omits the top-level key -- a common
    near-miss -- the tables themselves still carry it, so take the one they
    mostly agree on rather than failing a run that is otherwise complete.
    """
    stated = response.get("primary_entity_key")
    if isinstance(stated, str) and stated.strip():
        return stated.strip()

    votes = Counter(t.primary_entity_key for t in tables if t.primary_entity_key)
    if not votes:
        raise ValueError("The model returned no primary entity key, and no table supplied one.")

    inferred = votes.most_common(1)[0][0]
    logger.warning("No top-level primary_entity_key; using %r from the tables.", inferred)
    return inferred
