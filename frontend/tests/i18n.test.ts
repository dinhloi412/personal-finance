/**
 * The two rules the dictionaries have to satisfy.
 *
 * The `Dict` interface already makes a missing key a compile error, so these
 * tests look for the things a type cannot express: a key left in English inside
 * the Vietnamese file, and a placeholder that exists in one language's sentence
 * and not the other's — which renders as a literal `{count}` in the interface
 * and is never noticed until a user sees it.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { en } from "../src/i18n/en.ts";
import { vi } from "../src/i18n/vi.ts";

const viKeys = Object.keys(vi).sort();
const enKeys = Object.keys(en).sort();

test("both languages define exactly the same keys", () => {
  assert.deepEqual(viKeys, enKeys);
});

test("no translation is empty or a leftover key", () => {
  for (const [key, value] of Object.entries({ ...vi, ...en })) {
    assert.ok(value.trim().length > 0, `${key} is empty`);
    // A value identical to its own key is an unfinished translation.
    assert.notEqual(value, key, `${key} was never translated`);
  }
});

/**
 * Strings that are legitimately the same in both languages.
 *
 * A language names itself, so "Tiếng Việt" and "English" are the same word in
 * both dictionaries. The list is explicit rather than pattern-matched: an
 * exemption should be a decision someone made, not a shape a wrong string can
 * happen to fit.
 */
const SHARED_IN_BOTH_LANGUAGES = new Set(["lang.vi", "lang.en"]);

test("no English sentence was left in the Vietnamese file", () => {
  for (const key of viKeys as (keyof typeof vi)[]) {
    if (SHARED_IN_BOTH_LANGUAGES.has(key)) continue;
    const viet = vi[key];
    const english = en[key as keyof typeof en];
    if (viet !== english) continue;
    // A single shared word is normal ("USD", "Coin"); a whole shared sentence
    // is a dictionary that was never translated.
    assert.ok(
      !/\s/.test(viet.trim()),
      `${key} is an untranslated sentence, identical in both languages: ${viet}`,
    );
  }
});

/** Every `{name}` placeholder used in a string. */
function placeholders(text: string): string[] {
  return [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
}

test("both languages use the same placeholders in the same keys", () => {
  for (const key of viKeys as (keyof typeof vi)[]) {
    const viet = placeholders(vi[key]);
    const english = placeholders(en[key as keyof typeof en]);
    assert.deepEqual(
      viet,
      english,
      `${key} has placeholders ${JSON.stringify(viet)} in vi and ${JSON.stringify(english)} in en`,
    );
  }
});
