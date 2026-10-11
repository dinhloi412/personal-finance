"""Compare two money figures, and exit non-zero when they differ.

Used by `scripts/acceptance.sh` for the one check that is about arithmetic
rather than equality: moving money between two tables must leave the portfolio
total alone. `/tmp` is fine for this: the script is a check, not an artefact.
"""

import sys


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: compare_money.py <before> <after>", file=sys.stderr)
        return 2
    before, after = float(argv[1]), float(argv[2])
    ok = abs(before - after) < 1
    mark = "\033[32mok\033[0m  " if ok else "\033[31mFAIL\033[0m"
    print(f"  {mark} the total went {before:,.0f} -> {after:,.0f}, unchanged")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
