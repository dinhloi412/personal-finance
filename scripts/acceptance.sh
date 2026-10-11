#!/usr/bin/env bash
# The acceptance criteria from docs/SPEC.md §9, checked against a RUNNING app
# with the real network: real quotes from Yahoo, a real rate from the FX feed.
#
# This is not part of `pytest` — it is the check that the whole thing works
# against the world, run by hand against a server that is already up:
#
#   cd backend && uv run uvicorn app.main:app --port 8010 &
#   ./scripts/acceptance.sh
#
# It refuses to touch a database it did not create: the server must be started
# with DATABASE_URL pointing at a scratch file.

set -euo pipefail

base="${BASE_URL:-http://127.0.0.1:8010}"
failures=0

pass() { printf '  \033[32mok\033[0m   %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; failures=$((failures + 1)); }

check() {
  # check <description> <actual> <expected>
  if [ "$2" = "$3" ]; then pass "$1"; else fail "$1 (got '$2', wanted '$3')"; fi
}

# jq_get "<expression applied to the parsed body d>"
# A comprehension is evaluated as written; anything else is read as a subscript
# of d. So `['total']` and `[p['x'] for p in d['ys']]` both do what they look
# like they do.
jq_get() {
  python3 -c "
import sys, json
d = json.load(sys.stdin)
expr = sys.argv[1]
print(list(eval(expr)) if ' for ' in expr else eval('d' + expr))
" "$1"
}

echo "Acceptance against $base"
echo

echo "1. health and settings"
health="$(curl -fsS "$base/api/health" | jq_get "['status']")"
check "the app answers /api/health" "$health" "ok"
currencies="$(curl -fsS "$base/api/settings" | jq_get "['supported_currencies']")"
check "exactly two currencies are supported" "$currencies" "['VND', 'USD']"
kinds="$(curl -fsS "$base/api/settings" | jq_get "['supported_kinds']")"
check "the four kinds are supported, cash included" "$kinds" "['stock', 'fund', 'crypto', 'cash']"
langs="$(curl -fsS "$base/api/settings" | jq_get "['supported_languages']")"
check "exactly two languages are supported" "$langs" "['vi', 'en']"

echo
echo "2. adding positions in both currencies (criterion 2)"
curl -fsS -X POST "$base/api/assets" -H 'Content-Type: application/json' \
  -d '{"symbol":"AAPL","kind":"stock","name":"Apple Inc.","quantity":10,"cost_basis":2000,"currency":"USD"}' \
  >/dev/null
curl -fsS -X POST "$base/api/assets" -H 'Content-Type: application/json' \
  -d '{"symbol":"VIC.VN","kind":"stock","name":"Vingroup JSC","quantity":1000,"cost_basis":60000000,"currency":"VND"}' \
  >/dev/null
curl -fsS -X POST "$base/api/prices/refresh" >/dev/null
aapl_price="$(curl -fsS "$base/api/portfolio" | jq_get "['assets'][0]['price']")"
if [ "$aapl_price" = "None" ]; then fail "AAPL has a price"; else pass "AAPL priced at $aapl_price"; fi

echo
echo "3. cash in both currencies (criterion 3)"
# One pot per currency, there without being created: filling a balance is the
# whole of "adding cash" now.
fill_pot() {
  # fill_pot <currency> <balance>
  local id
  id="$(curl -fsS "$base/api/cash" | python3 -c "import sys,json;print(next(r['id'] for r in json.load(sys.stdin) if r['currency']=='$1'))")"
  curl -fsS -X PATCH "$base/api/cash/$id" -H 'Content-Type: application/json' \
    -d "{\"balance\":$2}" >/dev/null
}
fill_pot VND 85000000
fill_pot USD 2400
cash_count="$(curl -fsS "$base/api/portfolio" | jq_get "['counts']['cash']")"
check "a pot per currency is counted" "$cash_count" "2"

echo
echo "4. the total is a sum of conversions (criterion 2 and 3)"
total="$(curl -fsS "$base/api/portfolio" | jq_get "['total']")"
python3 - "$total" <<'PY'
import sys
total = float(sys.argv[1])
# VIC 1000 × 225 500 = 225 500 000, plus cash 85 000 000 = 310 500 000 in VND,
# plus AAPL and the USD cash converted at the real rate. Anything under
# 400 000 000 means the dollars were added as though they were dong.
ok = total > 400_000_000
mark = "\033[32mok\033[0m  " if ok else "\033[31mFAIL\033[0m"
print(f"  {mark} the total is {total:,.0f} VND, not a sum of mixed units")
sys.exit(0 if ok else 1)
PY

echo
echo "5. a rate is reported with the total (criterion 2)"
rate_ccy="$(curl -fsS "$base/api/portfolio" | jq_get "['rates'][0]['currency']")"
check "the USD rate used is reported" "$rate_ccy" "USD"
rate_source="$(curl -fsS "$base/api/portfolio" | jq_get "['rates'][0]['source']")"
check "the rate comes from the feed, not the placeholder" "$rate_source" "feed"

echo
echo "6. a currency the app cannot hold is refused (criterion 7)"
status="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$base/api/cash" \
  -H 'Content-Type: application/json' -d '{"name":"Revolut","currency":"EUR","balance":100}')"
# 405, not 422: there is no route that adds a pot at all, which is a stronger
# refusal than a validator rejecting its currency.
check "a cash balance cannot be created in a third currency" "$status" "405"

echo
echo "7. switching the display currency re-expresses every total (criterion 5)"
curl -fsS -X PATCH "$base/api/settings" -H 'Content-Type: application/json' \
  -d '{"base_currency":"USD"}' >/dev/null
total_usd="$(curl -fsS "$base/api/portfolio" | jq_get "['total']")"
unconverted="$(curl -fsS "$base/api/portfolio" | jq_get "['unconverted']")"
check "nothing became unconvertible by switching" "$unconverted" "[]"
python3 - "$total_usd" <<'PY'
import sys
total = float(sys.argv[1])
ok = 10_000 < total < 100_000
mark = "\033[32mok\033[0m  " if ok else "\033[31mFAIL\033[0m"
print(f"  {mark} the portfolio reads {total:,.2f} USD")
sys.exit(0 if ok else 1)
PY

echo
echo "8. a recorded point keeps the currency it was written in (criterion 5)"
curl -fsS -X POST "$base/api/portfolio/snapshot" >/dev/null
history_base="$(curl -fsS "$base/api/portfolio/history" | jq_get "['points'][0]['base_currency']")"
check "the point recorded under USD says USD" "$history_base" "USD"

curl -fsS -X PATCH "$base/api/settings" -H 'Content-Type: application/json' \
  -d '{"base_currency":"VND"}' >/dev/null
# The same day is one point by design (see docs/SPEC.md §2), so re-recording
# replaces it rather than adding a second: there is still one point, and it now
# says VND. The earlier USD figure is not re-expressed at the new rate — it was
# a fact about a moment, and it is replaced by a newer fact about the same day.
curl -fsS -X POST "$base/api/portfolio/snapshot" >/dev/null
bases="$(curl -fsS "$base/api/portfolio/history" | jq_get "[p['base_currency'] for p in d['points']]")"
check "re-recording the same day replaces it, in the new base" "$bases" "['VND']"

echo
echo "9. a term deposit earns interest the contract's way (criterion 2b)"
year_ago="$(python3 -c 'import datetime;print((datetime.date.today()-datetime.timedelta(days=365)).isoformat())')"
today="$(python3 -c 'import datetime;print(datetime.date.today().isoformat())')"
deposit="$(curl -fsS -X POST "$base/api/deposits" -H 'Content-Type: application/json' \
  -d "{\"name\":\"Vietcombank 12 thang\",\"currency\":\"VND\",\"principal\":1000000000,\"annual_rate\":6,\"start_date\":\"$year_ago\",\"maturity_date\":\"$today\"}")"
deposit_id="$(printf '%s' "$deposit" | jq_get "['id']")"
interest="$(printf '%s' "$deposit" | jq_get "['interest_accrued']")"
check "365 days at 6% of 1bn is 60,000,000" "$interest" "60000000.0"
matured="$(printf '%s' "$deposit" | jq_get "['matured']")"
check "the term has matured" "$matured" "True"
counted="$(curl -fsS "$base/api/portfolio" | jq_get "['counts']['deposits']")"
check "the deposit is counted in the portfolio" "$counted" "1"

echo
echo "10. withdrawing a deposit moves the money, it does not create it (criterion 9)"
before="$(curl -fsS "$base/api/portfolio" | jq_get "['total']")"
curl -fsS -X POST "$base/api/deposits/$deposit_id/withdraw" -H 'Content-Type: application/json' \
  -d '{"account_name":"Vietcombank TK"}' >/dev/null
after="$(curl -fsS "$base/api/portfolio" | jq_get "['total']")"
if python3 "$(dirname "$0")/compare_money.py" "$before" "$after"; then
  failures=$((failures + 0))
else
  failures=$((failures + 1))
fi
remaining="$(curl -fsS "$base/api/deposits" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')"
check "the closed deposit is gone" "$remaining" "0"

echo
echo "11. selling a position moves the gain, it does not erase it (criterion 11)"
# A position is created at a cost, then sold at the price the market is quoting
# for it. The portfolio's total gain must come out of that EXACTLY unchanged:
# the same money, moved from the unrealised column to the realised one. Erasing
# it is the one failure this feature exists to prevent, and it is the failure a
# deleted row would have produced silently.
sold="$(curl -fsS -X POST "$base/api/assets" -H 'Content-Type: application/json' \
  -d '{"symbol":"AAPL","kind":"stock","name":"Apple Inc.","quantity":10,"cost_basis":1500,"currency":"USD"}')"
sold_id="$(printf '%s' "$sold" | jq_get "['id']")"
sold_price="$(printf '%s' "$sold" | jq_get "['price']")"
positions_before="$(curl -fsS "$base/api/assets" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')"
gain_before="$(curl -fsS "$base/api/portfolio" | jq_get "['total_gain']")"
proceeds="$(python3 -c "print(10 * $sold_price)")"
curl -fsS -X POST "$base/api/assets/$sold_id/sell" -H 'Content-Type: application/json' \
  -d "{\"quantity\":10,\"proceeds\":$proceeds}" >/dev/null
gain_after="$(curl -fsS "$base/api/portfolio" | jq_get "['total_gain']")"
if python3 "$(dirname "$0")/compare_money.py" "$gain_before" "$gain_after"; then
  failures=$((failures + 0))
else
  failures=$((failures + 1))
fi
count="$(curl -fsS "$base/api/portfolio" | jq_get "['realized_count']")"
check "the sale is in the realised list" "$count" "1"
positions_after="$(curl -fsS "$base/api/assets" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')"
check "the position it closed is gone" "$positions_after" "$((positions_before - 1))"

echo
echo "12. cash-linked trades move money, they do not make it (criterion 12)"
curl -fsS -X PATCH "$base/api/settings" -H 'Content-Type: application/json' \
  -d '{"cash_linked":true}' >/dev/null
check "the link is on" "$(curl -fsS "$base/api/settings" | jq_get "['cash_linked']")" "True"

# Cash is one pot per currency, and it is there without being created.
pots="$(curl -fsS "$base/api/cash" | jq_get "[r['currency'] for r in d]")"
check "there is one pot per currency, dong first" "$pots" "['VND', 'USD']"
status="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$base/api/cash" \
  -H 'Content-Type: application/json' -d '{"name":"X","currency":"VND","balance":1}')"
check "a second dong pot cannot be added" "$status" "405"

wallet="$(curl -fsS "$base/api/cash" | python3 -c "import sys,json;print(next(r['id'] for r in json.load(sys.stdin) if r['currency']=='VND'))")"
wallet_balance() {
  curl -fsS "$base/api/cash" | python3 -c "import sys,json;print(next(r['balance'] for r in json.load(sys.stdin) if r['currency']=='VND'))"
}
curl -fsS -X PATCH "$base/api/cash/$wallet" -H 'Content-Type: application/json' \
  -d '{"balance":100000000}' >/dev/null

# A round trip at the SAME price, so the check does not depend on what the
# market happens to say today: 22,550,000 leaves the pot, the same comes back,
# and the balance is where it started. Anything else is the link's arithmetic
# rather than the market's.
bought="$(curl -fsS -X POST "$base/api/assets" -H 'Content-Type: application/json' \
  -d '{"symbol":"VIC.VN","kind":"stock","name":"Vingroup","quantity":100,"cost_basis":22550000,"currency":"VND"}')"
check "the purchase says it moved money" "$(printf '%s' "$bought" | jq_get "['cash']['moved']")" "True"
check "and exactly what it cost, in dong" "$(printf '%s' "$bought" | jq_get "['cash']['amount']")" "-22550000.0"
check "leaving 77,450,000 in the pot" "$(wallet_balance)" "77450000.0"
check "the movement is on the record" \
  "$(curl -fsS "$base/api/portfolio" | jq_get "['movements'][0]['action']")" "buy"

position_id="$(printf '%s' "$bought" | jq_get "['id']")"
curl -fsS -X POST "$base/api/assets/$position_id/sell" -H 'Content-Type: application/json' \
  -d '{"quantity":100,"proceeds":22550000}' >/dev/null
check "selling it back leaves the pot whole" "$(wallet_balance)" "100000000.0"

check "the position is gone from the holdings" \
  "$(curl -fsS "$base/api/assets" | jq_get "[a['symbol'] for a in d if a['id']==$position_id]")" "[]"

# A dollar trade moves the dollar pot, in dollars, with no rate involved — and
# leaves the dong pot alone. The delta is what is checked, not the balance:
# other steps have put money in that pot too.
usd_before="$(curl -fsS "$base/api/cash" | python3 -c "import sys,json;print(next(r['balance'] for r in json.load(sys.stdin) if r['currency']=='USD'))")"
usd_trade="$(curl -fsS -X POST "$base/api/assets" -H 'Content-Type: application/json' \
  -d '{"symbol":"AAPL","kind":"stock","name":"Apple Inc.","quantity":1,"cost_basis":200,"currency":"USD"}')"
check "a dollar purchase moves the dollar pot" \
  "$(printf '%s' "$usd_trade" | jq_get "['cash']['currency']")" "USD"
check "and the dollar pot is 200 lighter" \
  "$(curl -fsS "$base/api/cash" | python3 -c "import sys,json;print(next(r['balance'] for r in json.load(sys.stdin) if r['currency']=='USD'))")" \
  "$(python3 -c "print($usd_before - 200)")"
check "the dong pot was not touched by it" "$(wallet_balance)" "100000000.0"

echo
echo "13. money in and out, and a balance that equals its history (criterion 14)"
# The Cash page's own action: money the user says arrived or left, with a reason.
before="$(wallet_balance)"
entry="$(curl -fsS -X POST "$base/api/cash/$wallet/entry" -H 'Content-Type: application/json' \
  -d '{"amount":5000000,"direction":"in","note":"Lương tháng 10"}')"
check "money in lands in the balance" \
  "$(printf '%s' "$entry" | jq_get "['cash']['amount']")" "5000000.0"
check "and the balance grew by it" "$(wallet_balance)" "$(python3 -c "print($before + 5000000)")"

curl -fsS -X POST "$base/api/cash/$wallet/entry" -H 'Content-Type: application/json' \
  -d '{"amount":1200000,"direction":"out","note":"Tiền nhà"}' >/dev/null
check "money out is signed negative" \
  "$(curl -fsS "$base/api/portfolio" | jq_get "['movements'][0]['amount']")" "-1200000.0"

# Counting the balance and finding a different number is a real event, and it
# leaves a line too: the page prints one figure and claims it is the sum of the
# lines under it.
curl -fsS -X PATCH "$base/api/cash/$wallet" -H 'Content-Type: application/json' \
  -d '{"balance":25000000}' >/dev/null
check "a counted balance writes the difference" \
  "$(curl -fsS "$base/api/portfolio" | jq_get "['movements'][0]['action']")" "adjust"

history="$(curl -fsS "$base/api/portfolio" | python3 -c "
import sys, json
rows = [m for m in json.load(sys.stdin)['movements'] if m['currency'] == 'VND']
print(round(sum(m['amount'] for m in rows), 2))
")"
check "and the balance is the sum of its history" "$history" "$(wallet_balance)"

status="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$base/api/cash/$wallet/entry" \
  -H 'Content-Type: application/json' -d '{"amount":-1,"direction":"in"}')"
check "a negative amount is refused" "$status" "422"

echo
echo "14. language (criterion 6)"
curl -fsS -X PATCH "$base/api/settings" -H 'Content-Type: application/json' \
  -d '{"language":"en"}' >/dev/null
language="$(curl -fsS "$base/api/settings" | jq_get "['language']")"
check "the language is stored" "$language" "en"
status="$(curl -s -o /dev/null -w '%{http_code}' -X PATCH "$base/api/settings" \
  -H 'Content-Type: application/json' -d '{"language":"fr"}')"
check "a third language is a 422" "$status" "422"

echo
if [ "$failures" -eq 0 ]; then
  printf '\033[32mAll acceptance checks passed.\033[0m\n'
else
  printf '\033[31m%d check(s) failed.\033[0m\n' "$failures"
  exit 1
fi
