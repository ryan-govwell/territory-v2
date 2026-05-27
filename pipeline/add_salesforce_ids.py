#!/usr/bin/env python3
"""
add_salesforce_ids.py
Joins Salesforce Account IDs into all matching state data.csv files.

The input report must include 'Account ID' (15- or 18-char SF ID) and
'Starbridge Buyer ID' (UUID). A single export can cover multiple states —
the script auto-detects which states have matching accounts and updates
each one.

Export from Salesforce: run the standard accounts report with Account ID,
Starbridge Buyer ID, Account Name, Account Owner, Entity Type, Population,
Account Status. Drop the file wherever you like and point --input at it.

Usage (from repo root):
    python3 pipeline/add_salesforce_ids.py --input ~/Downloads/report_accounts.csv

Salesforce Lightning URL format (GovWell org):
    https://govwell.lightning.force.com/lightning/r/Account/<Account ID>/view
"""

import argparse
import csv
import sys
from pathlib import Path

SF_BASE_URL = 'https://govwell.lightning.force.com/lightning/r/Account'


def main():
    parser = argparse.ArgumentParser(description='Add Salesforce IDs to state data.csv files.')
    parser.add_argument('--input', required=True, help='Path to SF accounts report CSV (must have Account ID + Starbridge Buyer ID)')
    args = parser.parse_args()

    # Build lookup: Starbridge Buyer ID → SF Account ID
    sf_lookup = {}
    with open(args.input, newline='', encoding='latin-1') as f:
        for row in csv.DictReader(f):
            sb_id = row.get('Starbridge Buyer ID', '').strip()
            sf_id = row.get('Account ID', '').strip()
            if sb_id and sf_id:
                sf_lookup[sb_id] = sf_id

    print(f'Loaded {len(sf_lookup)} Salesforce IDs from {args.input}')

    # Find all state data.csv files
    states_dir = Path('states')
    if not states_dir.exists():
        sys.exit('Error: states/ directory not found. Run from the repo root.')

    state_files = sorted(states_dir.glob('*/data.csv'))
    if not state_files:
        sys.exit('Error: no states/*/data.csv files found.')

    for data_path in state_files:
        state = data_path.parent.name

        with open(data_path, newline='', encoding='utf-8') as f:
            reader     = csv.DictReader(f)
            fieldnames = list(reader.fieldnames)
            rows       = list(reader)

        if 'Salesforce ID' not in fieldnames:
            # Insert before Outreach ID if it exists, else append
            if 'Outreach ID' in fieldnames:
                idx = fieldnames.index('Outreach ID')
                fieldnames.insert(idx, 'Salesforce ID')
            else:
                fieldnames.append('Salesforce ID')

        matched, unmatched = 0, []
        for row in rows:
            sb_id = row.get('Account ID', '').strip()   # our 'Account ID' col is the Starbridge UUID
            sf_id = sf_lookup.get(sb_id, '')
            row['Salesforce ID'] = sf_id
            if sf_id:
                matched += 1
            else:
                unmatched.append(row.get('Account Name', sb_id))

        with open(data_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f'[{state}] Matched: {matched}/{len(rows)}', end='')
        if unmatched:
            print(f'  — {len(unmatched)} unmatched:')
            for name in unmatched:
                print(f'    {name}')
        else:
            print('  — all matched.')


if __name__ == '__main__':
    main()
