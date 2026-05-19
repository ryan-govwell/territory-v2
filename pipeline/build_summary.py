#!/usr/bin/env python3
"""
build_summary.py
Scans all states/*/data.csv files and produces states/summary.json —
a rep → [state codes] map used by the landing page rep filter.

Run after pipeline/run_all.py (or run_all.py calls this automatically):
    python3 pipeline/build_summary.py
"""

import csv
import json
from collections import defaultdict
from pathlib import Path


def main():
    rep_states = defaultdict(set)

    for data_path in sorted(Path('states').glob('*/data.csv')):
        state_code = data_path.parent.name
        with open(data_path, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                owner = row.get('Owner', '').strip()
                if owner:
                    rep_states[owner].add(state_code)

    output = {rep: sorted(states) for rep, states in sorted(rep_states.items())}

    with open('states/summary.json', 'w') as f:
        json.dump(output, f, indent=2)

    total_states = len(set().union(*rep_states.values())) if rep_states else 0
    print(f'Summary written: {len(output)} reps across {total_states} states')


if __name__ == '__main__':
    main()
