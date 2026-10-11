/**
 * English — the second dictionary, and the one that keeps the first honest.
 *
 * Declared `Dict`, like `vi`, so neither language can quietly gain or lose a
 * key. The wording follows the same rules as the Vietnamese: an unknown figure
 * is described as unknown, never shown as zero, and the explanations say what
 * to do next rather than only that something is wrong.
 */

import type { Dict } from "./types";

export const en: Dict = {
  // -- identity -------------------------------------------------------------
  "app.name": "SoTaiSan",
  "app.tagline": "Track stocks, funds, crypto, cash and savings",
  "app.offline_note":
    "Your data stays on this machine. Only market prices and exchange rates come from the internet.",

  // -- navigation -----------------------------------------------------------
  "nav.dashboard": "Overview",
  "nav.holdings": "Holdings",
  "nav.cash": "Cash",
  "nav.savings": "Savings",
  "nav.gold": "Gold",
  "nav.market": "Market",
  "nav.settings": "Settings",

  // -- generic actions ------------------------------------------------------
  "action.save": "Save",
  "action.cancel": "Cancel",
  "action.sell": "Sell",
  "action.edit": "Edit",
  "action.delete": "Delete",
  "action.confirm": "Confirm",
  "action.refresh": "Refresh",
  "action.retry": "Try again",
  "action.copy": "Copy",
  "action.copied": "Copied",

  // -- generic states -------------------------------------------------------
  "state.loading": "Loading…",
  "state.error": "Could not load the data",
  "state.empty": "Nothing here yet",
  "state.saving": "Saving…",
  "state.optional": "optional",
  "state.unknown": "Unknown",
  "state.not_counted": "Not in the total",

  // -- domain words ---------------------------------------------------------
  "kind.stock": "Stock",
  "kind.fund": "Fund",
  "kind.crypto": "Crypto",
  "kind.cash": "Cash",
  "kind.deposit": "Savings",
  "kind.gold": "Gold",
  "kind.all": "All",

  "currency.VND": "VND",
  "currency.USD": "USD",
  "field.currency": "Currency",

  "lang.vi": "Tiếng Việt",
  "lang.en": "English",

  // -- why a figure is missing ---------------------------------------------
  "reason.unpriced": "No price yet",
  "reason.not_convertible": "Cannot convert into the display currency",
  "reason.no_quantity": "Quantity is zero",
  "reason.no_cost": "No cost recorded",
  "reason.no_shop_price": "This gold product is no longer priced",
  "reason.price_list_unreachable": "The gold price list could not be fetched",
  "reason.hint":
    "These positions are left out of the total. Refresh their price, or use a listing quoted in VND or USD.",

  // -- dashboard ------------------------------------------------------------
  "dash.title": "Overview",
  "dash.total": "Total net worth",
  "dash.market_value": "Market value",
  "dash.cash_value": "Cash",
  "dash.gain": "Gain / loss",
  "dash.gain_pct": "Gain / loss %",
  "dash.gain_unknown": "Not available: a position is missing its cost",
  "dash.unrealized": "Unrealised",
  "dash.realized": "Realised gain / loss",
  "dash.realized_count": "{count} sales",
  "dash.realized_unknown": "Not available: a sale is missing its cost",
  "dash.total_gain": "Total gain / loss",
  "dash.total_gain_pct": "Total %",
  "dash.total_hint": "Unrealised + realised",
  "dash.allocation": "Allocation by kind",
  "dash.allocation_hint": "How much of the total each kind of asset makes up",
  "dash.exposure": "By currency",
  "dash.exposure_hint":
    "Only the converted column can be compared between rows; the amount column is the money in its own currency.",
  "dash.exposure_amount": "Amount",
  "dash.exposure_in_base": "Converted",
  "dash.history": "Net worth over time",
  "dash.history_empty":
    "No history yet. Use “Record today” to save the first point.",
  "dash.history_mixed_base":
    "The points below were written in more than one currency, so they are not drawn as a single line.",
  "dash.rates": "Rates in use",
  "dash.rate_stale": "Placeholder rate",
  "dash.rate_as_of": "for {date}",
  "dash.unconverted": "Not in the total",
  "dash.unconverted_hint":
    "The total above leaves these out, so what you actually hold is higher.",
  "dash.snapshot": "Record today",
  "dash.snapshot_done": "Today's value has been recorded",
  "dash.refresh_done": "Updated {count} symbols",
  "dash.refresh_failed": "Could not price: {list}",
  "dash.empty_title": "Nothing tracked yet",
  "dash.empty_body":
    "Start by adding a position on the Holdings page, or writing down a cash balance on the Cash page.",
  "dash.count_assets": "{count} positions",
  "dash.count_cash": "{count} cash accounts",
  "dash.count_deposits": "{count} term deposits",
  "dash.count_gold": "{count} gold holdings",
  "dash.allocation_share": "Share",
  "dash.history_first": "Recorded point",
  "dash.history_single":
    "Only one point has been recorded, so there is no line yet. Record one more to see whether your net worth rose or fell.",

  // -- positions ------------------------------------------------------------
  "hold.title": "Holdings",
  "hold.add": "Add position",
  "hold.search": "Search",
  "hold.search_placeholder": "Search by symbol or name",
  "hold.count": "Positions",
  "hold.total": "Total value",
  "hold.symbol": "Symbol",
  "hold.kind": "Kind",
  "hold.quantity": "Quantity",
  "hold.price": "Price",
  "hold.price_date": "Price date",
  "hold.value": "Value",
  "hold.cost": "Cost",
  "hold.gain": "Gain / loss",
  "hold.gain_pct": "Gain / loss %",
  "hold.actions": "Actions",
  "hold.price_now": "Fetch a new price",
  "hold.delete_confirm": "Delete the position {symbol}?",
  "hold.delete_title": "Delete position",
  "hold.delete_action": "Delete this position",
  "hold.none_title": "Your holdings are empty",
  "hold.none_body":
    "Add your first stock, fund or crypto position. Prices are fetched from the market automatically.",
  "hold.none_filtered": "No position matches the current filter.",

  // -- selling a position ---------------------------------------------------
  "sell.title": "Sell {symbol}",
  "sell.quantity": "Quantity to sell",
  "sell.quantity_hint": "You hold {quantity}. Sell part of it or all of it.",
  "sell.too_many": "You cannot sell more than you hold.",
  "sell.all": "Sell everything",
  "sell.proceeds": "Amount received",
  "sell.proceeds_hint":
    "The total received in {currency}, not a price per unit.",
  "sell.market_hint": "The market value of that part is {amount}",
  "sell.sold_on": "Sold on",
  "sell.cost_note":
    "Cost is released in proportion to what is sold, not in full.",
  "sell.no_cost":
    "This position has no cost recorded, so the sale's gain cannot be worked out. The sale is still recorded.",
  "sell.confirm": "Record the sale",
  "sell.failed": "Could not record the sale",
  "sell.done": "Recorded the sale of {symbol}",

  // -- what has been sold ---------------------------------------------------
  "hold.realized_title": "Sold",
  "hold.realized_hint":
    "Gain already locked in. Kept even when the position was sold in full.",
  "hold.sold_on": "Sold on",
  "hold.proceeds": "Received",
  "hold.cost_removed": "Cost released",
  "hold.delete_sale_title": "Delete this sale",
  "hold.delete_sale_confirm":
    "The sale of {symbol} on {date} will be removed from the history. The position will not come back.",
  "hold.delete_sale_action": "Delete this sale",

  // -- the position form ----------------------------------------------------
  "form.add_title": "Add a position",
  "form.edit_title": "Edit the position",
  "form.symbol_hint":
    "For example AAPL, VIC.VN, VWCE.DE, BTC-USD. Search, or just type the symbol.",
  "form.name": "Name",
  "form.kind": "Kind",
  "form.quantity": "Quantity",
  "form.cost_basis": "Total cost",
  "form.cost_basis_hint":
    "The total you paid, not the price per unit. Leave it blank if you do not remember — gain will then be left out rather than guessed.",
  "form.currency": "Currency of the cost",
  "form.currency_hint": "Only VND and USD are supported.",
  "form.note": "Note",
  "form.invalid": "Not a valid value",
  "form.required": "Required",
  "form.save_failed": "Could not save",

  // -- instrument picker ----------------------------------------------------
  "pick.search": "Find a symbol",
  "pick.placeholder": "Type a name or a symbol, for example Apple or VIC.VN",
  "pick.searching": "Searching…",
  "pick.no_results": "No matching symbol",
  "pick.degraded":
    "The search feed is unreachable. You can still type the symbol into the field above.",

  // -- cash -----------------------------------------------------------------
  "cash.pot": "Cash {currency}",
  "cash.title": "Cash",
  "move.from": "Take from",
  "move.to": "Add to",
  "move.amount": "Amount in {currency}",
  "move.amount_hint":
    "What actually left (or entered) the account. Edit it if the bank says otherwise.",
  "move.edit_note": "Editing the total cost moves the difference to or from the account that paid for it.",
  "move.done_out": "Took {amount} from {account}",
  "move.done_in": "Added {amount} to {account}",
  "move.balance_after": "Balance now {amount}",
  "move.skipped": "No cash moved this time",
  "move.skip.link_off": "The cash link is off.",
  "move.skip.no_amount": "No cost was recorded, so there was nothing to take.",
  "move.skip.no_account":
    "There is no cash balance yet. Open the Cash page to make one.",
  "move.skip.no_rate":
    "There is no rate between these two currencies, so nothing was converted.",
  "move.skip.nothing_paid":
    "This was never paid for out of cash, so nothing is given back.",
  "cash.move_log": "Cash history",
  "cash.move_log_hint":
    "One line per movement in or out of a balance, with the reason. The balance above is these lines plus whatever you have edited by hand.",
  "cash.move_log_empty": "Nothing has moved yet.",
  "cash.move_account":
    "Balance",
  "cash.move_all":
    "Both",
  "cash.move_what": "What",
  "cash.move_date": "Date",
  "cash.move_amount": "Amount",
  "cash.move_history": "History",
  "move.action.buy": "Bought {name}",
  "move.action.sell": "Sold {name}",
  "move.action.open": "Opened {name}",
  "move.action.close": "Closed {name}",
  "move.action.adjust": "Adjusted {name}",
  "move.action.refund": "Refunded {name}",
  "cash.manual_note":
    "There is exactly one balance per currency, and it is a number you write down yourself. When the money moves, edit the balance in place — or let trades move it for you once the cash link is on.",
  "cash.name":
    "Label",
  "cash.balance": "Balance",
  "cash.balance_at": "Written on",
  "cash.note": "Note",
  "cash.value_in_base": "Converted",
  "cash.subtotal": "Subtotal per currency",
  "cash.edit_title":
    "Edit the cash balance",
  "cash.edit_balance": "Edit the balance",
  "cash.add_entry": "Add / withdraw money",
  "cash.entry_title": "Money in or out",
  "cash.entry_hint":
    "Record money going into or out of this balance — a salary, a bill, someone paying you back. It is not an investment, so it needs a reason and no category.",
  "cash.entry_direction": "Direction",
  "cash.entry_in": "Into the balance",
  "cash.entry_out": "Out of the balance",
  "cash.entry_amount": "Amount",
  "cash.entry_date": "Date",
  "cash.entry_reason": "Reason",
  "cash.entry_reason_hint": "For example: October salary, rent, sold the bike.",
  "cash.entry_done_in": "Added {amount} to {name}",
  "cash.entry_done_out": "Took {amount} out of {name}",
  "cash.entry_failed": "Could not record it",
  "cash.adjust_line": "Balance adjusted",
  "move.action.in": "Money in",
  "move.action.out": "Money out",
  "cash.balance_saved": "Balance saved",
  "cash.total": "Total converted",

  // -- savings (term deposits) ---------------------------------------------
  "dep.title": "Savings",
  "dep.add": "Add a term deposit",
  "dep.note":
    "A term deposit: interest is simple, on actual days held over a 365-day year, and is not compounded before maturity — the way the bank pays it.",
  "dep.bank": "Bank / name",
  "dep.principal": "Principal",
  "dep.rate": "Interest rate (% per year)",
  "dep.rate_unit": "%/yr",
  "dep.rate_hint": "Write it as the contract does: 6.5 means 6.5% a year.",
  "dep.start_date": "Start date",
  "dep.maturity_date": "Maturity date",
  "dep.maturity_hint":
    "Leave blank for a demand deposit: no end date, and interest keeps accruing.",
  "dep.demand": "Demand deposit",
  "dep.demand_hint": "No maturity date; interest keeps accruing every day.",
  "dep.term_days": "{days} days",
  "dep.days_accrued": "Days of interest",
  "dep.days_remaining": "Remaining",
  "dep.interest_accrued": "Interest accrued",
  "dep.interest_at_maturity": "Interest at maturity",
  "dep.value": "Value today",
  "dep.value_at_maturity": "Value at maturity",
  "dep.value_in_base": "Converted",
  "dep.matured": "Matured",
  "dep.matured_hint":
    "Interest stopped on the maturity date. This one needs a decision: roll it over, or take it out.",
  "dep.accruing": "Accruing",
  "dep.roll": "Roll over",
  "dep.roll_title": "Roll over into a new term",
  "dep.roll_hint":
    "The interest is added to the principal to make the new deposit. The bank, the rate and the length of the term are kept unless you change them.",
  "dep.roll_new_principal": "New principal",
  "dep.roll_new_rate": "New rate (% per year)",
  "dep.roll_new_maturity": "New maturity date",
  "dep.roll_done": "The deposit has been rolled over",
  "dep.withdraw": "Withdraw",
  "dep.withdraw_title": "Withdraw the deposit",
  "dep.withdraw_hint":
    "The deposit is closed and the money becomes a cash balance, in one step.",
  "dep.withdraw_amount": "Amount received",
  "dep.withdraw_done": "Withdrawn {amount}",
  "dep.edit_title": "Edit the term deposit",
  "dep.delete_confirm": "Delete the deposit {name}?",
  "dep.none_title": "No term deposits yet",
  "dep.none_body":
    "Add a fixed-term deposit to follow its interest accruing day by day.",
  "dep.subtotal": "By currency",
  "dep.projection": "Growth to maturity",
  "dep.projection_empty": "A demand deposit has no maturity to draw towards.",
  "dep.rate_invalid": "The rate must be between 0 and 100",
  "dep.dates_invalid": "The maturity date must be after the start date",

  // -- gold (Vietnamese, priced by the shop) --------------------------------
  "gold.title": "Gold",
  "gold.note":
    "Vietnamese gold does not follow the world price: SJC bars and rings carry their own domestic premium. So the app reads Bảo Tín Minh Châu's published prices — what the shop buys at and what it sells at — and normalises them to a price per chỉ.",
  "gold.add": "Add gold",
  "gold.edit_title": "Edit the gold holding",
  "gold.holding": "Name",
  "gold.product": "Gold product",
  "gold.product_hint":
    "Pick the exact product line you hold. The price follows that line, not a single rate for all gold.",
  "gold.quantity": "Quantity",
  "gold.unit": "Unit",
  "gold.unit.chi": "chỉ",
  "gold.unit.luong": "lượng",
  "gold.unit.gram": "gram",
  "gold.unit.ounce": "ounce",
  "gold.pricing": "Which price",
  "gold.pricing_hint":
    "“What the shop charges” is the market price — the figure the news quotes, and the same basis as every other holding here (what it would cost to buy). “What the shop pays” is what you would actually get for it today; the gap between the two is a real cost.",
  "gold.pricing.buy": "What the shop pays (buy-in)",
  "gold.pricing.sell": "What the shop charges (= market)",
  "gold.shop_price_per": "Shop's published price / {unit}",
  "gold.luong_note": "{luong} per lượng (= 10 chỉ)",
  "gold.price_per_unit": "Price per {unit}",
  "gold.value": "Value",
  "gold.cost": "Cost",
  "gold.gain": "Gain / loss",
  "gold.price_date": "Price date",
  "gold.product_gone":
    "This product line is no longer in the shop's price list. Pick the product again — the app will not quietly value it at another line's price.",
  "gold.shop_down": "The gold price list could not be fetched",
  "gold.shop_down_hint":
    "Bảo Tín Minh Châu's price list is unreachable, so the gold holdings are not valued and are left out of the total.",
  "gold.source_note":
    "Prices published by Bảo Tín Minh Châu, normalised to one chỉ. Domestic gold trades at a premium to the world price, so this is the Vietnamese price and not the world one.",
  "gold.no_products": "No gold line matches",
  "gold.search_products": "Search gold products",
  "gold.none_title": "No gold yet",
  "gold.none_body":
    "Add the gold you hold — in chỉ or in lượng — and pick the exact product line for its price to follow.",
  "gold.delete_confirm": "Delete the gold holding {name}?",
  "gold.total": "Total in gold",
  "gold.weight": "Weight",

  // -- market ---------------------------------------------------------------
  "market.prices": "Stored prices",
  "market.prices_note":
    "“Price date” is the day the number belongs to — the trading session for a listed security, or the NAV date for an open-ended fund; “fetched” is when the source was last asked. An old price is still usable — as long as you can see that it is old.",
  "market.symbol": "Symbol",
  "market.price": "Price",
  "market.currency_of_quote": "Quote currency",
  "market.close_date": "Price date",
  "market.fetched_at": "Fetched",
  "market.row_error": "Price fetch failed",
  "market.source_market": "Market close",
  "market.source_fund": "Fund NAV",
  "market.source_note":
    "“Market close” is the closing price of a listed security. “Fund NAV” is net asset value per certificate, published daily by the fund's management company — an open-ended fund is not listed, so it has no closing price.",
  "market.rates": "Exchange rates",
  "market.rates_note":
    "“feed” is a published rate; “seed” is the built-in placeholder used when the feed has never answered.",
  "market.base": "Base",
  "market.rate": "Rate",
  "market.source": "Source",
  "market.source_feed": "Published",
  "market.source_seed": "Placeholder",
  "market.source_other": "Other",
  "market.seed_warning":
    "A placeholder rate is in use. Use “Refresh rates” once you are online.",
  "market.refresh_prices": "Refresh prices",
  "market.refresh_rates": "Refresh rates",
  "market.refresh_done": "Updated {count} entries",
  "market.refresh_failed": "Could not price: {list}",
  "market.refresh_error": "The rate feed reported an error",
  "market.rate_date": "Rate date",
  "market.stale": "Stale",
  "market.nothing_cached": "No prices stored yet.",
  "market.no_rates": "No rates stored yet.",

  // -- settings -------------------------------------------------------------
  "set.title": "Settings",
  "set.language": "Language",
  "set.language_hint": "Changing the language applies immediately, with no reload.",
  "set.base_currency": "Display currency",
  "set.base_currency_hint":
    "Every total is converted into this currency. Points already recorded keep the currency they were recorded in.",
  "set.about": "About",
  "set.version": "Version",
  "set.database": "Data file",
  "set.database_hint": "Backing up this file backs up everything you have.",
  "set.cash_linked": "Post trades to cash",
  "set.cash_linked_hint":
    "When on, every trade in Holdings, Savings and Gold takes money out of, or puts it into, the cash balance in that trade's own currency, and leaves a line of history. Leave it off while entering the portfolio you already own: then cash and holdings are two numbers you type, with nothing between them.",
  "set.cash_linked_on": "On",
  "set.cash_linked_off": "Off",
  "set.cash_linked_note":
    "Applies to trades from the moment it is switched on. Nothing already recorded is changed.",
  "set.danger": "Delete data",
  "set.danger_hint":
    "Deletes every position, cash balance and recorded point. Your settings and the cached prices and rates are kept. This cannot be undone.",
  "set.wipe": "Delete all data",
  "set.wipe_confirm_title": "Delete all data?",
  "set.wipe_confirm_body":
    "Every position, cash balance and recorded point will be deleted permanently. Back up the data file first if you are not sure.",
  "set.wipe_done": "Deleted {count} records",
  "set.scope": "Scope",
  "set.scope_tracks":
    "This app tracks stocks, funds, crypto and cash, in VND and USD.",
  "set.scope_does_not":
    "It has no goals, no advice, no debts, no income or expenses, and no other currency.",
};
