#!/usr/bin/env python3
"""
add_outreach_ids.py
Joins Outreach account IDs into a state's data.csv.

Export from Outreach: Accounts → Export → select Id and Name columns only.
Run from the repo root after each Outreach export.

Usage:
    python3 pipeline/add_outreach_ids.py --state FL --outreach ~/Downloads/Accounts_2026-05-18_394.csv
    python3 pipeline/add_outreach_ids.py --state KS --outreach ~/Downloads/Accounts_2026-05-19_347.csv
"""

import argparse
import csv
import sys
from pathlib import Path


def normalize(name: str, state_code: str) -> str:
    suffix = f', {state_code.upper()}'
    return name.strip().lower().removesuffix(suffix.lower()).strip()


def main():
    parser = argparse.ArgumentParser(description='Add Outreach IDs to a state data.csv.')
    parser.add_argument('--state',    required=True, help='2-letter state code (e.g. FL)')
    parser.add_argument('--outreach', required=True, help='Path to Outreach accounts CSV export (Id, Name columns)')
    args = parser.parse_args()

    state     = args.state.upper()
    data_path = Path(f'states/{state}/data.csv')

    if not data_path.exists():
        sys.exit(f'Error: {data_path} not found. Run the pipeline first.')

    # Load Outreach lookup: normalized name → Id
    outreach_lookup = {}
    with open(args.outreach, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            key = normalize(row['Name'], state)
            outreach_lookup[key] = str(int(float(row['Id'])))

    # Load data.csv
    with open(data_path, newline='', encoding='utf-8') as f:
        reader     = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows       = list(reader)

    # Ensure Outreach ID column exists
    if 'Outreach ID' not in fieldnames:
        fieldnames.append('Outreach ID')

    # Match and update
    matched, unmatched = 0, []
    for row in rows:
        key = normalize(row['Account Name'], state)
        oid = outreach_lookup.get(key, '')
        row['Outreach ID'] = oid
        if oid:
            matched += 1
        else:
            unmatched.append(row['Account Name'])

    # Write back
    with open(data_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f'[{state}] Matched: {matched}/{len(rows)}')
    if unmatched:
        print(f'  No Outreach ID for {len(unmatched)} accounts:')
        for name in unmatched:
            print(f'    {name}')
    else:
        print(f'  All accounts matched.')
    print(f'  Updated: {data_path}')


if __name__ == '__main__':
    main()
