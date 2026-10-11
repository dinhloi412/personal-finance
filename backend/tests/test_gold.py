"""Gold: the shop's payload, the unit arithmetic, and what happens when the
product line moves.

The failures worth guarding here are all about units and about which of two
published prices is the truth:

1. **A price is per unit, and the payload does not say which unit.** `VÀNG
   MIẾNG SJC` is quoted per lượng and `VÀNG NGUYÊN LIỆU` per chỉ, in the same
   list, with the unit written only inside the product's name. Read the wrong
   one and a holding is out by a factor of ten, which is not a rounding error.
2. **The shop buys at one price and sells at another.** Valuing gold at the
   sell price shows a profit on gold bought a moment ago; the buy price is what
   you would actually get.
3. **A product line can disappear.** `VÀNG MIẾNG SJC` may be renamed, and a
   holding that quietly re-pointed at whatever is first in the list would be
   valued at another product's price without anyone being told.
"""

from __future__ import annotations

import pytest

from app import gold, models, pricing, valuation
from app.money import CHI_IN_GRAMS, GRAMS_PER_UNIT

#: The shop's real figures for 2026-10-11, from the real payload.
SJC_PER_LUONG_BUY = 14_100_000
SJC_PER_LUONG_SELL = 14_480_000
SJC_PER_CHI_BUY = 1_410_000
SJC_PER_CHI_SELL = 1_448_000


class TestThePayloadShape:
    """The payload is a list of one-key objects, not a list of rows."""

    def test_every_gold_line_is_read(self):
        products = gold.prices(fresh=True)
        assert len(products) >= 3

    def test_a_shop_line_carries_both_of_its_prices(self):
        sjc = gold.find("vang-mieng-sjc-vang-sjc")
        assert sjc.buy == SJC_PER_CHI_BUY
        assert sjc.sell == SJC_PER_CHI_SELL
        assert sjc.unit == "chi"

    def test_silver_is_not_gold(self):
        """The same payload carries the shop's silver. Offering someone a silver
        bar when they asked for gold is worse than offering nothing."""
        names = " ".join(product.name.lower() for product in gold.prices())
        assert "bạc" not in names
        assert not any("bac" in product.key for product in gold.prices())

    def test_a_line_with_no_sell_price_still_has_a_buy_price(self):
        # `VÀNG NGUYÊN LIỆU` publishes `bán = 0`, which means "not trading this
        # line today", not "worth nothing".
        raw = gold.find("vang-nguyen-lieu-vang-thi-truong")
        assert raw.sell == raw.buy
        assert raw.buy > 0

    def test_the_shop_date_is_read_as_a_date(self):
        sjc = gold.find("vang-mieng-sjc-vang-sjc")
        assert gold.updated_on(sjc) == "2026-10-11"


class TestTheUnitArithmetic:
    def test_a_bar_priced_per_luong_is_normalised_to_the_chi(self):
        # 14 100 000 for a lượng is 1 410 000 for a chỉ: 1 lượng is 10 chỉ.
        assert gold.weight_in_chi("VÀNG MIẾNG SJC (Vàng SJC)") == 10.0

    def test_a_weight_named_in_the_product_is_read(self):
        # `LƯỢNG` ends in a `g`, and a careless unit pattern reads that `g` as
        # grams: `5 LƯỢNG` became "5 grams", which is fifty times a chỉ and ten
        # times a lượng. This test is the one that caught it.
        assert gold.weight_in_chi("VÀNG 5 LƯỢNG (X)") == 50.0
        assert gold.weight_in_chi("VÀNG 10 LƯỢNG (X)") == 100.0
        assert gold.weight_in_chi("VÀNG 1 LƯỢNG (X)") == 10.0

    def test_a_weight_named_in_chi_is_read(self):
        assert gold.weight_in_chi("VÀNG 5 CHỈ (X)") == 5.0
        assert gold.weight_in_chi("VÀNG 1 CHỈ (X)") == 1.0

    def test_a_weight_in_kilograms_is_read(self):
        # 1 kg is 1000 g and a chỉ is 3.75 g, so 1 kg is 266,67 chỉ.
        assert gold.weight_in_chi("VÀNG 1 KG (X)") == pytest.approx(
            1000 / CHI_IN_GRAMS
        )

    def test_a_decimal_comma_is_read(self):
        assert gold.weight_in_chi("VÀNG 0,5 KG (X)") == pytest.approx(
            500 / CHI_IN_GRAMS
        )

    def test_a_name_with_no_weight_is_one_luong(self):
        # That is how the shop lists its bars and its rings.
        assert gold.weight_in_chi("NHẪN TRÒN TRƠN") == 10.0

    def test_a_derived_price_is_the_published_price_over_the_weight(self):
        from tests.conftest import fake_gold_payload

        rows = gold.parse_payload(fake_gold_payload())
        sjc = next(p for p in rows if p.key == "vang-mieng-sjc-vang-sjc")
        # 14 100 000 for one lượng is 1 410 000 for one chỉ.
        assert sjc.buy == pytest.approx(SJC_PER_CHI_BUY)
        assert sjc.sell == pytest.approx(SJC_PER_CHI_SELL)

    def test_a_line_whose_weight_is_not_stated_is_dropped_not_guessed(self):
        """`ĐỒNG XU VRTL 0.1` states no unit, and reading it as the default one
        lượng put it at 139 600 ₫ a chỉ — a tenth of what a chỉ of gold costs.

        The middle of the list is what catches it: gold is one metal on one
        day, so its lines cannot differ by an order of magnitude. Guessing the
        unit would be worse than dropping the line, because a wrong weight is
        wrong by a factor of ten and says nothing.
        """
        from tests.conftest import fake_gold_payload

        keys = [p.key for p in gold.parse_payload(fake_gold_payload())]
        assert not any("dong-xu" in key for key in keys), keys
        # The plausible lines all survive.
        assert "vang-mieng-sjc-vang-sjc" in keys
        assert "nhan-tron-tron-vang-rong-thang-long" in keys


class TestTheTwoPrices:
    def test_the_default_is_what_the_shop_would_pay_you(self):
        # The buy price, not the sell price: gold is worth what you could get
        # for it, and the spread is a real cost rather than a rounding error.
        assert gold.PRICE_BASIS_BUY == "buy"
        sjc = gold.find("vang-mieng-sjc-vang-sjc")
        assert sjc.price() == sjc.buy
        assert sjc.price("sell") == sjc.sell
        assert sjc.sell > sjc.buy, "a shop sells for more than it buys for"


class TestFindingAProduct:
    def test_a_key_that_is_gone_raises_rather_than_picking_another(self):
        with pytest.raises(gold.GoldError):
            gold.find("vang-mieng-sjc-2019-khong-con")

    def test_search_prefers_a_key_match(self):
        found = gold.search("sjc")
        assert found and "sjc" in found[0].key

    def test_search_finds_by_accented_name(self):
        assert any("NHẪN" in product.name for product in gold.search("nhẫn"))

    def test_an_empty_query_returns_nothing(self):
        assert gold.search("   ") == []

    def test_the_default_product_is_the_sjc_bar(self):
        assert gold.default_key() == "vang-mieng-sjc-vang-sjc"


class TestThePriceListIsFetchedOnce:
    def test_many_holdings_share_one_request(self, monkeypatch):
        calls = {"n": 0}

        def counting():
            calls["n"] += 1
            from tests.conftest import fake_gold_payload

            return fake_gold_payload()

        monkeypatch.setattr(gold, "_fetch_prices", counting)
        gold.forget_cache()

        for _ in range(5):
            gold.prices()
        assert calls["n"] == 1

    def test_an_unreachable_shop_says_so_rather_than_returning_nothing(self, monkeypatch):
        def explode():
            raise OSError("no route to host")

        monkeypatch.setattr(gold, "_fetch_prices", explode)
        gold.forget_cache()
        with pytest.raises(gold.GoldError):
            gold.prices()


# --------------------------------------------------------------------------
# Through the API and the portfolio
# --------------------------------------------------------------------------

SJC_KEY = "vang-mieng-sjc-vang-sjc"


class TestGoldInThePortfolio:
    def test_a_gold_holding_counts_towards_the_total(self, client):
        before = client.get("/api/portfolio").json()
        created = client.post(
            "/api/gold",
            json={
                "name": "SJC 5 chỉ",
                "currency": "VND",
                "quantity": 5,
                "unit": "chi",
                "product_key": SJC_KEY,
                "pricing": "buy",
                "cost_basis": 6_500_000,
            },
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["price"] == SJC_PER_CHI_BUY
        assert body["value"] == pytest.approx(5 * SJC_PER_CHI_BUY)
        assert body["value_base"] == pytest.approx(5 * SJC_PER_CHI_BUY)
        assert body["price_as_of"] == "2026-10-11"

        after = client.get("/api/portfolio").json()
        assert after["gold_value"] == pytest.approx(5 * SJC_PER_CHI_BUY)
        assert after["total"] == pytest.approx(before["total"] + after["gold_value"])
        assert after["counts"]["gold"] == 1

    def test_gold_is_its_own_kind_in_the_allocation(self, client):
        client.post(
            "/api/gold",
            json={
                "name": "SJC", "currency": "VND", "quantity": 1,
                "unit": "chi", "product_key": SJC_KEY,
            },
        )
        kinds = {row["kind"]: row for row in client.get("/api/portfolio").json()["by_kind"]}
        assert kinds["gold"]["count"] == 1
        assert kinds["gold"]["value"] > 0

    def test_a_weight_in_luong_is_converted_to_the_shops_unit(self, client):
        """One lượng of gold is ten chỉ of it, and the price is per chỉ."""
        created = client.post(
            "/api/gold",
            json={
                "name": "SJC 1 lượng", "currency": "VND", "quantity": 1,
                "unit": "luong", "product_key": SJC_KEY,
            },
        ).json()
        assert created["price"] == pytest.approx(SJC_PER_CHI_BUY * 10)
        assert created["value"] == pytest.approx(SJC_PER_LUONG_BUY)

    def test_the_sell_price_can_be_chosen_and_is_higher(self, client):
        created = client.post(
            "/api/gold",
            json={
                "name": "SJC", "currency": "VND", "quantity": 1,
                "unit": "chi", "product_key": SJC_KEY, "pricing": "sell",
            },
        ).json()
        assert created["price"] == SJC_PER_CHI_SELL
        assert created["value"] > SJC_PER_CHI_BUY

    def test_a_dollar_holding_of_vietnamese_gold_is_converted_from_dong(self, client):
        """The shop quotes dong; a holding kept in dollars is still that gold."""
        created = client.post(
            "/api/gold",
            json={
                "name": "SJC", "currency": "USD", "quantity": 10,
                "unit": "chi", "product_key": SJC_KEY,
            },
        ).json()
        # 10 chỉ at 1 410 000 ₫ = 14 100 000 ₫, at 26 000 ₫/$ .
        assert created["value"] == pytest.approx(14_100_000)
        assert created["value_base"] == pytest.approx(14_100_000)

    def test_a_holding_whose_product_is_gone_is_reported_not_zeroed(self, client, db):
        created = client.post(
            "/api/gold",
            json={
                "name": "SJC", "currency": "VND", "quantity": 5,
                "unit": "chi", "product_key": SJC_KEY,
            },
        ).json()
        # The shop stops publishing that line.
        row = db.get(models.Gold, created["id"])
        row.product_key = "vang-mieng-sjc-doi-ten"
        db.commit()

        portfolio = client.get("/api/portfolio").json()
        assert portfolio["gold_value"] == 0.0
        assert portfolio["unconverted"][0]["reason"] == "no_shop_price"
        # And it is NOT valued at nothing silently: it is listed as excluded.
        assert "gold" in [item["kind"] for item in portfolio["unconverted"]]

    def test_an_unreachable_shop_excludes_gold_and_says_why(self, client, monkeypatch, db):
        client.post(
            "/api/gold",
            json={
                "name": "SJC", "currency": "VND", "quantity": 5,
                "unit": "chi", "product_key": SJC_KEY,
            },
        )

        def explode():
            raise OSError("shop is down")

        monkeypatch.setattr(gold, "_fetch_prices", explode)
        gold.forget_cache()

        portfolio = client.get("/api/portfolio").json()
        assert portfolio["gold_value"] == 0.0
        assert portfolio["unconverted"][0]["reason"] == "price_list_unreachable"


class TestTheGoldEndpoints:
    def test_the_price_list_is_offered_with_both_prices(self, client):
        body = client.get("/api/gold/products").json()
        assert body["degraded"] is False
        keys = [product["key"] for product in body["products"]]
        assert SJC_KEY in keys
        sjc = body["products"][keys.index(SJC_KEY)]
        assert sjc["buy"] == SJC_PER_CHI_BUY
        assert sjc["sell"] == SJC_PER_CHI_SELL
        assert sjc["unit"] == "chi"
        assert sjc["updated_on"] == "2026-10-11"

    def test_the_price_list_can_be_searched(self, client):
        body = client.get("/api/gold/products", params={"q": "sjc"}).json()
        assert [p["key"] for p in body["products"]] == [SJC_KEY]

    def test_an_unreachable_shop_is_reported_as_degraded(self, client, monkeypatch):
        def explode():
            raise OSError("shop is down")

        monkeypatch.setattr(gold, "_fetch_prices", explode)
        gold.forget_cache()

        body = client.get("/api/gold/products").json()
        assert body["degraded"] is True
        assert body["products"] == []
        assert body["error"]

    def test_a_product_the_shop_does_not_publish_is_refused(self, client):
        response = client.post(
            "/api/gold",
            json={
                "name": "Vàng gì đó", "currency": "VND", "quantity": 1,
                "unit": "chi", "product_key": "khong-co-san-pham-nay",
            },
        )
        assert response.status_code == 422

    def test_a_holding_can_be_edited(self, client):
        created = client.post(
            "/api/gold",
            json={
                "name": "SJC", "currency": "VND", "quantity": 5,
                "unit": "chi", "product_key": SJC_KEY,
            },
        ).json()
        updated = client.patch(
            f"/api/gold/{created['id']}", json={"quantity": 10}
        ).json()
        assert updated["value"] == pytest.approx(10 * SJC_PER_CHI_BUY)

    def test_editing_to_a_product_that_does_not_exist_is_refused(self, client):
        created = client.post(
            "/api/gold",
            json={
                "name": "SJC", "currency": "VND", "quantity": 5,
                "unit": "chi", "product_key": SJC_KEY,
            },
        ).json()
        response = client.patch(
            f"/api/gold/{created['id']}", json={"product_key": "khong-co"}
        )
        assert response.status_code == 422

    def test_a_holding_can_be_deleted(self, client):
        created = client.post(
            "/api/gold",
            json={
                "name": "SJC", "currency": "VND", "quantity": 5,
                "unit": "chi", "product_key": SJC_KEY,
            },
        ).json()
        assert client.delete(f"/api/gold/{created['id']}").status_code == 204
        assert client.get("/api/gold").json() == []

    def test_a_negative_weight_is_refused(self, client):
        response = client.post(
            "/api/gold",
            json={
                "name": "SJC", "currency": "VND", "quantity": -1,
                "unit": "chi", "product_key": SJC_KEY,
            },
        )
        assert response.status_code == 422

    def test_a_unit_that_is_not_a_weight_is_refused(self, client):
        response = client.post(
            "/api/gold",
            json={
                "name": "SJC", "currency": "VND", "quantity": 1,
                "unit": "kg", "product_key": SJC_KEY,
            },
        )
        assert response.status_code == 422

    def test_a_price_basis_that_is_not_one_of_the_two_is_refused(self, client):
        response = client.post(
            "/api/gold",
            json={
                "name": "SJC", "currency": "VND", "quantity": 1,
                "unit": "chi", "product_key": SJC_KEY, "pricing": "mid",
            },
        )
        assert response.status_code == 422


class TestGoldThroughARefresh:
    def test_refreshing_prices_does_not_touch_gold(self, db):
        """Gold is not a symbol and has no cache row: it is priced from the
        shop's list every time the portfolio is read, so a price refresh has
        nothing to say about it."""
        db.add(
            models.Gold(
                name="SJC", currency="VND", quantity=5,
                unit="chi", product_key=SJC_KEY, pricing="buy",
            )
        )
        db.commit()

        report = pricing.refresh_prices(db)
        assert report["asked"] == 0
        assert db.query(models.PriceCache).count() == 0

    def test_gold_is_in_the_recorded_total(self, db):
        db.add(
            models.Gold(
                name="SJC", currency="VND", quantity=5,
                unit="chi", product_key=SJC_KEY, pricing="buy",
            )
        )
        db.commit()

        row = valuation.write_snapshot(db)
        assert row.gold_value == pytest.approx(5 * SJC_PER_CHI_BUY)
        assert row.total >= row.gold_value


class TestTheUnitTableIsConsistent:
    def test_a_luong_is_ten_chi_everywhere(self):
        # Defined from one constant, so these cannot drift apart.
        assert GRAMS_PER_UNIT["luong"] == GRAMS_PER_UNIT["chi"] * 10
        assert CHI_IN_GRAMS == 3.75

    def test_an_ounce_is_lighter_than_a_luong(self):
        # Which is easy to get backwards, and worth stating once: an ounce is
        # 31,1 g and a lượng is 37,5 g, so a "lượng of gold" is the larger
        # quantity. The world price being per ounce and Vietnam's per lượng is
        # exactly why the unit has to travel with the number.
        assert GRAMS_PER_UNIT["ounce"] < GRAMS_PER_UNIT["luong"]
        assert GRAMS_PER_UNIT["chi"] < GRAMS_PER_UNIT["ounce"]
