#!/usr/bin/env python3
"""
refresh_contacts.py
Splits a combined Salesforce contacts export (with Email + Phone columns)
into per-state raw/sf_contacts.csv files, then runs process_contacts.py
for each state to regenerate states/{XX}/contacts.csv.

Uses the existing states/{XX}/raw/sf_accounts.csv files to determine which
Account IDs belong to which state — no need to re-supply accounts/opps/activity.

Usage:
    python3 pipeline/refresh_contacts.py \
        --contacts /Users/ryanminter/Downloads/report1779394506436.csv

Optional — process only specific states (e.g. smoke test FL first):
    python3 pipeline/refresh_contacts.py \
        --contacts /Users/ryanminter/Downloads/report1779394506436.csv \
        --states FL
"""

import argparse
import csv
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Refresh per-state contacts from combined SF export.')
    parser.add_argument('--contacts', required=True, help='Combined SF contacts CSV (with Email + Phone)')
    parser.add_argument('--states',   default='',   help='Comma-separated state codes to process (default: all)')
    args = parser.parse_args()

    contacts_path = Path(args.contacts)
    if not contacts_path.exists():
        print(f'ERROR: contacts file not found: {contacts_path}', file=sys.stderr)
        sys.exit(1)

    only = {s.strip().upper() for s in args.states.split(',') if s.strip()} if args.states else set()

    # ── 1. Build Account ID → state code map from existing raw/sf_accounts.csv ──
    print('Building Account ID → state map from existing raw/sf_accounts.csv files...')
    id_to_code = {}
    all_states_found = set()
    for acct_path in sorted(Path('states').glob('*/raw/sf_accounts.csv')):
        code = acct_path.parts[1]
        with open(acct_path, newline='', encoding='latin-1') as f:
            for row in csv.DictReader(f):
                aid = row.get('Account ID', '').strip()
                if aid:
                    id_to_code[aid] = code
                    all_states_found.add(code)
    print(f'  {len(id_to_code)} account IDs across {len(all_states_found)} states')

    # ── 2. Read new contacts CSV and split by state ───────────────────────────
    print(f'Reading {contacts_path.name}...')
    fieldnames = None
    by_state   = defaultdict(list)
    orphans    = []

    with open(contacts_path, newline='', encoding='latin-1') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            aid  = row.get('Account ID', '').strip()
            code = id_to_code.get(aid)
            if code:
                by_state[code].append(row)
            else:
                orphans.append(row)

    if orphans:
        orphan_path = Path('pipeline/orphaned_contacts.csv')
        print(f'  WARNING: {len(orphans)} orphaned row(s) — Account ID not matched to any known state.')
        print(f'  Writing orphans to {orphan_path} for inspection.')
        with open(orphan_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(orphans)
    else:
        print('  No orphaned contacts.')

    states_to_run = sorted(c for c in by_state if not only or c in only)
    print(f'States to refresh: {len(states_to_run)} ({", ".join(states_to_run)})')

    # ── 3. Per-state: backup, write new raw file, run process_contacts.py ────
    ok, failed = [], []

    for code in states_to_run:
        raw_path = Path(f'states/{code}/raw/sf_contacts.csv')

        # Before/after count
        old_count = 0
        if raw_path.exists():
            with open(raw_path, newline='', encoding='latin-1') as f:
                old_count = sum(1 for _ in csv.DictReader(f))

        new_count = len(by_state[code])
        delta     = new_count - old_count
        delta_str = f'+{delta}' if delta >= 0 else str(delta)
        print(f'\n▶ {code}  old={old_count}  new={new_count}  ({delta_str})')

        # Backup existing file before overwriting
        if raw_path.exists():
            bak_path = raw_path.with_suffix('.csv.bak')
            shutil.copy2(raw_path, bak_path)

        # Write new raw file
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(by_state[code])

        # Run process_contacts.py to regenerate states/{CODE}/contacts.csv
        result = subprocess.run(
            ['python3', 'pipeline/process_contacts.py',
             '--input',  str(raw_path),
             '--state',  code,
             '--output', f'states/{code}/contacts.csv'],
            capture_output=False,
        )
        if result.returncode != 0:
            print(f'  ERROR: process_contacts.py failed for {code}')
            failed.append(code)
        else:
            ok.append(code)

    # ── 4. Summary ────────────────────────────────────────────────────────────
    print(f'\n{"─" * 50}')
    print(f'Done.  Success: {len(ok)}   Failed: {len(failed)}')
    if failed:
        print(f'Failed states: {", ".join(failed)}')
    if orphans:
        print(f'Orphaned contacts written to pipeline/orphaned_contacts.csv — review manually.')
    print('\nTo restore any state from backup:')
    print('  cp states/{XX}/raw/sf_contacts.csv.bak states/{XX}/raw/sf_contacts.csv')


if __name__ == '__main__':
    main()
