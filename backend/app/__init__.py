"""SoTaiSan — a minimal personal asset tracker.

Four things can be held: stocks, funds, crypto, and cash. Two currencies: VND
and USD. Two languages: Vietnamese and English. Everything else was left out on
purpose — including every trace of the AI advisor the original project was
built around.

`main.py` (this file is `app/__init__.py`) wires the pieces together; the pieces
themselves are:

    money.py           the shared vocabulary (currencies, kinds, languages)
    database.py        SQLite engine and session
    models.py          the seven tables
    market.py          Yahoo Finance: what a symbol is, what it closed at
    fx.py              rates, and the rule that keeps a total honest
    valuation.py       what it is all worth, in one currency
    pricing.py         refreshing, and reporting per-symbol failures
    settings_store.py  the base currency and the language
"""

__version__ = "0.1.0"
