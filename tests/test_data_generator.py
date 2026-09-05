"""
The generated fixtures must be reproducible and must actually carry signal.

A fixture that is merely well-shaped is useless: if the churning cohort does not
separate from the healthy one, every feature computed downstream is noise.
"""
import hashlib
import runpy
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

import generate_mock_data as gen

DATA = Path("data")
SECTORS = {
    "saas": ("users.csv", "user_id", "usr_"),
    "telecom": ("subscribers.csv", "subscriber_id", "sub_"),
    "fintech": ("accounts.csv", "account_id", "acc_"),
}


def _digest() -> str:
    h = hashlib.sha256()
    for path in sorted(DATA.rglob("*.csv")):
        h.update(path.read_bytes())
    return h.hexdigest()


@pytest.fixture(scope="module")
def generated():
    """Generate once for the module; assert the data is present."""
    if not (DATA / "saas" / "users.csv").exists():
        runpy.run_path("generate_mock_data.py", run_name="__main__")
    return DATA


def test_two_runs_are_byte_identical(generated):
    """Seeded and frozen: regeneration must not churn the working tree."""
    before = _digest()
    subprocess.run([sys.executable, "generate_mock_data.py"], check=True, capture_output=True)
    assert _digest() == before


def test_reference_date_is_frozen():
    """A wall-clock anchor would make the fixtures drift and tests flaky."""
    assert gen.REFERENCE_DATE.year == 2025
    assert gen.REFERENCE_DATE.month == 6


def test_timestamp_columns_the_spec_omitted_are_present(generated):
    """
    §6 defined network_cdrs and card_swipes with no timestamp, which makes the
    §2B rolling features impossible. Both now carry one.
    """
    cdrs = pd.read_csv(DATA / "telecom" / "network_cdrs.csv")
    swipes = pd.read_csv(DATA / "fintech" / "card_swipes.csv")
    assert "call_timestamp" in cdrs.columns
    assert "swipe_timestamp" in swipes.columns
    assert pd.to_datetime(cdrs["call_timestamp"], format="mixed").notna().all()
    assert pd.to_datetime(swipes["swipe_timestamp"], format="mixed").notna().all()


def test_free_text_actually_varies(generated):
    """The original notes column was one identical string 30 times."""
    notes = pd.read_csv(DATA / "telecom" / "complaints.csv")["notes"]
    subjects = pd.read_csv(DATA / "saas" / "tickets.csv")["subject"]
    assert notes.nunique() > 1, "complaint notes are a single repeated string"
    assert subjects.nunique() > 5


@pytest.mark.parametrize("sector", list(SECTORS))
def test_entity_counts(generated, sector):
    dimension, key, _ = SECTORS[sector]
    df = pd.read_csv(DATA / sector / dimension)
    assert len(df) == gen.ENTITY_COUNT
    assert df[key].nunique() == gen.ENTITY_COUNT


def _cohorts(sector):
    """Entity ids are 1-based; indices 0..24 are the churning cohort."""
    _, _, prefix = SECTORS[sector]
    churning = {f"{prefix}{i}" for i in range(1, gen.CHURN_COHORT_SIZE + 1)}
    healthy = {f"{prefix}{i}" for i in range(gen.CHURN_COHORT_SIZE + 1, gen.ENTITY_COUNT + 1)}
    return churning, healthy


def test_saas_churning_cohort_has_failed_invoices(generated):
    churning, healthy = _cohorts("saas")
    inv = pd.read_csv(DATA / "saas" / "invoices.csv")
    failed = inv[inv["status"] == "FAILED"].groupby("user_id").size()

    churn_rate = sum(failed.get(u, 0) for u in churning) / len(churning)
    healthy_rate = sum(failed.get(u, 0) for u in healthy) / len(healthy)
    assert churn_rate > healthy_rate * 3, (churn_rate, healthy_rate)


def test_telecom_churning_cohort_drops_more_calls(generated):
    churning, healthy = _cohorts("telecom")
    cdrs = pd.read_csv(DATA / "telecom" / "network_cdrs.csv")
    rate = cdrs.assign(d=(cdrs["call_status"] == "DROPPED")).groupby("subscriber_id")["d"].mean()

    churn_rate = rate[rate.index.isin(churning)].mean()
    healthy_rate = rate[rate.index.isin(healthy)].mean()
    assert churn_rate > 0.12, churn_rate
    assert churn_rate > healthy_rate * 2, (churn_rate, healthy_rate)


def test_telecom_churning_cohort_has_port_out_complaints(generated):
    churning, _ = _cohorts("telecom")
    comp = pd.read_csv(DATA / "telecom" / "complaints.csv")
    churn_comp = comp[comp["subscriber_id"].isin(churning)]
    assert len(churn_comp) > 0
    port_out = (churn_comp["category"] == "MNP_PORT_OUT").mean()
    assert port_out > 0.2, port_out


def test_fintech_churning_cohort_skews_to_withdrawals_recently(generated):
    churning, healthy = _cohorts("fintech")
    tx = pd.read_csv(DATA / "fintech" / "ledger_transactions.csv")
    tx["ts"] = pd.to_datetime(tx["timestamp"], format="mixed")
    recent = tx[tx["ts"] >= tx["ts"].max() - pd.Timedelta(days=14)]

    share = recent.assign(w=(recent["tx_type"] == "WITHDRAWAL")).groupby("account_id")["w"].mean()
    churn_share = share[share.index.isin(churning)].mean()
    healthy_share = share[share.index.isin(healthy)].mean()
    assert churn_share > healthy_share, (churn_share, healthy_share)


def test_fintech_churning_cohort_has_disputes(generated):
    churning, healthy = _cohorts("fintech")
    disputes = pd.read_csv(DATA / "fintech" / "disputes.csv").groupby("account_id").size()
    churn_rate = sum(disputes.get(a, 0) for a in churning) / len(churning)
    healthy_rate = sum(disputes.get(a, 0) for a in healthy) / len(healthy)
    assert churn_rate > healthy_rate * 3, (churn_rate, healthy_rate)
