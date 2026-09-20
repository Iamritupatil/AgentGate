#!/usr/bin/env bash
# Prove a deployment is real by exercising the gate through whichever URL the
# browser will use. Run it against the Vercel URL, not just the EC2 host: that
# is the path that also proves the /api rewrite works.
#
#   bash deployment/smoke-test.sh https://agentgate.vercel.app
set -uo pipefail

BASE="${1:-}"
if [ -z "$BASE" ]; then
  echo "Usage: bash $0 <base-url>" >&2
  exit 1
fi
BASE="${BASE%/}"

failures=0

check() {
  local label="$1" expect="$2" body="$3"
  if printf '%s' "$body" | grep -q "$expect"; then
    printf '  PASS  %s\n' "$label"
  else
    printf '  FAIL  %s\n        wanted %s\n        got    %s\n' \
      "$label" "$expect" "${body:-<no response>}"
    failures=$((failures + 1))
  fi
}

evaluate() {
  local amount="$1" order="$2"
  curl -fsS --max-time 15 -X POST "$BASE/api/gate/evaluate" \
    -H 'Content-Type: application/json' \
    -d "{\"principal\":{\"type\":\"Agent\",\"id\":\"support-agent\"},\"action\":\"refund_order\",\"resource\":{\"type\":\"Order\",\"id\":\"$order\"},\"context\":{\"amount\":$amount}}" 2>&1
}

echo "Smoke testing $BASE"

check "GET /api/health" '"status":"ok"' \
  "$(curl -fsS --max-time 15 "$BASE/api/health" 2>&1)"

check "refund 799 is autonomous" '"decision":"ALLOW"' "$(evaluate 799 ORD-1001)"
check "refund 8499 needs a human" '"decision":"REQUIRE_APPROVAL"' "$(evaluate 8499 ORD-1002)"
check "refund 25000 is refused" '"decision":"DENY"' "$(evaluate 25000 ORD-1003)"

check "policy bench passes" '"all_passed":true' \
  "$(curl -fsS --max-time 20 -X POST "$BASE/api/policy-test" 2>&1)"

echo
if [ "$failures" -eq 0 ]; then
  echo "All checks passed. Open $BASE/ and run the scenarios."
  exit 0
fi
echo "$failures check(s) failed."
exit 1
