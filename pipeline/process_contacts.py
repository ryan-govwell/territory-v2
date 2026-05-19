#!/usr/bin/env python3
"""
process_contacts.py
Cleans a Salesforce contacts export and classifies each contact by function.

Usage:
    python3 pipeline/process_contacts.py \
        --input  ~/Downloads/sf_contacts.csv \
        --state  FL \
        --output states/FL/contacts.csv

Input columns expected: Starbridge Buyer ID, First Name, Last Name, Title,
                        Account Name, Last Activity
Output columns: Account ID, Full Name, Title, Function, Last Activity
"""

import argparse
import csv
import re
from datetime import datetime
from pathlib import Path


FUNCTIONS = [
    'Building/Permitting/Inspections',
    'Planning & Zoning',
    'Code Enforcement',
    'Other',
]


def classify(title: str) -> str:
    t = title.lower().strip()

    # ── Code Enforcement ───────────────────────────────────────────────────
    # Must check before Building because "Building Code Enforcement" exists.
    # We only count it as Code Enforcement if the enforcement role is primary
    # (i.e. not overshadowed by "building code" as a phrase).
    if ('code enforcement' in t or 'code compliance' in t) and 'building code' not in t:
        return 'Code Enforcement'

    # ── Building / Permitting / Inspections ────────────────────────────────
    BUILD_KW = [
        'building', 'permit', 'inspect', 'plans examiner', 'plan review',
        'plan examiner', 'floodplain', 'construction code', 'cbo',
    ]
    if any(k in t for k in BUILD_KW):
        return 'Building/Permitting/Inspections'

    # ── Planning & Zoning ──────────────────────────────────────────────────
    PLAN_KW = [
        'planning', 'planner', 'zoning', 'growth management',
        'community development', 'development services',
        'land use', 'land development', 'neighborhood development',
        'gis ', ' gis', 'geographic information',
    ]
    if any(k in t for k in PLAN_KW):
        return 'Planning & Zoning'

    return 'Other'


def parse_date(val: str) -> str:
    val = val.strip()
    if not val:
        return ''
    for fmt in ('%m/%d/%Y', '%Y-%m-%d', '%m/%d/%y'):
        try:
            return datetime.strptime(val, fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
    return val


def main():
    parser = argparse.ArgumentParser(description='Process Salesforce contacts export.')
    parser.add_argument('--input',  required=True, help='Path to SF contacts CSV')
    parser.add_argument('--state',  required=True, help='2-letter state code (e.g. FL)')
    parser.add_argument('--output', required=True, help='Output CSV path')
    args = parser.parse_args()

    state = args.state.upper()

    rows_out = []
    skipped  = 0

    with open(args.input, newline='', encoding='latin-1') as f:
        for row in csv.DictReader(f):
            sb_id = row.get('Starbridge Buyer ID', '').strip()
            if not sb_id:
                skipped += 1
                continue

            first = row.get('First Name', '').strip()
            last  = row.get('Last Name',  '').strip()
            name  = f'{first} {last}'.strip()
            if not name:
                skipped += 1
                continue

            title    = row.get('Title', '').strip()
            function = classify(title)
            last_act = parse_date(row.get('Last Activity', ''))

            rows_out.append({
                'Account ID':    sb_id,
                'Full Name':     name,
                'Title':         title,
                'Function':      function,
                'Last Activity': last_act,
            })

    FIELDNAMES = ['Account ID', 'Full Name', 'Title', 'Function', 'Last Activity']

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows_out)

    from collections import Counter
    funcs = Counter(r['Function'] for r in rows_out)
    has_act = sum(1 for r in rows_out if r['Last Activity'])

    print(f'Contacts written:  {len(rows_out)}')
    print(f'Skipped (no ID):   {skipped}')
    print(f'With last activity:{has_act}')
    print('By function:')
    for fn in FUNCTIONS:
        print(f'  {funcs[fn]:4d}  {fn}')


if __name__ == '__main__':
    main()
