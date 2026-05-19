#!/usr/bin/env python3
"""
process_accounts.py
Processes a Salesforce accounts report into a clean accounts CSV.

All accounts are included regardless of owner. No BDM filtering applied here —
that filter applies only to activity data (see process_activity.py).

Usage:
    python3 process_accounts.py \
        --accounts   <path to SF accounts report CSV> \
        --starbridge <path to Starbridge ID report CSV> \
        --geo        <path to geo_lookup.json> \
        --state      "Florida" \
        --output     <output CSV path>

Example:
    python3 scripts/process_accounts.py \
        --accounts   ~/Downloads/territory_FL.csv \
        --starbridge ~/Downloads/starbridge_FL.csv \
        --geo        data/geo_lookup.json \
        --state      Florida \
        --output     ~/Downloads/FL_accounts.csv
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from constants import TIER_S_MIN, TIER_1_MIN, TIER_2_MIN, SQO_POINTS


def pop_tier(population_str):
    try:
        p = int(population_str) if population_str else 0
    except ValueError:
        p = 0
    if p >= TIER_S_MIN: return 'Tier S'
    if p >= TIER_1_MIN: return 'Tier 1'
    if p >= TIER_2_MIN: return 'Tier 2'
    return 'Tier 3'


def load_starbridge(path):
    mapping = {}
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            key = row['Account Name'].strip().lower()
            mapping[key] = row['Starbridge Buyer ID'].strip()
    return mapping


def load_geo(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description='Process Salesforce accounts report.')
    parser.add_argument('--accounts',   required=True, help='Path to SF accounts report CSV')
    parser.add_argument('--starbridge', required=True, help='Path to Starbridge ID report CSV')
    parser.add_argument('--geo',        required=True, help='Path to geo_lookup.json')
    parser.add_argument('--state',      required=True, help='State name (e.g. Florida)')
    parser.add_argument('--output',     required=True, help='Output CSV path')
    args = parser.parse_args()

    starbridge = load_starbridge(args.starbridge)
    geo        = load_geo(args.geo)

    FIELDNAMES = [
        'Account ID', 'Account Name', 'State',
        'Entity Type', 'Muni Type', 'Owner', 'Population',
        'Account Classification', 'Tier', 'SQO Points',
        'Lat', 'Lng',
    ]

    rows_out = []
    unmatched_sb  = []
    unmatched_geo = []

    with open(args.accounts, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            name    = row['Account Name'].strip()
            key     = name.lower()
            tier    = pop_tier(row.get('Population', ''))
            coords  = geo.get(key, {})

            if key not in starbridge:
                unmatched_sb.append(name)
            if not coords:
                unmatched_geo.append(name)

            rows_out.append({
                'Account ID':             starbridge.get(key, ''),
                'Account Name':           name,
                'State':                  args.state,
                'Entity Type':            row.get('Entity Type', '').strip(),
                'Muni Type':              row.get('Muni Type', '').strip(),
                'Owner':                  row.get('New Owner', row.get('Account Owner', '')).strip(),
                'Population':             row.get('Population', '').strip(),
                'Account Classification': row.get('Account Classification', '').strip(),
                'Tier':                   tier,
                'SQO Points':             SQO_POINTS[tier],
                'Lat':                    coords.get('lat', ''),
                'Lng':                    coords.get('lng', ''),
            })

    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows_out)

    print(f'Accounts written: {len(rows_out)}')
    if unmatched_sb:
        print(f'WARNING — No Starbridge ID for {len(unmatched_sb)} accounts:')
        for n in unmatched_sb: print(f'  {n}')
    if unmatched_geo:
        print(f'WARNING — No coordinates for {len(unmatched_geo)} accounts:')
        for n in unmatched_geo: print(f'  {n}')


if __name__ == '__main__':
    main()
