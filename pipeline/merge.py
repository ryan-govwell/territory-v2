#!/usr/bin/env python3
"""
merge.py
Merges processed accounts, opportunities, and activity CSVs into a single master CSV.

Joins on Account ID (Starbridge Buyer ID).

Opportunity logic (per account):
  - If any Open opp exists → use its details as primary
  - Flag "Previously Lost" if account also has a Closed Lost alongside an open opp
  - If only Closed Lost → status = Closed Lost
  - If Closed Won → status = Closed Won
  - No opp → blank opp fields

Usage:
    python3 scripts/merge.py \
        --accounts      <FL_accounts.csv> \
        --opportunities <FL_opportunities.csv> \
        --activity      <FL_activity.csv> \
        --output        <FL_master.csv>

Example:
    python3 scripts/merge.py \
        --accounts      ~/Downloads/FL_accounts.csv \
        --opportunities ~/Downloads/FL_opportunities.csv \
        --activity      ~/Downloads/FL_activity.csv \
        --output        ~/Downloads/FL_master.csv
"""

import argparse
import csv
from collections import defaultdict


def load_opportunities(path):
    """Returns dict of Account ID → aggregated opp data."""
    raw = defaultdict(list)
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            raw[row['Account ID']].append(row)

    result = {}
    for acct_id, opps in raw.items():
        open_opps   = [o for o in opps if o['Opp Status'] == 'Open']
        won_opps    = [o for o in opps if o['Opp Status'] == 'Closed Won']
        lost_opps   = [o for o in opps if o['Opp Status'] == 'Closed Lost']

        if open_opps:
            primary = open_opps[0]
            result[acct_id] = {
                'Opp Status':          'Open',
                'Stage':               primary['Stage'],
                'Funnel Position':     primary['Funnel Position'],
                'Sourced By':          primary['Sourced By'],
                'Discovery Call Date': primary['Discovery Call Date'],
                'Created Date':        primary['Created Date'],
                'ARR':                 primary['ARR'],
                'Previously Lost':     'Yes' if lost_opps else '',
            }
        elif won_opps:
            primary = won_opps[0]
            result[acct_id] = {
                'Opp Status':          'Closed Won',
                'Stage':               '',
                'Funnel Position':     '',
                'Sourced By':          primary['Sourced By'],
                'Discovery Call Date': primary['Discovery Call Date'],
                'Created Date':        primary['Created Date'],
                'ARR':                 primary['ARR'],
                'Previously Lost':     '',
            }
        elif lost_opps:
            primary = lost_opps[0]
            result[acct_id] = {
                'Opp Status':          'Closed Lost',
                'Stage':               '',
                'Funnel Position':     '',
                'Sourced By':          primary['Sourced By'],
                'Discovery Call Date': primary['Discovery Call Date'],
                'Created Date':        primary['Created Date'],
                'ARR':                 primary['ARR'],
                'Previously Lost':     '',
            }

    return result


def load_activity(path):
    """Returns dict of Account ID → activity row."""
    result = {}
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        activity_fields = reader.fieldnames
        for row in reader:
            result[row['Account ID']] = row
    return result, activity_fields


def main():
    parser = argparse.ArgumentParser(description='Merge accounts, opportunities, and activity CSVs.')
    parser.add_argument('--accounts',      required=True)
    parser.add_argument('--opportunities', required=True)
    parser.add_argument('--activity',      required=True)
    parser.add_argument('--output',        required=True)
    args = parser.parse_args()

    opps, activity_rows, activity_fields = (
        load_opportunities(args.opportunities),
        *load_activity(args.activity),
    )

    OPP_FIELDS = [
        'Opp Status', 'Stage', 'Funnel Position',
        'Sourced By', 'Discovery Call Date', 'Created Date',
        'ARR', 'Previously Lost',
    ]

    # Activity fields to carry over (exclude Account ID + Account Name, already in accounts)
    ACT_FIELDS = [f for f in activity_fields if f not in ('Account ID', 'Account Name')]

    rows_out = []
    with open(args.accounts, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        account_fields = reader.fieldnames
        FIELDNAMES = account_fields + OPP_FIELDS + ACT_FIELDS

        for row in reader:
            acct_id = row['Account ID']

            # Merge opp data
            opp = opps.get(acct_id, {})
            for field in OPP_FIELDS:
                row[field] = opp.get(field, '')

            # Merge activity data
            act = activity_rows.get(acct_id, {})
            for field in ACT_FIELDS:
                row[field] = act.get(field, '')

            rows_out.append(row)

    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows_out)

    # Summary
    has_opp      = sum(1 for r in rows_out if r['Opp Status'])
    has_activity = sum(1 for r in rows_out if r['Total Calls'])
    re_engage    = sum(1 for r in rows_out if r['Previously Lost'] == 'Yes')
    print(f'Accounts in master: {len(rows_out)}')
    print(f'  With opp data:    {has_opp}')
    print(f'  With activity:    {has_activity}')
    print(f'  Re-engage flags:  {re_engage}')
    print(f'Output: {args.output}')


if __name__ == '__main__':
    main()
