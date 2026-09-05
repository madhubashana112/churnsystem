"""
Shared fixtures.

Feature tests deliberately use hand-built frames with hand-computable expected
values rather than the generated fixtures: a test that asserts against generated
data only proves the two agree, not that either is right.
"""
from datetime import datetime, timedelta

import pandas as pd
import pytest

from churn_platform.domain.models.schema_mapping import SchemaMapping, TableClassification

# Fixed anchor for hand-built frames, so expected ages are exact.
ANCHOR = datetime(2025, 6, 1, 12, 0, 0)


def ago(days: float) -> str:
    return (ANCHOR - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def anchor() -> datetime:
    return ANCHOR


@pytest.fixture
def synthesizer():
    from churn_platform.infrastructure.parsers.feature_synthesizer import PandasFeatureSynthesizer
    return PandasFeatureSynthesizer()


def simple_schema(primary_key: str, tables) -> SchemaMapping:
    """tables: iterable of (file_name, role, timestamp_column, noise_columns)."""
    return SchemaMapping(
        primary_entity_key=primary_key,
        tables=[
            TableClassification(
                file_name=name,
                role=role,
                primary_entity_key=primary_key,
                timestamp_column=ts,
                noise_columns=list(noise or []),
            )
            for name, role, ts, noise in tables
        ],
    )


@pytest.fixture
def make_schema():
    return simple_schema


@pytest.fixture
def velocity_frames():
    """
    One entity with 10 events in the last 7 days and 20 in the prior 30-day
    window. Velocity = 10 / (20 / (30/7)) = 10 / 4.667 = 2.14.
    """
    users = pd.DataFrame({"user_id": ["u1"], "tier": ["Pro"]})
    stamps = [ago(1)] * 10 + [ago(20)] * 20
    events = pd.DataFrame({
        "event_id": [f"e{i}" for i in range(len(stamps))],
        "user_id": ["u1"] * len(stamps),
        "timestamp": stamps,
        "event_type": ["login"] * len(stamps),
    })
    return {"users.csv": users, "events.csv": events}
