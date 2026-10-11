"""Guards on the scope of this app.

The project this one was reduced from is a wealth planner with goals, an AI
advisor, cash-flow analysis, debts and a plan engine. None of that belongs
here, and the cheapest way for it to come back is a copy-paste from that
codebase. These tests fail loudly if it does.

They are also the place where the closed sets — currencies, kinds, languages —
are pinned down, because "we only support VND and USD" is a promise that is
easy to make and easy to break in one forgotten literal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app"

#: Names of features this app does not have. A module called one of these is a
#: scope leak, not a coincidence.
FORBIDDEN_NAMES = (
    "advisor",
    "chat",
    "goal",
    "mcp",
    "questionnaire",
    "websearch",
    "liabilit",
    "real_asset",
    "accumulation",
    "cashflow",
    "income",
    "expense",
    "analytics",
    "chain",
    "dividend",
)

def _modules() -> list[Path]:
    return sorted(APP.rglob("*.py"))


class TestScope:
    def test_no_module_is_named_after_a_feature_we_removed(self):
        offenders = [
            path.name
            for path in _modules()
            if any(word in path.name.lower() for word in FORBIDDEN_NAMES)
        ]
        assert offenders == []

    def test_no_such_module_is_even_importable(self):
        import sys

        import app.main  # noqa: F401 — importing the app is what loads them

        loaded = [name for name in sys.modules if name.startswith("app.")]
        for name in loaded:
            assert not any(
                word in name.split(".")[-1].lower() for word in FORBIDDEN_NAMES
            ), name

    def test_no_module_mentions_the_ai_provider(self):
        for path in _modules():
            text = path.read_text(encoding="utf-8").lower()
            assert "openrouter" not in text, path.name
            assert "openai" not in text, path.name

    def test_no_route_is_a_goal_or_a_chat(self):
        from app.main import app

        for path in _api_paths(app):
            lowered = path.lower()
            for word in ("goal", "chat", "advisor", "debt", "liabilit"):
                assert word not in lowered, path

    def test_the_api_is_exactly_what_the_spec_lists(self):
        from app.main import app

        assert sorted(_api_paths(app)) == [
            "/api/assets",
            "/api/assets/{asset_id}",
            "/api/assets/{asset_id}/price",
            "/api/cash",
            "/api/cash/{account_id}",
            "/api/deposits",
            "/api/deposits/{deposit_id}",
            "/api/deposits/{deposit_id}/roll",
            "/api/deposits/{deposit_id}/schedule",
            "/api/deposits/{deposit_id}/withdraw",
            "/api/fx",
            "/api/fx/refresh",
            "/api/gold",
            "/api/gold/products",
            "/api/gold/{gold_id}",
            "/api/health",
            "/api/market",
            "/api/market/search",
            "/api/portfolio",
            "/api/portfolio/history",
            "/api/portfolio/history/{as_of}",
            "/api/portfolio/snapshot",
            "/api/prices",
            "/api/prices/refresh",
            "/api/refresh",
            "/api/settings",
            "/api/settings/wipe",
        ]


def _api_paths(app) -> set[str]:
    """Every API path the app actually serves.

    Read from the OpenAPI document rather than by walking `app.routes`: the
    document is the contract the frontend is written against and what a reader
    sees in `/docs`, so a route missing from it does not exist as far as anyone
    outside this process is concerned.
    """
    return {
        path for path in app.openapi().get("paths", {}) if path.startswith("/api")
    }


class TestClosedSets:
    def test_the_schema_refuses_a_currency_the_app_cannot_hold(self):
        from pydantic import ValidationError

        from app.schemas import AssetCreate, CashCreate

        for currency in ("EUR", "GBP", "JPY", "vnd "):
            with pytest.raises(ValidationError):
                CashCreate(name="x", currency=currency, balance=1)
        with pytest.raises(ValidationError):
            AssetCreate(symbol="X", kind="stock", quantity=1, currency="EUR")

    def test_the_schema_refuses_a_kind_the_app_does_not_track(self):
        from pydantic import ValidationError

        from app.schemas import AssetCreate

        for kind in ("cash", "bond", "real_estate", "commodity"):
            with pytest.raises(ValidationError):
                AssetCreate(symbol="X", kind=kind, quantity=1, currency="USD")

    def test_the_money_vocabulary_is_the_promise(self):
        from app.money import ASSET_KINDS, BASE_CURRENCIES, CURRENCIES, LANGUAGES

        assert CURRENCIES == ("VND", "USD")
        assert BASE_CURRENCIES == ("VND", "USD")
        assert ASSET_KINDS == ("stock", "fund", "crypto", "cash", "deposit", "gold")
        assert LANGUAGES == ("vi", "en")

    def test_the_only_currency_type_is_the_two_currency_one(self):
        """Every money field in the app is annotated with ONE of these aliases.

        There is no second `Currency` anywhere to drift out of step: the two
        definitions below are asserted to be the same two strings, so a third
        currency would have to be added in both places at once, loudly.
        """
        from typing import get_args

        from app.money import Currency as MoneyCurrency
        from app.schemas import Currency as SchemaCurrency

        assert get_args(MoneyCurrency) == ("VND", "USD")
        assert get_args(SchemaCurrency) == ("VND", "USD")

    def test_no_currency_other_than_the_two_is_a_literal_in_a_public_signature(self):
        """No endpoint accepts a currency the app cannot hold.

        Checked against the OpenAPI document the app actually publishes, so it
        covers every route at once rather than every file a reader remembers.
        """
        from app.main import app

        schema = app.openapi()
        for name, definition in schema.get("components", {}).get("schemas", {}).items():
            for field, spec in (definition.get("properties") or {}).items():
                if field != "currency":
                    continue
                enum = spec.get("enum")
                if enum is None:
                    continue
                assert set(enum) <= {"VND", "USD"}, f"{name}.{field} allows {enum}"
