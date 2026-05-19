#!/usr/bin/env python3
"""
run_all.py
Processes combined multi-state Salesforce exports into per-state data.csv files.

The accounts report must include a 'Billing State/Province' column with full state names.
All 4 reports are combined exports covering all states; this script splits them by state
and runs the existing per-state pipeline for each one.

Usage:
    python3 pipeline/run_all.py \
        --accounts  ~/Downloads/sf_accounts_all.csv \
        --opps      ~/Downloads/sf_opps_all.csv \
        --activity  ~/Downloads/sf_activity_all.csv \
        --contacts  ~/Downloads/sf_contacts_all.csv

Optional — process only specific states:
    python3 pipeline/run_all.py ... --states FL,KS,IA
"""

import argparse
import csv
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

STATE_CODES = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
    'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
    'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
    'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
    'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
    'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
    'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
    'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
    'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
    'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
    'Wisconsin': 'WI', 'Wyoming': 'WY',
}


def read_csv(path):
    with open(path, newline='', encoding='latin-1') as f:
        return list(csv.DictReader(f))


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description='Run full pipeline for all states from combined SF exports.')
    parser.add_argument('--accounts', required=True, help='Combined SF accounts CSV')
    parser.add_argument('--opps',     required=True, help='Combined SF opportunities CSV')
    parser.add_argument('--activity', required=True, help='Combined SF activity CSV')
    parser.add_argument('--contacts', required=True, help='Combined SF contacts CSV')
    parser.add_argument('--states',   default='', help='Comma-separated state codes to process (default: all)')
    args = parser.parse_args()

    only = {s.strip().upper() for s in args.states.split(',') if s.strip()} if args.states else set()

    # ── 1. Split accounts by state ────────────────────────────────────────────
    print('Reading accounts...')
    acct_rows = read_csv(args.accounts)
    acct_fieldnames = list(csv.DictReader(
        open(args.accounts, encoding='latin-1')
    ).fieldnames)

    by_state  = defaultdict(list)   # code → [account rows]
    id_to_code = {}                  # Account ID → state code

    for row in acct_rows:
        state_name = row.get('Billing State/Province', '').strip()
        code = STATE_CODES.get(state_name)
        if not code:
            continue
        if only and code not in only:
            continue
        by_state[code].append(row)
        acct_id = row.get('Account ID', '').strip()
        if acct_id:
            id_to_code[acct_id] = code

    states_to_run = sorted(by_state.keys())
    print(f'States found: {len(states_to_run)} ({", ".join(states_to_run)})')

    # ── 2. Split opps, activity, contacts by Account ID ───────────────────────
    print('Reading opportunities...')
    opp_rows  = read_csv(args.opps)
    opp_fn    = list(csv.DictReader(open(args.opps, encoding='latin-1')).fieldnames)
    opps_by_state = defaultdict(list)
    for row in opp_rows:
        code = id_to_code.get(row.get('Account ID', '').strip())
        if code:
            opps_by_state[code].append(row)

    print('Reading activity...')
    act_rows  = read_csv(args.activity)
    act_fn    = list(csv.DictReader(open(args.activity, encoding='latin-1')).fieldnames)
    act_by_state = defaultdict(list)
    for row in act_rows:
        code = id_to_code.get(row.get('Account ID', '').strip())
        if code:
            act_by_state[code].append(row)

    print('Reading contacts...')
    con_rows  = read_csv(args.contacts)
    con_fn    = list(csv.DictReader(open(args.contacts, encoding='latin-1')).fieldnames)
    con_by_state = defaultdict(list)
    for row in con_rows:
        code = id_to_code.get(row.get('Account ID', '').strip())
        if code:
            con_by_state[code].append(row)

    # ── 3. Write per-state raw files and run pipeline ─────────────────────────
    geo = 'pipeline/geo/geo_lookup.json'
    ok, failed = [], []

    for code in states_to_run:
        state_name = next(k for k, v in STATE_CODES.items() if v == code)
        raw = Path(f'states/{code}/raw')
        print(f'\n▶ {state_name} ({code}) — {len(by_state[code])} accounts')

        write_csv(raw / 'sf_accounts.csv',     acct_fieldnames,       by_state[code])
        write_csv(raw / 'sf_opportunities.csv', opp_fn,               opps_by_state[code])
        write_csv(raw / 'sf_activity.csv',      act_fn,               act_by_state[code])
        write_csv(raw / 'sf_contacts.csv',      con_fn,               con_by_state[code])

        result = subprocess.run(
            ['bash', 'pipeline/run.sh', code, state_name],
            capture_output=False,
        )
        if result.returncode != 0:
            print(f'  ERROR running pipeline for {code}')
            failed.append(code)
            continue

        result2 = subprocess.run(
            ['python3', 'pipeline/process_contacts.py',
             '--input',  str(raw / 'sf_contacts.csv'),
             '--state',  code,
             '--output', f'states/{code}/contacts.csv'],
            capture_output=False,
        )
        if result2.returncode != 0:
            print(f'  WARNING: contacts failed for {code}')

        ok.append(code)

    # ── 4. Rebuild landing summary ────────────────────────────────────────────
    subprocess.run(['python3', 'pipeline/build_summary.py'], capture_output=False)

    # ── 5. Done ───────────────────────────────────────────────────────────────
    print(f'\n{"─"*50}')
    print(f'Done.  Success: {len(ok)}   Failed: {len(failed)}')
    if failed:
        print(f'Failed states: {", ".join(failed)}')
    print(f'\nNext: run add_outreach_ids.py per state to attach Outreach links.')


if __name__ == '__main__':
    main()
