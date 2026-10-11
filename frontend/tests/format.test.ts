/**
 * What the formatters must never do.
 *
 * The interesting cases are not the happy ones — they are `null`, zero, and
 * the date that must not shift by a day. Each of those is a way a money figure
 * can be wrong on screen while every type in the codebase says it is right.
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  CURRENCIES,
  DASH,
  decimalsFor,
  formatDate,
  formatMoney,
  formatPercent,
  formatQuantity,
  formatRate,
  formatShare,
  formatSignedMoney,
  known,
  parseDate,
} from "../src/i18n/format.ts";

test("an unknown figure is a dash, never a zero", () => {
  for (const value of [null, undefined, Number.NaN]) {
    assert.equal(formatMoney(value, "VND", "vi"), DASH);
    assert.equal(formatSignedMoney(value, "USD", "en"), DASH);
    assert.equal(formatPercent(value, "vi"), DASH);
    assert.equal(formatQuantity(value, "vi"), DASH);
    assert.equal(formatRate(value, "vi"), DASH);
  }
  assert.equal(known(null), false);
  assert.equal(known(0), true);
});

test("a real zero is shown as zero, not as unknown", () => {
  assert.notEqual(formatMoney(0, "VND", "vi"), DASH);
  assert.match(formatMoney(0, "VND", "vi"), /0/);
});

test("VND is shown without decimals and USD with two", () => {
  assert.equal(decimalsFor("VND"), 0);
  assert.equal(decimalsFor("USD"), 2);
  // 1 000 000,5 dong must not gain a decimal point it does not have.
  assert.doesNotMatch(formatMoney(1_000_000.5, "VND", "vi"), /,5|\.5/);
  assert.match(formatMoney(1_000_000.5, "USD", "en"), /\.50/);
});

test("a number is formatted for the reader's language, not the currency", () => {
  // Both are one and a half million, grouped the way each reader expects.
  const viet = formatQuantity(1_500_000, "vi");
  const english = formatQuantity(1_500_000, "en");
  assert.match(viet, /1\.500\.000/);
  assert.match(english, /1,500,000/);
});

test("a gain and a loss are told apart, and zero is not signed", () => {
  const gain = formatSignedMoney(1_000, "USD", "en");
  const loss = formatSignedMoney(-1_000, "USD", "en");
  assert.match(gain, /\+/);
  assert.match(loss, /−/);
  assert.doesNotMatch(formatSignedMoney(0, "USD", "en"), /[+−]/);
});

test("a percentage is taken as a percentage, not as a fraction", () => {
  // 12.5 must render as 12.50%, not 1250.00%.
  assert.match(formatPercent(12.5, "en"), /12\.50%/);
  assert.match(formatPercent(-3, "en"), /−?3\.00%/);
});

test("a calendar date never shifts by a day", () => {
  // The bug this guards: `new Date("2026-01-01")` is UTC midnight, which is
  // 31/12 in any negative-offset timezone.
  const parsed = parseDate("2026-01-01");
  assert.ok(parsed);
  assert.equal(parsed.getFullYear(), 2026);
  assert.equal(parsed.getMonth(), 0);
  assert.equal(parsed.getDate(), 1);
  assert.equal(formatDate("2026-01-01", "en"), "01/01/2026");
});

test("a timestamp is shown with its date", () => {
  assert.match(formatDate("2026-03-09T10:00:00+00:00", "en"), /2026/);
});

test("the two currencies are the two the app promises", () => {
  assert.deepEqual(CURRENCIES, ["VND", "USD"]);
});

test("a share is unsigned, a change is signed", () => {
  // These are the two things that look alike and are not: a 40% allocation and
  // a +40% return. The first must never print a plus sign.
  assert.doesNotMatch(formatShare(40.2, "vi"), /[+−-]/);
  assert.match(formatPercent(40.2, "vi"), /\+/);
});

test("a share is one decimal and unknown is a dash", () => {
  assert.match(formatShare(40.24, "en"), /40\.2%/);
  assert.equal(formatShare(null, "en"), DASH);
  assert.equal(formatShare(undefined, "vi"), DASH);
});

test("a share of zero is zero, not unknown", () => {
  assert.notEqual(formatShare(0, "en"), DASH);
  assert.match(formatShare(0, "en"), /0\.0%/);
});
