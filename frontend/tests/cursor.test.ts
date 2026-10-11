/**
 * The pointer rules, checked because they are the one thing a screenshot
 * cannot show.
 *
 * This is not a test of styling for its own sake. Tailwind v4's preflight sets
 * `cursor: default` on buttons — a change from v3 — so the app shipped with
 * every control showing an arrow, and nothing said "this is clickable". The fix
 * is a handful of selectors in `index.css`, and the failure mode is silent:
 * remove one, or change it in a way the browser drops, and the interface goes
 * back to looking inert with every other test still green.
 *
 * Reading the source rather than the built bundle on purpose: the rule's
 * content is what has to be right, and a string check on the minified output
 * would pass on a rule the browser had thrown away.
 */

import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

// Comments mention `cursor: default` and `cursor: pointer` while explaining
// them, so they are stripped first: this test is about what the browser is
// told, and prose is not a declaration.
const css = readFileSync("src/index.css", "utf8").replace(/\/\*[\s\S]*?\*\//g, "");

/**
 * The selector list of the rule whose body sets `cursor: <value>`.
 *
 * Built from the declarations rather than by scanning text, so a mention of a
 * property in a comment (stripped above) or in a value cannot be mistaken for
 * the rule itself.
 */
function selectorFor(value: string): string {
  const declaration = new RegExp(`cursor:\\s*${value}\\s*;`);
  for (const match of css.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
    if (declaration.test(match[2])) return match[1].trim();
  }
  return "";
}

test("something makes every pressable element show a pointer", () => {
  const rule = selectorFor("pointer");
  assert.notEqual(rule, "", "no rule sets cursor: pointer at all");

  for (const part of [
    "button:not(:disabled)",
    'a[href]',
    'select:not(:disabled)',
    "summary",
    "label[for]",
    'input[type="checkbox"]:not(:disabled)',
    'input[type="radio"]:not(:disabled)',
  ]) {
    assert.ok(
      rule.includes(part),
      `the pointer rule does not cover ${part} — that control will show an arrow`,
    );
  }
});

test("a label that owns a control is pressable too", () => {
  // A label with a `for` focuses the field, opens the select, ticks the box.
  // Missing this was a real bug: the filter labels on Holdings showed an arrow
  // while the selects under them showed a hand.
  const rule = selectorFor("pointer");
  assert.ok(rule.includes("label[for]"));
  assert.ok(rule.includes(":has("));
});

test("a disabled control says so instead of pretending", () => {
  const rule = selectorFor("not-allowed");
  assert.notEqual(rule, "", "no rule sets cursor: not-allowed");
  assert.ok(rule.includes("button:disabled"));
  assert.ok(rule.includes("input:disabled"));
  assert.ok(rule.includes('aria-disabled'));
});

test("a text field keeps its caret, not a hand", () => {
  // A pointer over a text input is wrong: the thing you are about to do there
  // is type, and the rule above must not have swallowed inputs wholesale.
  const rule = selectorFor("pointer");
  assert.ok(
    !/(^|[,\s])input\s*[,{]/.test(rule),
    "the pointer rule matches every input, including text fields",
  );
  assert.ok(rule.includes('input[type="checkbox"]'));
});
