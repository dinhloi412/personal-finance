/**
 * The shape of the dictionary, defined once.
 *
 * Both `vi` and `en` are declared `Dict`, so a key added to one language and
 * forgotten in the other is a compile error rather than a blank label someone
 * notices months later. That is the entire reason this interface exists
 * instead of two loose objects.
 *
 * Keys are flat and dotted (`dashboard.total`) rather than nested: a flat map
 * makes "is this key translated?" a question with a one-line answer, and makes
 * a diff of two languages readable.
 */

export interface Dict {
  // -- identity -------------------------------------------------------------
  "app.name": string;
  "app.tagline": string;
  "app.offline_note": string;

  // -- navigation -----------------------------------------------------------
  "nav.dashboard": string;
  "nav.holdings": string;
  "nav.cash": string;
  "nav.savings": string;
  "nav.gold": string;
  "nav.market": string;
  "nav.settings": string;

  // -- generic actions ------------------------------------------------------
  "action.save": string;
  "action.cancel": string;
  "action.edit": string;
  "action.delete": string;
  "action.confirm": string;
  "action.refresh": string;
  "action.retry": string;
  "action.copy": string;
  "action.copied": string;

  // -- generic states -------------------------------------------------------
  "state.loading": string;
  "state.error": string;
  "state.empty": string;
  "state.saving": string;
  "state.optional": string;
  "state.unknown": string;
  "state.not_counted": string;

  // -- domain words ---------------------------------------------------------
  "kind.stock": string;
  "kind.fund": string;
  "kind.crypto": string;
  "kind.cash": string;
  "kind.deposit": string;
  "kind.gold": string;
  "kind.all": string;

  "currency.VND": string;
  "currency.USD": string;
  "field.currency": string;

  // A language names itself, so these two read the same in both dictionaries.
  "lang.vi": string;
  "lang.en": string;

  // -- why a figure is missing ---------------------------------------------
  "reason.unpriced": string;
  "reason.not_convertible": string;
  "reason.no_quantity": string;
  "reason.no_cost": string;
  "reason.no_shop_price": string;
  "reason.price_list_unreachable": string;
  "reason.hint": string;

  // -- dashboard ------------------------------------------------------------
  "dash.title": string;
  "dash.total": string;
  "dash.market_value": string;
  "dash.cash_value": string;
  "dash.gain": string;
  "dash.gain_pct": string;
  "dash.gain_unknown": string;
  "dash.allocation": string;
  "dash.allocation_hint": string;
  "dash.exposure": string;
  "dash.exposure_hint": string;
  "dash.exposure_amount": string;
  "dash.exposure_in_base": string;
  "dash.history": string;
  "dash.history_empty": string;
  "dash.history_mixed_base": string;
  "dash.rates": string;
  "dash.rate_stale": string;
  "dash.rate_as_of": string;
  "dash.unconverted": string;
  "dash.unconverted_hint": string;
  "dash.snapshot": string;
  "dash.snapshot_done": string;
  "dash.refresh_done": string;
  "dash.refresh_failed": string;
  "dash.empty_title": string;
  "dash.empty_body": string;
  "dash.count_assets": string;
  "dash.count_cash": string;
  "dash.count_deposits": string;
  "dash.count_gold": string;
  "dash.allocation_share": string;
  "dash.history_first": string;
  "dash.history_single": string;

  // -- positions ------------------------------------------------------------
  "hold.title": string;
  "hold.add": string;
  "hold.search": string;
  "hold.search_placeholder": string;
  "hold.count": string;
  "hold.total": string;
  "hold.symbol": string;
  "hold.kind": string;
  "hold.quantity": string;
  "hold.price": string;
  "hold.price_date": string;
  "hold.value": string;
  "hold.cost": string;
  "hold.gain": string;
  "hold.gain_pct": string;
  "hold.actions": string;
  "hold.price_now": string;
  "hold.delete_confirm": string;
  "hold.delete_title": string;
  "hold.delete_action": string;
  "hold.none_title": string;
  "hold.none_body": string;
  "hold.none_filtered": string;

  // -- the position form ----------------------------------------------------
  "form.add_title": string;
  "form.edit_title": string;
  "form.symbol_hint": string;
  "form.name": string;
  "form.kind": string;
  "form.quantity": string;
  "form.cost_basis": string;
  "form.cost_basis_hint": string;
  "form.currency": string;
  "form.currency_hint": string;
  "form.note": string;
  "form.required": string;
  "form.save_failed": string;

  // -- instrument picker ----------------------------------------------------
  "pick.search": string;
  "pick.placeholder": string;
  "pick.searching": string;
  "pick.no_results": string;
  "pick.degraded": string;

  // -- cash -----------------------------------------------------------------
  "cash.title": string;
  "cash.add": string;
  "cash.manual_note": string;
  "cash.name": string;
  "cash.balance": string;
  "cash.balance_at": string;
  "cash.note": string;
  "cash.value_in_base": string;
  "cash.subtotal": string;
  "cash.edit_title": string;
  "cash.delete_confirm": string;
  "cash.delete_title": string;
  "cash.delete_action": string;
  "cash.edit_balance": string;
  "cash.balance_saved": string;
  "cash.none_title": string;
  "cash.none_body": string;
  "cash.total": string;

  // -- savings (term deposits) ---------------------------------------------
  "dep.title": string;
  "dep.add": string;
  "dep.note": string;
  "dep.bank": string;
  "dep.principal": string;
  "dep.rate": string;
  "dep.rate_unit": string;
  "dep.rate_hint": string;
  "dep.start_date": string;
  "dep.maturity_date": string;
  "dep.maturity_hint": string;
  "dep.demand": string;
  "dep.demand_hint": string;
  "dep.term_days": string;
  "dep.days_accrued": string;
  "dep.days_remaining": string;
  "dep.interest_accrued": string;
  "dep.interest_at_maturity": string;
  "dep.value": string;
  "dep.value_at_maturity": string;
  "dep.value_in_base": string;
  "dep.matured": string;
  "dep.matured_hint": string;
  "dep.accruing": string;
  "dep.roll": string;
  "dep.roll_title": string;
  "dep.roll_hint": string;
  "dep.roll_new_principal": string;
  "dep.roll_new_rate": string;
  "dep.roll_new_maturity": string;
  "dep.roll_done": string;
  "dep.withdraw": string;
  "dep.withdraw_title": string;
  "dep.withdraw_hint": string;
  "dep.withdraw_account": string;
  "dep.withdraw_amount": string;
  "dep.withdraw_done": string;
  "dep.edit_title": string;
  "dep.delete_confirm": string;
  "dep.none_title": string;
  "dep.none_body": string;
  "dep.subtotal": string;
  "dep.projection": string;
  "dep.projection_empty": string;
  "dep.rate_invalid": string;
  "dep.dates_invalid": string;

  // -- gold (Vietnamese, priced by the shop) --------------------------------
  "gold.title": string;
  "gold.note": string;
  "gold.add": string;
  "gold.edit_title": string;
  "gold.holding": string;
  "gold.product": string;
  "gold.product_hint": string;
  "gold.quantity": string;
  "gold.unit": string;
  "gold.unit.chi": string;
  "gold.unit.luong": string;
  "gold.unit.gram": string;
  "gold.unit.ounce": string;
  "gold.pricing": string;
  "gold.pricing_hint": string;
  "gold.pricing.buy": string;
  "gold.pricing.sell": string;
  "gold.shop_price": string;
  "gold.price_per_unit": string;
  "gold.value": string;
  "gold.cost": string;
  "gold.gain": string;
  "gold.price_date": string;
  "gold.product_gone": string;
  "gold.shop_down": string;
  "gold.shop_down_hint": string;
  "gold.source_note": string;
  "gold.no_products": string;
  "gold.search_products": string;
  "gold.none_title": string;
  "gold.none_body": string;
  "gold.delete_confirm": string;
  "gold.total": string;
  "gold.weight": string;

  // -- market ---------------------------------------------------------------
  "market.prices": string;
  "market.prices_note": string;
  "market.symbol": string;
  "market.price": string;
  "market.currency_of_quote": string;
  "market.close_date": string;
  "market.fetched_at": string;
  "market.row_error": string;
  "market.source_market": string;
  "market.source_fund": string;
  "market.source_note": string;
  "market.rates": string;
  "market.rates_note": string;
  "market.base": string;
  "market.rate": string;
  "market.source": string;
  "market.source_feed": string;
  "market.source_seed": string;
  "market.source_other": string;
  "market.seed_warning": string;
  "market.refresh_prices": string;
  "market.refresh_rates": string;
  "market.refresh_done": string;
  "market.refresh_failed": string;
  "market.refresh_error": string;
  "market.rate_date": string;
  "market.stale": string;
  "market.nothing_cached": string;
  "market.no_rates": string;

  // -- settings -------------------------------------------------------------
  "set.title": string;
  "set.language": string;
  "set.language_hint": string;
  "set.base_currency": string;
  "set.base_currency_hint": string;
  "set.about": string;
  "set.version": string;
  "set.database": string;
  "set.database_hint": string;
  "set.danger": string;
  "set.danger_hint": string;
  "set.wipe": string;
  "set.wipe_confirm_title": string;
  "set.wipe_confirm_body": string;
  "set.wipe_done": string;
  "set.scope": string;
  "set.scope_tracks": string;
  "set.scope_does_not": string;
}

export type TranslationKey = keyof Dict;
export type Vars = Record<string, string | number>;
