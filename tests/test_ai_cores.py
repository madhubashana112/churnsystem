"""
The Qwen path: the three sector cores and the AI schema resolver.

These were the one part of the pipeline with no coverage, because they are only
reachable with a live API key. Nothing here touches the network -- a fake
gateway returns the JSON a model would, including the malformed shapes a model
actually produces, which is the point: this path is a parser for untrusted
output, and it is the shape of that output that has to be pinned down.
"""
import asyncio
import json

import pytest

from churn_platform.domain.models.customer_features import CustomerFeatures
from churn_platform.infrastructure.ai.cores.fintech_core import FintechCore
from churn_platform.infrastructure.ai.cores.saas_core import SaasCore
from churn_platform.infrastructure.ai.cores.telecom_core import TelecomCore
from churn_platform.infrastructure.parsers.schema_resolver import AISchemaResolver


class _FakeGateway:
    """Returns a canned response and records what it was asked."""

    def __init__(self, response):
        self.response = response
        self.calls = []

    async def generate_json(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _features(n=2):
    return [CustomerFeatures(entity_id=f"e{i}", features={"days_since": i}) for i in range(n)]


def _playbook():
    return {"action_type": "DISCOUNT", "action_payload": "20% for 3 months", "channel": "EMAIL"}


def _entry(entity_id, **prediction_fields):
    block = {"churn_probability": 0.82, "risk_tier": "HIGH"}
    block.update(prediction_fields)
    return {
        "entity_id": entity_id,
        "churn_prediction": block,
        "retention_playbook": _playbook(),
    }


def _run(core, features):
    return asyncio.run(core.analyze(features))


# ------------------------------------------------------------- happy path

def test_saas_core_maps_a_well_formed_response():
    gateway = _FakeGateway({"predictions": [
        _entry("e0", primary_drivers=["Seat count fell 40%", "No admin login in 30 days"]),
        _entry("e1"),
    ]})
    results = _run(SaasCore(gateway), _features(2))

    assert len(results) == 2
    prediction, playbook = results[0]
    assert prediction.entity_id == "e0"
    assert prediction.churn_probability == 0.82
    assert prediction.risk_tier == "HIGH"
    assert prediction.primary_drivers == ["Seat count fell 40%", "No admin login in 30 days"]
    assert playbook.channel == "EMAIL"
    assert playbook.action_payload == "20% for 3 months"
    # Absent optional fields stay absent rather than becoming a default.
    assert results[1][0].primary_drivers is None


def test_telecom_core_keeps_its_sector_fields():
    gateway = _FakeGateway({"predictions": [
        _entry("e0", root_cause="Repeated dropped calls", regional_network_impact_flag=True),
    ]})
    prediction, _ = _run(TelecomCore(gateway), _features(1))[0]

    assert prediction.root_cause == "Repeated dropped calls"
    assert prediction.regional_network_impact_flag is True
    # A field belonging to another sector is not invented here.
    assert prediction.dormancy_type is None


def test_fintech_core_keeps_its_sector_fields():
    gateway = _FakeGateway({"predictions": [_entry("e0", dormancy_type="SILENT_ATTRITION")]})
    prediction, _ = _run(FintechCore(gateway), _features(1))[0]

    assert prediction.dormancy_type == "SILENT_ATTRITION"
    assert prediction.root_cause is None


@pytest.mark.parametrize("core_cls,marker", [
    (SaasCore, "SaaS"), (TelecomCore, "Telecom"), (FintechCore, "FinTech"),
])
def test_each_core_sends_its_own_sector_prompt_and_the_features(core_cls, marker):
    """A core wired to the wrong prompt would score the cohort as another industry."""
    gateway = _FakeGateway({"predictions": [_entry("e0")]})
    _run(core_cls(gateway), _features(1))

    system_prompt, user_prompt = gateway.calls[0]
    assert marker.lower() in system_prompt.lower()
    assert "e0" in user_prompt
    assert "days_since" in user_prompt
    # The features must arrive as JSON the model can read, not as a repr.
    payload = json.loads(user_prompt.split("\n", 1)[1])
    assert payload[0]["entity_id"] == "e0"


# --------------------------------------------------- malformed model output

def test_one_unreadable_entry_does_not_discard_the_rest_of_the_batch():
    """
    At a batch size of 10 and a 20-entity cap, aborting on a single bad entry
    costs half the run -- so the bad entry is dropped, not the batch.
    """
    gateway = _FakeGateway({"predictions": [
        _entry("e0"),
        {"entity_id": "e1"},                                   # no prediction block
        {"churn_prediction": {"churn_probability": 0.4}},      # no id, no tier
        _entry("e2", **{}),
    ]})
    results = _run(SaasCore(gateway), _features(3))

    assert [p.entity_id for p, _ in results] == ["e0", "e2"]


@pytest.mark.parametrize("entry", [
    None,
    "a sentence where an object was asked for",
    [],
    {"entity_id": "e0", "churn_prediction": "HIGH", "retention_playbook": {}},
    {"entity_id": "e0", "churn_prediction": {"churn_probability": "very likely",
                                             "risk_tier": "HIGH"},
     "retention_playbook": {}},
    {"entity_id": "e0", "churn_prediction": {"churn_probability": 0.9, "risk_tier": "HIGH"},
     "retention_playbook": {"action_type": "DISCOUNT"}},   # playbook missing channel
])
def test_entries_of_the_wrong_shape_are_dropped_not_raised(entry):
    gateway = _FakeGateway({"predictions": [_entry("e1"), entry]})
    results = _run(SaasCore(gateway), _features(2))

    assert [p.entity_id for p, _ in results] == ["e1"]


def test_a_prediction_for_an_entity_never_sent_is_dropped():
    """
    A hallucinated id would show on the dashboard as an account with drivers
    but no features, and would count towards entities_scored.
    """
    gateway = _FakeGateway({"predictions": [_entry("e0"), _entry("ghost-account")]})
    results = _run(SaasCore(gateway), _features(1))

    assert [p.entity_id for p, _ in results] == ["e0"]


@pytest.mark.parametrize("response", [
    {},
    {"predictions": []},
    {"predictions": "none"},
    {"results": [1, 2]},
    [],
    None,
    {"predictions": [{"nonsense": True}]},
])
def test_a_response_with_nothing_usable_raises_so_the_caller_can_fall_back(response):
    """
    Returning [] here would be reported as a completed Qwen run that scored no
    accounts. Raising sends the caller to the local engine instead.
    """
    with pytest.raises(ValueError):
        _run(SaasCore(_FakeGateway(response)), _features(2))


def test_an_empty_batch_asks_for_nothing_and_returns_nothing():
    gateway = _FakeGateway({"predictions": []})
    assert _run(SaasCore(gateway), []) == []


def test_a_gateway_failure_propagates():
    """The use case turns this into a skipped batch; it must not be swallowed here."""
    gateway = _FakeGateway(RuntimeError("401 invalid_api_key"))
    with pytest.raises(RuntimeError):
        _run(SaasCore(gateway), _features(2))


# ------------------------------------------------------------ schema resolver

def _table(name="users.csv", role="DIMENSION", key="user_id", **extra):
    table = {"file_name": name, "role": role, "primary_entity_key": key}
    table.update(extra)
    return table


def _resolve(response, samples=None):
    resolver = AISchemaResolver(_FakeGateway(response))
    return asyncio.run(resolver.resolve(samples or {"users.csv": "user_id,tier\nu1,Pro\n"}))


def test_schema_resolver_maps_a_well_formed_response():
    schema = _resolve({
        "primary_entity_key": "user_id",
        "tables": [
            _table("users.csv"),
            _table("events.csv", role="TIME_SERIES_EVENT", timestamp_column="ts",
                   noise_columns=["session_id"]),
        ],
    })

    assert schema.primary_entity_key == "user_id"
    assert [t.file_name for t in schema.tables] == ["users.csv", "events.csv"]
    assert schema.tables[1].role == "TIME_SERIES_EVENT"
    assert schema.tables[1].timestamp_column == "ts"
    assert schema.tables[1].noise_columns == ["session_id"]


def test_one_unclassifiable_table_does_not_lose_the_others():
    schema = _resolve({
        "primary_entity_key": "user_id",
        "tables": [_table("users.csv"), {"file_name": "mystery.csv", "role": "TABLE"}],
    })

    assert [t.file_name for t in schema.tables] == ["users.csv"]


def test_a_missing_top_level_key_is_taken_from_the_tables():
    """The tables already agree on the join key; failing the run would be needless."""
    schema = _resolve({"tables": [
        _table("users.csv", key="account_id"),
        _table("events.csv", role="TIME_SERIES_EVENT", key="account_id"),
    ]})

    assert schema.primary_entity_key == "account_id"


@pytest.mark.parametrize("response", [
    {},
    {"tables": []},
    {"primary_entity_key": "user_id", "tables": [{"role": "DIMENSION"}]},
    {"primary_entity_key": "user_id", "tables": "users.csv"},
    "not an object",
    None,
])
def test_an_unusable_schema_response_raises_so_the_heuristic_resolver_takes_over(response):
    with pytest.raises(ValueError):
        _resolve(response)


def test_the_resolver_sends_the_file_samples_as_json():
    gateway = _FakeGateway({"primary_entity_key": "user_id", "tables": [_table()]})
    asyncio.run(AISchemaResolver(gateway).resolve({"users.csv": "user_id,tier\nu1,Pro\n"}))

    _, user_prompt = gateway.calls[0]
    assert "users.csv" in user_prompt
    assert "user_id,tier" in user_prompt
