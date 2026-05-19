#!/usr/bin/env bash
# Run the full territory data pipeline for one state.
#
# Usage:
#   ./pipeline/run.sh FL Florida
#
# Before running, place your four Salesforce exports in states/<CODE>/raw/:
#   sf_accounts.csv        — Salesforce accounts report
#   sf_starbridge.csv      — Starbridge Buyer ID report
#   sf_opportunities.csv   — Salesforce opportunities report
#   sf_activity.csv        — Salesforce activity report
#
# Output: states/<CODE>/data.csv  (ready for the dashboard)
#
# After running, add external IDs (run both):
#
#   Salesforce IDs (covers all states in one go):
#     python3 pipeline/add_salesforce_ids.py --input <path/to/sf_accounts_report.csv>
#   SF report must include: Account ID, Starbridge Buyer ID, Account Name
#
#   Outreach IDs (per state):
#     python3 pipeline/add_outreach_ids.py --state <CODE> --outreach <path/to/Accounts_export.csv>
#   Export from Outreach: Accounts → Export → Id and Name columns only.

set -euo pipefail

STATE_CODE=${1:?'Usage: ./pipeline/run.sh STATE_CODE STATE_NAME  (e.g. FL Florida)'}
STATE_NAME=${2:?'Usage: ./pipeline/run.sh STATE_CODE STATE_NAME  (e.g. FL Florida)'}
RAW="states/${STATE_CODE}/raw"
TMP=$(mktemp -d)
GEO="pipeline/geo/geo_lookup.json"

echo "▶ ${STATE_NAME} (${STATE_CODE})"

echo "  1/4  accounts..."
python3 pipeline/process_accounts.py \
  --accounts    "${RAW}/sf_accounts.csv" \
  --starbridge  "${RAW}/sf_starbridge.csv" \
  --geo         "${GEO}" \
  --state       "${STATE_NAME}" \
  --state-code  "${STATE_CODE}" \
  --output      "${TMP}/accounts.csv"

echo "  2/4  opportunities..."
python3 pipeline/process_opportunities.py \
  --input  "${RAW}/sf_opportunities.csv" \
  --output "${TMP}/opportunities.csv"

echo "  3/4  activity..."
python3 pipeline/process_activity.py \
  --input  "${RAW}/sf_activity.csv" \
  --output "${TMP}/activity.csv"

echo "  4/4  merge..."
python3 pipeline/merge.py \
  --accounts      "${TMP}/accounts.csv" \
  --opportunities "${TMP}/opportunities.csv" \
  --activity      "${TMP}/activity.csv" \
  --output        "states/${STATE_CODE}/data.csv"

rm -rf "${TMP}"
echo "✓ Done → states/${STATE_CODE}/data.csv"
