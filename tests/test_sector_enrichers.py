"""
Sector enrichment, asserted against hand-computable values.
"""
import pandas as pd
import pytest

from churn_platform.infrastructure.parsers.sector_feature_enrichers import SectorFeatureEnricher
from churn_platform.domain.models.customer_features import CustomerFeatures
from tests.conftest import ago, simple_schema


@pytest.fixture
def enricher():
    return SectorFeatureEnricher()


def run(enricher, sector, key, frames, entity_ids, tables):
    features = [CustomerFeatures(entity_id=e, features={}) for e in entity_ids]
    schema = simple_schema(key, tables)
    out = enricher.enrich(sector, features, schema, frames)
    return {f.entity_id: f.features for f in out}


# ------------------------------------------------------------------ FinTech

def test_balance_drain_uses_deposits_and_withdrawals_only(enricher):
    """
    Inflow 100, outflow 300, plus a 500 P2P that must be ignored.
    drain = 300 / (100 + 300) = 0.75 -> rapid.
    Counting the P2P as outflow would give 800/900 = 0.89 and overstate it.
    """
    ledger = pd.DataFrame({
        "tx_id": ["t1", "t2", "t3"],
        "account_id": ["a1"] * 3,
        "timestamp": [ago(3), ago(2), ago(1)],
        "amount": [100.0, 300.0, 500.0],
        "tx_type": ["DEPOSIT", "WITHDRAWAL", "P2P"],
        "status": ["SUCCESS"] * 3,
    })
    f = run(enricher, "FinTech", "account_id", {"ledger_transactions.csv": ledger}, ["a1"],
            [("ledger_transactions.csv", "TRANSACTIONAL", "timestamp", None)])["a1"]

    assert f["balance_drain_ratio"] == pytest.approx(0.75, abs=0.001)
    assert f["rapid_balance_drain"] == 1


def test_healthy_account_is_not_flagged_as_draining(enricher):
    ledger = pd.DataFrame({
        "tx_id": ["t1", "t2"],
        "account_id": ["a1", "a1"],
        "timestamp": [ago(2), ago(1)],
        "amount": [900.0, 100.0],
        "tx_type": ["DEPOSIT", "WITHDRAWAL"],
        "status": ["SUCCESS", "SUCCESS"],
    })
    f = run(enricher, "FinTech", "account_id", {"ledger_transactions.csv": ledger}, ["a1"],
            [("ledger_transactions.csv", "TRANSACTIONAL", "timestamp", None)])["a1"]

    assert f["balance_drain_ratio"] == pytest.approx(0.1, abs=0.001)
    assert f["rapid_balance_drain"] == 0


def test_p2p_failure_streak_counts_consecutive_failures_in_time_order(enricher):
    """FAIL, FAIL, SUCCESS, FAIL, FAIL, FAIL -> longest run is 3."""
    statuses = ["FAILED", "FAILED", "SUCCESS", "FAILED", "FAILED", "FAILED"]
    ledger = pd.DataFrame({
        "tx_id": [f"t{i}" for i in range(6)],
        "account_id": ["a1"] * 6,
        # Deliberately out of order in the frame; the enricher must sort by time.
        "timestamp": [ago(6 - i) for i in range(6)][::-1],
        "amount": [10.0] * 6,
        "tx_type": ["P2P"] * 6,
        "status": statuses[::-1],
    })
    f = run(enricher, "FinTech", "account_id", {"ledger_transactions.csv": ledger}, ["a1"],
            [("ledger_transactions.csv", "TRANSACTIONAL", "timestamp", None)])["a1"]
    assert f["p2p_failure_streak"] == 3


# ------------------------------------------------------------------ Telecom

def test_expanding_topup_intervals_detected(enricher):
    """Gaps of 5, 8, 20, 50 days -> late average far exceeds early -> flagged."""
    ages = [83, 78, 70, 50, 0]      # gaps: 5, 8, 20, 50
    recharge = pd.DataFrame({
        "rec_id": [f"r{i}" for i in range(len(ages))],
        "subscriber_id": ["s1"] * len(ages),
        "amount": [10] * len(ages),
        "recharge_date": [ago(a) for a in ages],
    })
    f = run(enricher, "Telecom", "subscriber_id", {"recharge_history.csv": recharge}, ["s1"],
            [("recharge_history.csv", "TRANSACTIONAL", "recharge_date", None)])["s1"]

    assert f["max_recharge_gap_days"] == pytest.approx(50.0, abs=0.1)
    assert f["expanding_topup_intervals"] == 1


def test_steady_topups_are_not_flagged(enricher):
    ages = [28, 21, 14, 7, 0]       # a uniform weekly cadence
    recharge = pd.DataFrame({
        "rec_id": [f"r{i}" for i in range(len(ages))],
        "subscriber_id": ["s1"] * len(ages),
        "amount": [10] * len(ages),
        "recharge_date": [ago(a) for a in ages],
    })
    f = run(enricher, "Telecom", "subscriber_id", {"recharge_history.csv": recharge}, ["s1"],
            [("recharge_history.csv", "TRANSACTIONAL", "recharge_date", None)])["s1"]

    assert f["avg_recharge_gap_days"] == pytest.approx(7.0, abs=0.1)
    assert f["expanding_topup_intervals"] == 0


# --------------------------------------------------------------------- SaaS

def test_export_ratio(enricher):
    """3 exports out of 10 events -> 0.3."""
    events = pd.DataFrame({
        "event_id": [f"e{i}" for i in range(10)],
        "user_id": ["u1"] * 10,
        "timestamp": [ago(1)] * 10,
        "event_type": ["export"] * 3 + ["login"] * 7,
    })
    f = run(enricher, "SaaS", "user_id", {"events_log.csv": events}, ["u1"],
            [("events_log.csv", "TIME_SERIES_EVENT", "timestamp", None)])["u1"]
    assert f["export_ratio"] == pytest.approx(0.3, abs=0.001)


# ------------------------------------------------------------------ hygiene

def test_unknown_sector_is_a_no_op(enricher):
    f = run(enricher, "Retail", "user_id", {"x.csv": pd.DataFrame({"user_id": ["u1"]})},
            ["u1"], [("x.csv", "DIMENSION", None, None)])["u1"]
    assert f == {}


def test_missing_table_does_not_raise(enricher):
    """A tenant may simply not have uploaded the ledger."""
    f = run(enricher, "FinTech", "account_id", {"accounts.csv": pd.DataFrame({"account_id": ["a1"]})},
            ["a1"], [("accounts.csv", "DIMENSION", None, None)])["a1"]
    assert f == {}
