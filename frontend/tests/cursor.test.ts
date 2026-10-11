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

/**
 * A dialog is as wide as it says it is.
 *
 * The overlay used to wrap its panel in a bare `<div>`. As a flex item that div
 * is sized by its own content — 229px for the cash form — so a panel asking for
 * `w-full max-w-lg` was measured against a 229px parent and came out 229px
 * wide. The dialog was a third of the size it asked for, and nothing in the
 * type system or the test suite could see it.
 *
 * `w-full` is what makes the wrapper take the room, and `justify-center` is
 * what puts the panel in the middle of it: adding the first without the second
 * left the dialog hard against the left edge, which is how this test came to
 * check both. The rule is read from the source because that is where the
 * decision lives.
 */
test("the overlay wrapper fills the backdrop and places its panel", () => {
  const ui = readFileSync("src/components/ui.tsx", "utf8");
  // From the declaration to the comment banner that follows it. A regex for a
  // balanced brace block would be a lie; the next banner is a real boundary.
  const start = ui.indexOf("function Overlay(");
  const end = ui.indexOf("Charts", start);
  assert.ok(start > 0 && end > start, "Overlay not found in ui.tsx");
  const overlay = ui.slice(start, end);

  assert.ok(
    /className=\{`flex w-full min-w-0 max-w-full/.test(overlay),
    "the overlay wrapper must be w-full, or the panel inside cannot use max-w-*",
  );
  assert.ok(
    overlay.includes('side === "center" ? "justify-center" : "justify-end"'),
    "the wrapper must place its panel: centred for a dialog, end for a slide-over",
  );
  assert.ok(
    overlay.includes("onMouseDown"),
    "the overlay still has to close on a click outside the panel",
  );
});

/**
 * The dropdown's arrow has room around it.
 *
 * A native select draws its arrow hard against the right edge whatever padding
 * the element has, so a control whose text starts 12px from the left ended with
 * its arrow touching the border on the right. The fix is `appearance: none`,
 * a padding-right wide enough for a drawn chevron, and the chevron itself —
 * and forgetting any one of the three puts the native arrow back, which is a
 * visual regression no type can catch.
 */
test("a dropdown draws its own chevron instead of the browser's", () => {
  const ui = readFileSync("src/components/ui.tsx", "utf8");
  const start = ui.indexOf("export function Select(");
  const end = ui.indexOf("export function Textarea(", start);
  assert.ok(start > 0 && end > start, "Select not found in ui.tsx");
  const select = ui.slice(start, end);

  assert.ok(
    select.includes("appearance-none"),
    "without appearance-none the browser draws its own arrow against the border",
  );
  assert.ok(
    /pr-10/.test(select),
    "the select needs padding-right wide enough for the chevron to sit inside it",
  );
  assert.ok(
    /absolute right-3\.5/.test(select),
    "the chevron must be positioned with a margin from the right edge",
  );
  assert.ok(
    select.includes("pointer-events-none"),
    "the chevron overlays the select, so clicks must pass through it",
  );
});
