#!/usr/bin/env python3
"""
process_activity.py
Processes a Salesforce activity report into a clean per-account activity CSV.

Filters to BDM team calls only. Salesforce has no native way to separate BD vs. AE
activity, so non-BDM names are excluded here. This filter is intentional and specific
to activity — it does NOT apply to accounts or opportunities.

Aggregates raw call rows into one row per account with:
  - Total Calls (BD only)
  - Last Call Date (BD only)
  - Per-rep call volume columns (Calls - [Rep Name])

Usage:
    python3 process_activity.py \
        --input  <path to SF activity report CSV> \
        --output <output CSV path>

Example:
    python3 scripts/process_activity.py \
        --input  ~/Downloads/report_activity_FL.csv \
        --output ~/Downloads/FL_activity.csv
"""

import argparse
import csv
import sys
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import BDM_TEAM

DATE_FORMATS = ['%m/%d/%Y', '%Y-%m-%d', '%m/%d/%y']


def parse_date(val):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(val.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def main():
    parser = argparse.ArgumentParser(description='Process Salesforce activity report.')
    parser.add_argument('--input',  required=True, help='Path to SF activity report CSV')
    parser.add_argument('--output', required=True, help='Output CSV path')
    args = parser.parse_args()

    with open(args.input, newline='', encoding='utf-8') as f:
        all_rows = list(csv.DictReader(f))

    # Support two export formats: FL/KS use 'Created By'+'Activity Date', AL uses 'Assigned'+'Date'
    sample = all_rows[0] if all_rows else {}
    col_rep  = 'Created By'    if 'Created By'    in sample else 'Assigned'
    col_date = 'Activity Date' if 'Activity Date' in sample else 'Date'

    skipped  = [r for r in all_rows if r[col_rep].strip() not in BDM_TEAM]
    raw_rows = [r for r in all_rows if r[col_rep].strip() in BDM_TEAM]
    if skipped:
        non_bd = Counter(r[col_rep] for r in skipped)
        print(f'Excluded {len(skipped)} non-BD rows from: {dict(non_bd)}')

    # Determine rep order by total volume
    all_reps = [rep for rep, _ in Counter(r[col_rep] for r in raw_rows).most_common()]

    # Aggregate per account
    accounts = defaultdict(lambda: {
        'Account ID':   '',
        'Account Name': '',
        'dates':        [],
        'rep_counts':   Counter(),
    })

    for row in raw_rows:
        key  = row['Starbridge Buyer ID'].strip()
        acct = accounts[key]
        acct['Account ID']   = key
        acct['Account Name'] = row['Account Name'].strip()
        d = parse_date(row.get(col_date, ''))
        if d:
            acct['dates'].append(d)
        acct['rep_counts'][row[col_rep].strip()] += 1

    # Build output
    rows_out = []
    for acct in accounts.values():
        row = {
            'Account ID':    acct['Account ID'],
            'Account Name':  acct['Account Name'],
            'Total Calls':   sum(acct['rep_counts'].values()),
            'Last Call Date': max(acct['dates']).strftime('%Y-%m-%d') if acct['dates'] else '',
        }
        for rep in all_reps:
            row[f'Calls - {rep}'] = acct['rep_counts'].get(rep, '') or ''
        rows_out.append(row)

    rows_out.sort(key=lambda r: -r['Total Calls'])

    FIELDNAMES = (
        ['Account ID', 'Account Name', 'Total Calls', 'Last Call Date'] +
        [f'Calls - {r}' for r in all_reps]
    )

    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows_out)

    print(f'Accounts with activity: {len(rows_out)}')
    print(f'Total call rows processed: {len(raw_rows)}')
    print(f'Reps tracked ({len(all_reps)}): {", ".join(all_reps)}')


if __name__ == '__main__':
    main()
