"""
Generates the mock datasets under data/.

Unlike a purely random fixture, each entity is given a latent risk level first and
its behaviour is then generated conditionally. That means the tables contain a
signal worth finding: at-risk entities really do go quiet, complain more, fail
payments and drift towards competitors, so the churn engine has something to
learn from and the dashboard shows a believable spread of risk tiers.
"""
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

SECTOR_DIRS = ['data/saas', 'data/telecom', 'data/fintech']
ENTITY_COUNT = 100
SEED = 42

NOW = datetime.now()


def create_dirs():
    for d in SECTOR_DIRS:
        os.makedirs(d, exist_ok=True)


def days_ago(n):
    return NOW - timedelta(days=float(n))


def risk_profile(rng, count):
    """
    A latent 0..1 risk score per entity, skewed towards healthy accounts:
    roughly 55% healthy, 25% wobbling, 20% clearly leaving.
    """
    draw = rng.random(count)
    risk = np.where(
        draw < 0.55, rng.uniform(0.02, 0.30, count),
        np.where(draw < 0.80, rng.uniform(0.30, 0.62, count),
                 rng.uniform(0.62, 0.97, count)),
    )
    return np.round(risk, 3)


# ----------------------------------------------------------------------------- SaaS
def generate_saas_data():
    rng = np.random.default_rng(SEED)
    user_ids = [f'usr_{i}' for i in range(1, ENTITY_COUNT + 1)]
    risk = risk_profile(rng, ENTITY_COUNT)

    users = pd.DataFrame({
        'user_id': user_ids,
        # Newer accounts churn a little more readily.
        'signup_date': [days_ago(rng.integers(30, 700) * (1 - 0.4 * r)).strftime('%Y-%m-%d')
                        for r in risk],
        'seats': [max(1, int(rng.integers(1, 40) * (1 - 0.6 * r))) for r in risk],
        'tier': [rng.choice(['Basic', 'Pro', 'Enterprise'],
                            p=[0.25 + 0.4 * r, 0.45 - 0.15 * r, 0.30 - 0.25 * r] / np.sum(
                                [0.25 + 0.4 * r, 0.45 - 0.15 * r, 0.30 - 0.25 * r]))
                 for r in risk],
        'ip_address': [f'192.168.1.{rng.integers(1, 255)}' for _ in range(ENTITY_COUNT)],
        'last_user_agent': ['Mozilla/5.0'] * ENTITY_COUNT,
    })
    users.to_csv('data/saas/users.csv', index=False)

    # Events: healthy users are active recently and often; at-risk users went quiet.
    rows = []
    counter = 1
    for uid, r in zip(user_ids, risk):
        volume = int(np.clip(rng.normal(40 * (1 - r) + 3, 6), 1, 120))
        # Days since the account was last seen — the core churn tell.
        silence = int(rng.integers(0, 4) + r * rng.integers(10, 55))
        for _ in range(volume):
            age = silence + rng.exponential(12 * (1 - 0.5 * r))
            rows.append({
                'event_id': f'evt_{counter}',
                'user_id': uid,
                'timestamp': days_ago(min(age, 180)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'event_type': rng.choice(
                    ['login', 'feature_a', 'feature_b', 'export', 'logout'],
                    p=[0.40, 0.20, 0.20, 0.10, 0.10]),
                'session_hash': f'hash_{rng.integers(1000, 9999)}',
            })
            counter += 1
    pd.DataFrame(rows).to_csv('data/saas/events_log.csv', index=False)

    # Invoices: at-risk accounts fail payments far more often.
    rows = []
    counter = 1
    for uid, r in zip(user_ids, risk):
        for _ in range(int(rng.integers(2, 7))):
            rows.append({
                'inv_id': f'inv_{counter}',
                'user_id': uid,
                'amount': float(rng.choice([29.99, 99.99, 299.99], p=[0.5, 0.35, 0.15])),
                'status': 'FAILED' if rng.random() < 0.04 + 0.42 * r else 'PAID',
                'due_date': days_ago(rng.integers(0, 180)).strftime('%Y-%m-%d'),
            })
            counter += 1
    pd.DataFrame(rows).to_csv('data/saas/invoices.csv', index=False)

    # Tickets: at-risk accounts raise more, and angrier, tickets.
    angry = ['Cancel subscription', 'Competitor is cheaper', 'Requesting refund']
    routine = ['Cannot login', 'Export not working', 'Slow performance', 'How do I invite a teammate']
    rows = []
    counter = 1
    for uid, r in zip(user_ids, risk):
        for _ in range(int(rng.poisson(0.4 + 3.0 * r))):
            hot = rng.random() < r
            rows.append({
                'ticket_id': f'tkt_{counter}',
                'user_id': uid,
                'subject': rng.choice(angry if hot else routine),
                'sentiment': rng.choice(['Neutral', 'Negative', 'Very Negative'],
                                        p=[0.7 - 0.6 * r, 0.22 + 0.28 * r, 0.08 + 0.32 * r]),
                'status': rng.choice(['OPEN', 'CLOSED'], p=[0.25 + 0.5 * r, 0.75 - 0.5 * r]),
                'opened_at': days_ago(rng.integers(0, 90)).strftime('%Y-%m-%d'),
            })
            counter += 1
    pd.DataFrame(rows).to_csv('data/saas/tickets.csv', index=False)


# -------------------------------------------------------------------------- Telecom
def generate_telecom_data():
    rng = np.random.default_rng(SEED + 1)
    sub_ids = [f'sub_{i}' for i in range(1, ENTITY_COUNT + 1)]
    risk = risk_profile(rng, ENTITY_COUNT)

    subs = pd.DataFrame({
        'subscriber_id': sub_ids,
        'plan': [rng.choice(['Prepaid', 'Postpaid'], p=[0.45 + 0.3 * r, 0.55 - 0.3 * r]) for r in risk],
        'region': rng.choice(['North', 'South', 'East', 'West'], ENTITY_COUNT),
        'tenure_months': [max(1, int(rng.integers(2, 72) * (1 - 0.35 * r))) for r in risk],
        'sim_imsi_hash': [f'imsi_{rng.integers(10000, 99999)}' for _ in range(ENTITY_COUNT)],
    })
    subs.to_csv('data/telecom/subscribers.csv', index=False)

    # Call records: at-risk subscribers make fewer, shorter calls and drop more.
    rows = []
    counter = 1
    for sid, r in zip(sub_ids, risk):
        volume = int(np.clip(rng.normal(30 * (1 - r) + 3, 5), 1, 90))
        silence = int(rng.integers(0, 3) + r * rng.integers(8, 45))
        for _ in range(volume):
            rows.append({
                'call_id': f'call_{counter}',
                'subscriber_id': sid,
                'call_date': days_ago(min(silence + rng.exponential(10), 120)).strftime('%Y-%m-%d'),
                'duration_sec': int(np.clip(rng.normal(420 * (1 - 0.7 * r), 180), 5, 1800)),
                'call_status': 'DROPPED' if rng.random() < 0.03 + 0.22 * r else 'COMPLETED',
                'tower_id': rng.choice(['TWR_A', 'TWR_B', 'TWR_C']),
            })
            counter += 1
    pd.DataFrame(rows).to_csv('data/telecom/network_cdrs.csv', index=False)

    # Recharges: the clearest prepaid churn tell is recharge value and recency.
    rows = []
    counter = 1
    for sid, r in zip(sub_ids, risk):
        for _ in range(int(np.clip(rng.normal(8 * (1 - r) + 1, 2), 1, 20))):
            gap = int(rng.integers(0, 5) + r * rng.integers(15, 70))
            rows.append({
                'rec_id': f'rec_{counter}',
                'subscriber_id': sid,
                'amount': int(rng.choice([10, 20, 50, 100],
                                         p=[0.20 + 0.45 * r, 0.35, 0.30 - 0.20 * r, 0.15 - 0.10 * r]
                                         / np.sum([0.20 + 0.45 * r, 0.35, 0.30 - 0.20 * r, 0.15 - 0.10 * r]))),
                'recharge_date': days_ago(min(gap + rng.exponential(9), 150)).strftime('%Y-%m-%d'),
            })
            counter += 1
    pd.DataFrame(rows).to_csv('data/telecom/recharge_history.csv', index=False)

    # Complaints: port-out enquiries concentrate in the at-risk cohort.
    notes = {
        'MNP_PORT_OUT': 'Asked for the porting authorisation code',
        'BILLING': 'Disputes the last bill amount',
        'NETWORK': 'Repeated call drops at the home address',
        'GENERAL': 'General enquiry about the current plan',
    }
    rows = []
    counter = 1
    for sid, r in zip(sub_ids, risk):
        for _ in range(int(rng.poisson(0.15 + 2.2 * r))):
            category = rng.choice(
                ['MNP_PORT_OUT', 'BILLING', 'NETWORK', 'GENERAL'],
                p=[0.05 + 0.40 * r, 0.25, 0.30, 0.40 - 0.40 * r]
                  / np.sum([0.05 + 0.40 * r, 0.25, 0.30, 0.40 - 0.40 * r]))
            rows.append({
                'comp_id': f'comp_{counter}',
                'subscriber_id': sid,
                'category': category,
                'logged_at': days_ago(rng.integers(0, 90)).strftime('%Y-%m-%d'),
                'notes': notes[category],
            })
            counter += 1
    pd.DataFrame(rows).to_csv('data/telecom/complaints.csv', index=False)


# -------------------------------------------------------------------------- FinTech
def generate_fintech_data():
    rng = np.random.default_rng(SEED + 2)
    acc_ids = [f'acc_{i}' for i in range(1, ENTITY_COUNT + 1)]
    risk = risk_profile(rng, ENTITY_COUNT)

    accs = pd.DataFrame({
        'account_id': acc_ids,
        'tier': [rng.choice(['Standard', 'Premium', 'Metal'],
                            p=[0.40 + 0.4 * r, 0.35 - 0.15 * r, 0.25 - 0.25 * r]
                              / np.sum([0.40 + 0.4 * r, 0.35 - 0.15 * r, 0.25 - 0.25 * r]))
                 for r in risk],
        'created_at': [days_ago(rng.integers(60, 900)).strftime('%Y-%m-%d') for _ in range(ENTITY_COUNT)],
        'balance': [round(float(np.clip(rng.normal(3200 * (1 - 0.8 * r), 900), 5, 20000)), 2) for r in risk],
        'device_mac_hash': [f'mac_{rng.integers(1000, 9999)}' for _ in range(ENTITY_COUNT)],
    })
    accs.to_csv('data/fintech/accounts.csv', index=False)

    # Ledger: at-risk accounts go dormant and drain the balance out.
    rows = []
    counter = 1
    for aid, r in zip(acc_ids, risk):
        volume = int(np.clip(rng.normal(28 * (1 - r) + 2, 5), 1, 80))
        dormancy = int(rng.integers(0, 4) + r * rng.integers(12, 60))
        for _ in range(volume):
            rows.append({
                'tx_id': f'tx_{counter}',
                'account_id': aid,
                'timestamp': days_ago(min(dormancy + rng.exponential(11), 180)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'amount': round(float(rng.uniform(5, 500)), 2),
                'tx_type': rng.choice(['DEPOSIT', 'WITHDRAWAL', 'P2P'],
                                      p=[0.45 - 0.35 * r, 0.25 + 0.35 * r, 0.30]),
                'status': 'FAILED' if rng.random() < 0.03 + 0.20 * r else 'SUCCESS',
            })
            counter += 1
    pd.DataFrame(rows).to_csv('data/fintech/ledger_transactions.csv', index=False)

    # Card swipes: usage falls away and declines rise.
    rows = []
    counter = 1
    for aid, r in zip(acc_ids, risk):
        for _ in range(int(np.clip(rng.normal(14 * (1 - r) + 1, 4), 0, 45))):
            rows.append({
                'swipe_id': f'swp_{counter}',
                'account_id': aid,
                'swipe_date': days_ago(rng.integers(0, 120)).strftime('%Y-%m-%d'),
                'merchant_category': rng.choice(['GROCERY', 'ENTERTAINMENT', 'TRAVEL', 'DINING']),
                'status': 'DECLINED' if rng.random() < 0.02 + 0.25 * r else 'APPROVED',
            })
            counter += 1
    pd.DataFrame(rows).to_csv('data/fintech/card_swipes.csv', index=False)

    # Disputes: rare, and heavily weighted to unhappy accounts.
    rows = []
    counter = 1
    for aid, r in zip(acc_ids, risk):
        for _ in range(int(rng.poisson(0.05 + 1.4 * r))):
            rows.append({
                'dispute_id': f'dsp_{counter}',
                'account_id': aid,
                'reason': rng.choice(['Fraudulent', 'Not Received', 'Duplicate'], p=[0.4, 0.35, 0.25]),
                'open_date': days_ago(rng.integers(0, 90)).strftime('%Y-%m-%d'),
                'status': rng.choice(['OPEN', 'RESOLVED'], p=[0.3 + 0.5 * r, 0.7 - 0.5 * r]),
            })
            counter += 1
    pd.DataFrame(rows).to_csv('data/fintech/disputes.csv', index=False)


if __name__ == '__main__':
    print('Generating mock data...')
    create_dirs()
    generate_saas_data()
    generate_telecom_data()
    generate_fintech_data()
    for directory in SECTOR_DIRS:
        for name in sorted(os.listdir(directory)):
            df = pd.read_csv(os.path.join(directory, name))
            print(f'  {directory}/{name:<26} {df.shape[0]:>5} rows x {df.shape[1]} cols')
    print('Mock data generated successfully in the data/ folder.')
