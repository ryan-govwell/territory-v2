#!/usr/bin/env python3
"""
process_opportunities.py
Processes a Salesforce opportunities report into a clean opportunities CSV.

All opportunities are included regardless of who created or owns them.
No filtering by BDM team — that filter applies only to activity data.

Usage:
    python3 process_opportunities.py \
        --input  <path to SF opportunities report CSV> \
        --output <output CSV path>

Example:
    python3 scripts/process_opportunities.py \
        --input  ~/Downloads/report_opps_FL.csv \
        --output ~/Downloads/FL_opportunities.csv
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import ARR_PLACEHOLDER, TOP_OF_FUNNEL_STAGES


def parse_arr(val):
    try:
        f = float(val)
        return '' if f == ARR_PLACEHOLDER else f'${f:,.0f}'
    except (ValueError, TypeError):
        return ''


def funnel_position(status, stage):
    if status != 'Open':
        return ''
    return 'Top of Funnel' if stage in TOP_OF_FUNNEL_STAGES else 'Mid Funnel'


def opp_status(row):
    if row['Closed Won Stage Date'].strip():
        return 'Closed Won'
    if row['Closed Lost Stage Date'].strip():
        return 'Closed Lost'
    return 'Open'


def main():
    parser = argparse.ArgumentParser(description='Process Salesforce opportunities report.')
    parser.add_argument('--input',  required=True, help='Path to SF opportunities report CSV')
    parser.add_argument('--output', required=True, help='Output CSV path')
    args = parser.parse_args()

    FIELDNAMES = [
        'Account ID', 'Account Name',
        'Opp Status', 'Stage', 'Funnel Position',
        'Sourced By', 'Discovery Call Date', 'Created Date',
        'ARR',
    ]

    rows_out = []
    with open(args.input, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            status = opp_status(row)
            stage  = row['Stage'].strip() if status == 'Open' else ''
            rows_out.append({
                'Account ID':          row['Account ID'].strip(),
                'Account Name':        row['Account Name'].strip(),
                'Opp Status':          status,
                'Stage':               stage,
                'Funnel Position':     funnel_position(status, stage),
                'Sourced By':          row['Discovery Call Booked By'].strip(),
                'Discovery Call Date': row['Discovery Call Date'].strip(),
                'Created Date':        row['Created Date'].strip(),
                'ARR':                 parse_arr(row['Annual Recurring Revenue (ARR)']),
            })

    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows_out)

    from collections import Counter
    statuses  = Counter(r['Opp Status'] for r in rows_out)
    real_arr  = sum(1 for r in rows_out if r['ARR'])
    print(f'Opportunities written: {len(rows_out)}')
    for s, c in statuses.most_common():
        print(f'  {s}: {c}')
    print(f'Real ARR values: {real_arr}')


if __name__ == '__main__':
    main()
