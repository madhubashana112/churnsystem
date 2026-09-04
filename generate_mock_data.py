import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def create_dirs():
    dirs = ['data/saas', 'data/telecom', 'data/fintech']
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def generate_saas_data():
    np.random.seed(42)
    # 1. users.csv
    users = pd.DataFrame({
        'user_id': [f'usr_{i}' for i in range(1, 101)],
        'signup_date': [(datetime.now() - timedelta(days=np.random.randint(30, 365))).strftime('%Y-%m-%d') for _ in range(100)],
        'tier': np.random.choice(['Basic', 'Pro', 'Enterprise'], 100),
        'ip_address': [f'192.168.1.{np.random.randint(1, 255)}' for _ in range(100)],
        'last_user_agent': ['Mozilla/5.0'] * 100
    })
    users.to_csv('data/saas/users.csv', index=False)

    # 2. events_log.csv
    event_ids = [f'evt_{i}' for i in range(1, 1001)]
    events = pd.DataFrame({
        'event_id': event_ids,
        'user_id': np.random.choice(users['user_id'], 1000),
        'timestamp': [(datetime.now() - timedelta(days=np.random.randint(0, 60))).strftime('%Y-%m-%dT%H:%M:%SZ') for _ in range(1000)],
        'event_type': np.random.choice(['login', 'feature_a', 'feature_b', 'export', 'logout'], 1000, p=[0.4, 0.2, 0.2, 0.1, 0.1]),
        'session_hash': [f'hash_{np.random.randint(1000, 9999)}' for _ in range(1000)]
    })
    events.to_csv('data/saas/events_log.csv', index=False)

    # 3. invoices.csv
    invoices = pd.DataFrame({
        'inv_id': [f'inv_{i}' for i in range(1, 201)],
        'user_id': np.random.choice(users['user_id'], 200),
        'amount': np.random.choice([29.99, 99.99, 299.99], 200),
        'status': np.random.choice(['PAID', 'FAILED'], 200, p=[0.9, 0.1]),
        'due_date': [(datetime.now() - timedelta(days=np.random.randint(-15, 60))).strftime('%Y-%m-%d') for _ in range(200)]
    })
    invoices.to_csv('data/saas/invoices.csv', index=False)

    # 4. tickets.csv
    tickets = pd.DataFrame({
        'ticket_id': [f'tkt_{i}' for i in range(1, 51)],
        'user_id': np.random.choice(users['user_id'], 50),
        'subject': np.random.choice(['Cannot login', 'Export not working', 'Competitor is cheaper', 'Slow performance', 'Cancel subscription'], 50),
        'sentiment': np.random.choice(['Neutral', 'Negative', 'Very Negative'], 50, p=[0.5, 0.3, 0.2]),
        'status': np.random.choice(['OPEN', 'CLOSED'], 50)
    })
    tickets.to_csv('data/saas/tickets.csv', index=False)

def generate_telecom_data():
    np.random.seed(42)
    # 1. subscribers.csv
    subs = pd.DataFrame({
        'subscriber_id': [f'sub_{i}' for i in range(1, 101)],
        'plan': np.random.choice(['Prepaid', 'Postpaid'], 100),
        'region': np.random.choice(['North', 'South', 'East', 'West'], 100),
        'sim_imsi_hash': [f'imsi_{np.random.randint(10000, 99999)}' for _ in range(100)]
    })
    subs.to_csv('data/telecom/subscribers.csv', index=False)

    # 2. network_cdrs.csv
    cdrs = pd.DataFrame({
        'call_id': [f'call_{i}' for i in range(1, 1001)],
        'subscriber_id': np.random.choice(subs['subscriber_id'], 1000),
        'duration_sec': np.random.randint(10, 1200, 1000),
        'call_status': np.random.choice(['COMPLETED', 'DROPPED'], 1000, p=[0.95, 0.05]),
        'tower_id': np.random.choice(['TWR_A', 'TWR_B', 'TWR_C'], 1000)
    })
    cdrs.to_csv('data/telecom/network_cdrs.csv', index=False)

    # 3. recharge_history.csv
    rech = pd.DataFrame({
        'rec_id': [f'rec_{i}' for i in range(1, 202)],
        'subscriber_id': np.random.choice(subs[subs['plan'] == 'Prepaid']['subscriber_id'], 201, replace=True) if len(subs[subs['plan'] == 'Prepaid']) > 0 else [],
        'amount': np.random.choice([10, 20, 50, 100], 201),
        'recharge_date': [(datetime.now() - timedelta(days=np.random.randint(0, 60))).strftime('%Y-%m-%d') for _ in range(201)]
    })
    rech.to_csv('data/telecom/recharge_history.csv', index=False)

    # 4. complaints.csv
    comp = pd.DataFrame({
        'comp_id': [f'comp_{i}' for i in range(1, 31)],
        'subscriber_id': np.random.choice(subs['subscriber_id'], 30),
        'category': np.random.choice(['MNP_PORT_OUT', 'BILLING', 'NETWORK', 'GENERAL'], 30, p=[0.2, 0.3, 0.3, 0.2]),
        'notes': ['Customer issue reported'] * 30
    })
    comp.to_csv('data/telecom/complaints.csv', index=False)

def generate_fintech_data():
    np.random.seed(42)
    # 1. accounts.csv
    accs = pd.DataFrame({
        'account_id': [f'acc_{i}' for i in range(1, 101)],
        'tier': np.random.choice(['Standard', 'Premium', 'Metal'], 100),
        'created_at': [(datetime.now() - timedelta(days=np.random.randint(30, 730))).strftime('%Y-%m-%d') for _ in range(100)],
        'device_mac_hash': [f'mac_{np.random.randint(1000, 9999)}' for _ in range(100)]
    })
    accs.to_csv('data/fintech/accounts.csv', index=False)

    # 2. ledger_transactions.csv
    txns = pd.DataFrame({
        'tx_id': [f'tx_{i}' for i in range(1, 1001)],
        'account_id': np.random.choice(accs['account_id'], 1000),
        'timestamp': [(datetime.now() - timedelta(days=np.random.randint(0, 90))).strftime('%Y-%m-%dT%H:%M:%SZ') for _ in range(1000)],
        'amount': np.random.uniform(5.0, 500.0, 1000).round(2),
        'tx_type': np.random.choice(['DEPOSIT', 'WITHDRAWAL', 'P2P'], 1000, p=[0.4, 0.3, 0.3]),
        'status': np.random.choice(['SUCCESS', 'FAILED'], 1000, p=[0.92, 0.08])
    })
    txns.to_csv('data/fintech/ledger_transactions.csv', index=False)

    # 3. card_swipes.csv
    swipes = pd.DataFrame({
        'swipe_id': [f'swp_{i}' for i in range(1, 502)],
        'account_id': np.random.choice(accs['account_id'], 501),
        'merchant_category': np.random.choice(['GROCERY', 'ENTERTAINMENT', 'TRAVEL', 'DINING'], 501),
        'status': np.random.choice(['APPROVED', 'DECLINED'], 501, p=[0.95, 0.05])
    })
    swipes.to_csv('data/fintech/card_swipes.csv', index=False)

    # 4. disputes.csv
    disputes = pd.DataFrame({
        'dispute_id': [f'dsp_{i}' for i in range(1, 21)],
        'account_id': np.random.choice(accs['account_id'], 20),
        'reason': np.random.choice(['Fraudulent', 'Not Received', 'Duplicate'], 20),
        'open_date': [(datetime.now() - timedelta(days=np.random.randint(0, 30))).strftime('%Y-%m-%d') for _ in range(20)]
    })
    disputes.to_csv('data/fintech/disputes.csv', index=False)

if __name__ == '__main__':
    print("Generating mock data...")
    create_dirs()
    generate_saas_data()
    generate_telecom_data()
    generate_fintech_data()
    print("Mock data generated successfully in data/ folder.")
