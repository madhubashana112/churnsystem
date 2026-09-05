"""
Feature synthesis, asserted against hand-computable values.
"""
import pandas as pd
import pytest

from tests.conftest import ago


def features_for(synthesizer, schema, frames, entity_id):
    result = synthesizer.synthesize(schema, frames)
    by_id = {f.entity_id: f.features for f in result}
    assert entity_id in by_id, f"{entity_id} missing from {list(by_id)}"
    return by_id[entity_id]


# ------------------------------------------------------------------ velocity

def test_velocity_compares_recent_week_to_prior_month(synthesizer, make_schema, velocity_frames):
    """10 events in 7d against 20 in the prior month -> 10 / (20/4.286) = 2.14."""
    schema = make_schema("user_id", [
        ("users.csv", "DIMENSION", None, None),
        ("events.csv", "TIME_SERIES_EVENT", "timestamp", None),
    ])
    f = features_for(synthesizer, schema, velocity_frames, "u1")

    assert f["events_events_7d"] == 10
    assert f["events_events_30d"] == 30      # 10 recent + 20 at day 20
    assert f["events_activity_velocity"] == pytest.approx(2.14, abs=0.01)


def test_velocity_epsilon_prevents_divide_by_zero(synthesizer, make_schema):
    """No prior-window activity -> baseline floors at 0.5 -> 10 / 0.5 = 20."""
    users = pd.DataFrame({"user_id": ["u1"], "tier": ["Pro"]})
    events = pd.DataFrame({
        "event_id": [f"e{i}" for i in range(10)],
        "user_id": ["u1"] * 10,
        "timestamp": [ago(1)] * 10,
        "event_type": ["login"] * 10,
    })
    schema = make_schema("user_id", [
        ("users.csv", "DIMENSION", None, None),
        ("events.csv", "TIME_SERIES_EVENT", "timestamp", None),
    ])
    f = features_for(synthesizer, schema, {"users.csv": users, "events.csv": events}, "u1")

    assert f["events_events_7d"] == 10
    assert f["events_activity_velocity"] == pytest.approx(20.0, abs=0.01)


def test_fully_dormant_entity_has_zero_velocity(synthesizer, make_schema):
    """
    All of u1's activity predates both windows -> velocity 0, recency large.

    u2 is present only to set the anchor: recency is measured from the newest
    row in the data, so without an active peer u1 would trivially be "newest".
    """
    users = pd.DataFrame({"user_id": ["u1", "u2"], "tier": ["Pro", "Basic"]})
    events = pd.DataFrame({
        "event_id": ["e1", "e2", "e3"],
        "user_id": ["u1", "u1", "u2"],
        "timestamp": [ago(90), ago(120), ago(0)],
        "event_type": ["login", "login", "login"],
    })
    schema = make_schema("user_id", [
        ("users.csv", "DIMENSION", None, None),
        ("events.csv", "TIME_SERIES_EVENT", "timestamp", None),
    ])
    f = features_for(synthesizer, schema, {"users.csv": users, "events.csv": events}, "u1")

    assert f["events_events_7d"] == 0
    assert f["events_activity_velocity"] == 0.0
    assert f["events_recency_days"] == pytest.approx(90.0, abs=0.1)


# ------------------------------------------------------- reference timestamp

def test_recency_anchors_to_data_not_wall_clock(synthesizer, make_schema):
    """
    The newest row is the anchor, so its recency is 0 no matter when the test
    runs. A wall-clock anchor would drift every day.
    """
    users = pd.DataFrame({"user_id": ["u1"], "tier": ["Pro"]})
    events = pd.DataFrame({
        "event_id": ["e1", "e2"],
        "user_id": ["u1", "u1"],
        "timestamp": [ago(0), ago(10)],
        "event_type": ["login", "login"],
    })
    schema = make_schema("user_id", [
        ("users.csv", "DIMENSION", None, None),
        ("events.csv", "TIME_SERIES_EVENT", "timestamp", None),
    ])
    f = features_for(synthesizer, schema, {"users.csv": users, "events.csv": events}, "u1")
    assert f["events_recency_days"] == pytest.approx(0.0, abs=0.1)


# -------------------------------------------------------------- failure rate

def test_failure_rate_is_share_of_failed_rows(synthesizer, make_schema):
    """3 FAILED out of 10 invoices -> 0.3."""
    users = pd.DataFrame({"user_id": ["u1"], "tier": ["Pro"]})
    invoices = pd.DataFrame({
        "inv_id": [f"i{i}" for i in range(10)],
        "user_id": ["u1"] * 10,
        "amount": [10.0] * 10,
        "status": ["FAILED"] * 3 + ["PAID"] * 7,
    })
    schema = make_schema("user_id", [
        ("users.csv", "DIMENSION", None, None),
        ("invoices.csv", "TRANSACTIONAL", None, None),
    ])
    f = features_for(synthesizer, schema, {"users.csv": users, "invoices.csv": invoices}, "u1")
    assert f["invoices_failure_rate"] == pytest.approx(0.3, abs=0.001)


# ---------------------------------------------------------------- text score

def test_text_churn_score_reads_keywords(synthesizer, make_schema):
    """
    Two tickets: "cancel" (3.0) and a routine one (0.0) -> mean 1.5.

    The feature is namespaced by table, so two text-bearing tables cannot
    collide into pandas _x / _y suffixes.
    """
    users = pd.DataFrame({"user_id": ["u1"], "tier": ["Pro"]})
    tickets = pd.DataFrame({
        "ticket_id": ["t1", "t2"],
        "user_id": ["u1", "u1"],
        "subject": ["Please cancel my plan", "How do I invite a teammate"],
    })
    schema = make_schema("user_id", [
        ("users.csv", "DIMENSION", None, None),
        ("tickets.csv", "UNSTRUCTURED_TEXT", None, None),
    ])
    f = features_for(synthesizer, schema, {"users.csv": users, "tickets.csv": tickets}, "u1")
    assert f["tickets_text_churn_score"] == pytest.approx(1.5, abs=0.01)
    assert f["tickets_has_negative_text"] == 0


def test_has_negative_text_trips_at_threshold(synthesizer, make_schema):
    """Both tickets carry exit intent, so the mean clears the 2.0 threshold."""
    users = pd.DataFrame({"user_id": ["u1"], "tier": ["Pro"]})
    tickets = pd.DataFrame({
        "ticket_id": ["t1", "t2"],
        "user_id": ["u1", "u1"],
        "subject": ["cancel my subscription", "competitor is cheaper, switching"],
    })
    schema = make_schema("user_id", [
        ("users.csv", "DIMENSION", None, None),
        ("tickets.csv", "UNSTRUCTURED_TEXT", None, None),
    ])
    f = features_for(synthesizer, schema, {"users.csv": users, "tickets.csv": tickets}, "u1")
    assert f["tickets_text_churn_score"] >= 2.0
    assert f["tickets_has_negative_text"] == 1


# -------------------------------------------------------------------- hygiene

def test_noise_columns_are_excluded(synthesizer, make_schema):
    users = pd.DataFrame({
        "user_id": ["u1"],
        "tier": ["Pro"],
        "ip_address": ["10.0.0.1"],
        "session_hash": ["abc"],
    })
    schema = make_schema("user_id", [
        ("users.csv", "DIMENSION", None, ["ip_address", "session_hash"]),
    ])
    f = features_for(synthesizer, schema, {"users.csv": users}, "u1")
    assert "ip_address" not in f
    assert "session_hash" not in f
    assert f["tier"] == "Pro"


def test_caller_dataframes_are_not_mutated(synthesizer, make_schema):
    """The API layer reports row counts from these frames after synthesis."""
    users = pd.DataFrame({"user_id": ["u1"], "tier": ["Pro"], "ip_address": ["10.0.0.1"]})
    frames = {"users.csv": users}
    before_keys = set(frames)
    before_cols = list(frames["users.csv"].columns)

    schema = make_schema("user_id", [("users.csv", "DIMENSION", None, ["ip_address"])])
    synthesizer.synthesize(schema, frames)

    assert set(frames) == before_keys
    assert list(frames["users.csv"].columns) == before_cols, "noise column was dropped in place"


def test_missing_data_is_not_reported_as_zero_recency(synthesizer, make_schema):
    """
    u2 has no events at all. Its count fills to 0, but recency must not fill to
    0 — that would claim the silent user was seen as recently as anyone else.
    u3 sets the anchor so u1's 3-day-old event really is 3 days old.
    """
    users = pd.DataFrame({"user_id": ["u1", "u2", "u3"], "tier": ["Pro", "Basic", "Pro"]})
    events = pd.DataFrame({
        "event_id": ["e1", "e2"],
        "user_id": ["u1", "u3"],
        "timestamp": [ago(3), ago(0)],
        "event_type": ["login", "login"],
    })
    schema = make_schema("user_id", [
        ("users.csv", "DIMENSION", None, None),
        ("events.csv", "TIME_SERIES_EVENT", "timestamp", None),
    ])
    result = {f.entity_id: f.features for f in synthesizer.synthesize(schema, {
        "users.csv": users, "events.csv": events})}

    assert result["u2"]["events_count"] == 0
    assert result["u2"].get("events_recency_days") in (None, 0) or pd.isna(result["u2"]["events_recency_days"])
    assert result["u1"]["events_recency_days"] == pytest.approx(3.0, abs=0.1)


def test_unknown_table_in_schema_is_skipped(synthesizer, make_schema):
    """A resolver naming a file that was never uploaded must not raise."""
    users = pd.DataFrame({"user_id": ["u1"], "tier": ["Pro"]})
    schema = make_schema("user_id", [
        ("users.csv", "DIMENSION", None, None),
        ("never_uploaded.csv", "TRANSACTIONAL", None, None),
    ])
    result = synthesizer.synthesize(schema, {"users.csv": users})
    assert [f.entity_id for f in result] == ["u1"]


def test_empty_input_returns_empty(synthesizer, make_schema):
    schema = make_schema("user_id", [])
    assert synthesizer.synthesize(schema, {}) == []


def test_two_text_tables_do_not_collide(synthesizer, make_schema):
    """
    Both tickets and complaints carry prose. Without namespacing pandas would
    silently suffix the second one _y and the feature would be unreadable.
    """
    users = pd.DataFrame({"user_id": ["u1"], "tier": ["Pro"]})
    tickets = pd.DataFrame({
        "ticket_id": ["t1"], "user_id": ["u1"], "subject": ["cancel my plan"]})
    complaints = pd.DataFrame({
        "comp_id": ["c1"], "user_id": ["u1"], "notes": ["general enquiry about the plan"]})

    schema = make_schema("user_id", [
        ("users.csv", "DIMENSION", None, None),
        ("tickets.csv", "UNSTRUCTURED_TEXT", None, None),
        ("complaints.csv", "UNSTRUCTURED_TEXT", None, None),
    ])
    f = features_for(synthesizer, schema, {
        "users.csv": users, "tickets.csv": tickets, "complaints.csv": complaints}, "u1")

    assert f["tickets_text_churn_score"] == pytest.approx(3.0, abs=0.01)
    assert f["complaints_text_churn_score"] == pytest.approx(0.0, abs=0.01)
    assert not any(k.endswith("_x") or k.endswith("_y") for k in f), sorted(f)
