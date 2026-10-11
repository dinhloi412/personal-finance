"""The routers, one module per resource.

There is deliberately no `goals`, no `chat`, no `advisor` and no `watchlist`
here. What this app tracks is what the user asked to track: stocks, funds,
crypto, and a cash balance they edit by hand.
"""

from app.routers import assets, cash, deposits, gold, market, portfolio, settings

__all__ = ["assets", "cash", "deposits", "gold", "market", "portfolio", "settings"]
