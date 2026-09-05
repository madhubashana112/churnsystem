"""
File ingestion, batching, sector normalisation and role validation.
"""
import asyncio
import io

import pandas as pd
import pytest
from pydantic import ValidationError

from churn_platform.application.use_cases.execute_sector_analysis import ExecuteSectorAnalysisUseCase
from churn_platform.domain.models.churn_prediction import ChurnPrediction
from churn_platform.domain.models.customer_features import CustomerFeatures
from churn_platform.domain.models.retention_playbook import RetentionPlaybook
from churn_platform.domain.models.schema_mapping import TableClassification
from churn_platform.infrastructure.parsers.file_ingestion import (
    SHEET_SEPARATOR,
    UnreadableFile,
    read_upload,
    read_uploads,
)
from churn_platform.presentation.api.dependencies import normalise_sector


# ---------------------------------------------------------------- ingestion

def _workbook(sheets: dict) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
    return buffer.getvalue()


def test_csv_upload_keeps_its_filename():
    tables = read_upload("users.csv", b"user_id,tier\nu1,Pro\n")
    assert list(tables) == ["users.csv"]
    assert tables["users.csv"].shape == (1, 2)


def test_every_excel_sheet_becomes_its_own_table():
    """Reading only the first sheet would silently discard the rest."""
    blob = _workbook({
        "users": pd.DataFrame({"user_id": ["u1"], "tier": ["Pro"]}),
        "invoices": pd.DataFrame({"inv_id": ["i1"], "user_id": ["u1"], "amount": [10.0]}),
    })
    tables = read_upload("book.xlsx", blob)

    assert set(tables) == {f"book.xlsx{SHEET_SEPARATOR}users", f"book.xlsx{SHEET_SEPARATOR}invoices"}
    assert tables[f"book.xlsx{SHEET_SEPARATOR}invoices"].shape == (1, 3)


def test_empty_sheets_are_skipped_but_the_workbook_still_loads():
    blob = _workbook({
        "data": pd.DataFrame({"user_id": ["u1"]}),
        "blank": pd.DataFrame(),
    })
    tables = read_upload("book.xlsx", blob)
    assert list(tables) == [f"book.xlsx{SHEET_SEPARATOR}data"]


@pytest.mark.parametrize("blob", [b"", b"\x00\x01\x02\x03", bytes(range(256))])
def test_unusable_bytes_raise_rather_than_yielding_an_empty_table(blob):
    with pytest.raises(UnreadableFile):
        read_upload("junk.csv", blob)


def test_one_bad_file_does_not_lose_the_others():
    tables, unreadable = read_uploads([
        ("users.csv", b"user_id,tier\nu1,Pro\n"),
        ("junk.bin", b""),
    ])
    assert list(tables) == ["users.csv"]
    assert unreadable == ["junk.bin"]


# ----------------------------------------------------------------- batching

class _RecordingCore:
    """Records the batch sizes it was asked to score."""

    def __init__(self, fail_on=()):
        self.batches = []
        self.fail_on = set(fail_on)

    async def analyze(self, features):
        index = len(self.batches)
        self.batches.append(len(features))
        if index in self.fail_on:
            raise RuntimeError("provider blew up")
        return [
            (
                ChurnPrediction(entity_id=f.entity_id, churn_probability=0.5, risk_tier="MEDIUM"),
                RetentionPlaybook(action_type="X", action_payload="y", channel="EMAIL"),
            )
            for f in features
        ]


def _features(n):
    return [CustomerFeatures(entity_id=f"e{i}", features={"a": i}) for i in range(n)]


def test_cohort_is_chunked_to_batch_size():
    core = _RecordingCore()
    results = asyncio.run(ExecuteSectorAnalysisUseCase(batch_size=10).execute(core, _features(25)))
    assert core.batches == [10, 10, 5]
    assert len(results) == 25


def test_small_cohort_is_a_single_call():
    core = _RecordingCore()
    asyncio.run(ExecuteSectorAnalysisUseCase(batch_size=10).execute(core, _features(4)))
    assert core.batches == [4]


def test_one_failing_batch_does_not_lose_the_run():
    """A provider hiccup on batch 2 must still return batches 1 and 3."""
    core = _RecordingCore(fail_on=[1])
    results = asyncio.run(ExecuteSectorAnalysisUseCase(batch_size=10).execute(core, _features(25)))
    assert core.batches == [10, 10, 5]
    assert len(results) == 15


def test_all_batches_failing_raises():
    core = _RecordingCore(fail_on=[0, 1, 2])
    with pytest.raises(RuntimeError):
        asyncio.run(ExecuteSectorAnalysisUseCase(batch_size=10).execute(core, _features(25)))


def test_empty_cohort_is_a_no_op():
    core = _RecordingCore()
    assert asyncio.run(ExecuteSectorAnalysisUseCase(batch_size=10).execute(core, [])) == []
    assert core.batches == []


# ------------------------------------------------------- sector + role input

@pytest.mark.parametrize("given,expected", [
    ("SaaS", "SaaS"), ("saas", "SaaS"), (" SAAS ", "SaaS"),
    ("telecom", "Telecom"), ("FINTECH", "FinTech"),
])
def test_sector_lookup_tolerates_casing(given, expected):
    assert normalise_sector(given) == expected


@pytest.mark.parametrize("given", ["Retail", "", None, "saa"])
def test_unknown_sector_returns_none(given):
    assert normalise_sector(given) is None


def test_role_typo_is_rejected_not_silently_accepted():
    with pytest.raises(ValidationError):
        TableClassification(file_name="x.csv", role="TABLE", primary_entity_key="id")


def test_recoverable_role_near_misses_are_normalised():
    """A model writing "dimensions" should not fail the whole run."""
    assert TableClassification(
        file_name="x.csv", role="dimensions", primary_entity_key="id").role == "DIMENSION"
    assert TableClassification(
        file_name="x.csv", role=" time-series-event ", primary_entity_key="id").role == "TIME_SERIES_EVENT"
