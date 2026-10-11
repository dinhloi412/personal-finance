/**
 * Tiếng Việt — the dictionary the app is written in first.
 *
 * Wording rules, kept deliberately consistent so the interface does not read
 * like two people wrote it:
 *
 * - "tài sản" for a holding, "vị thế" for one position.
 * - Money is "số dư" for cash and "giá trị" for a valuation.
 * - A figure we do not know is said to be unknown ("chưa có giá"), never shown
 *   as zero.
 * - Sentence case, no trailing full stop on labels, full sentences only in
 *   the explanations.
 */

import type { Dict } from "./types";

export const vi: Dict = {
  // -- identity -------------------------------------------------------------
  "app.name": "Sổ Tài Sản",
  "app.tagline": "Theo dõi cổ phiếu, quỹ, coin, tiền mặt và tiết kiệm",
  "app.offline_note":
    "Dữ liệu nằm trên máy của bạn. Chỉ có giá thị trường và tỷ giá được lấy từ internet.",

  // -- navigation -----------------------------------------------------------
  "nav.dashboard": "Tổng quan",
  "nav.holdings": "Danh mục",
  "nav.cash": "Tiền mặt",
  "nav.savings": "Tiết kiệm",
  "nav.gold": "Vàng",
  "nav.market": "Thị trường",
  "nav.settings": "Cài đặt",

  // -- generic actions ------------------------------------------------------
  "action.save": "Lưu",
  "action.cancel": "Huỷ",
  "action.edit": "Sửa",
  "action.delete": "Xoá",
  "action.confirm": "Xác nhận",
  "action.refresh": "Cập nhật",
  "action.retry": "Thử lại",
  "action.copy": "Sao chép",
  "action.copied": "Đã sao chép",

  // -- generic states -------------------------------------------------------
  "state.loading": "Đang tải…",
  "state.error": "Không tải được dữ liệu",
  "state.empty": "Chưa có gì",
  "state.saving": "Đang lưu…",
  "state.optional": "không bắt buộc",
  "state.unknown": "Chưa biết",
  "state.not_counted": "Không tính vào tổng",

  // -- domain words ---------------------------------------------------------
  "kind.stock": "Cổ phiếu",
  "kind.fund": "Quỹ",
  "kind.crypto": "Coin",
  "kind.cash": "Tiền mặt",
  "kind.deposit": "Tiết kiệm",
  "kind.gold": "Vàng",
  "kind.all": "Tất cả",

  "currency.VND": "VNĐ",
  "currency.USD": "USD",
  "field.currency": "Loại tiền",

  "lang.vi": "Tiếng Việt",
  "lang.en": "English",

  // -- why a figure is missing ---------------------------------------------
  "reason.unpriced": "Chưa có giá",
  "reason.not_convertible": "Không đổi được sang tiền tệ hiển thị",
  "reason.no_quantity": "Khối lượng bằng 0",
  "reason.no_cost": "Chưa ghi giá vốn",
  "reason.no_shop_price": "Dòng vàng này không còn trong bảng giá",
  "reason.price_list_unreachable": "Chưa lấy được bảng giá vàng",
  "reason.hint":
    "Những vị thế này không được cộng vào tổng. Hãy cập nhật giá, hoặc dùng mã được niêm yết bằng VNĐ/USD.",

  // -- dashboard ------------------------------------------------------------
  "dash.title": "Tổng quan",
  "dash.total": "Tổng tài sản",
  "dash.market_value": "Giá trị thị trường",
  "dash.cash_value": "Tiền mặt",
  "dash.gain": "Lãi/lỗ",
  "dash.gain_pct": "Tỷ lệ lãi/lỗ",
  "dash.gain_unknown": "Chưa tính được vì có vị thế thiếu giá vốn",
  "dash.allocation": "Cơ cấu theo loại",
  "dash.allocation_hint": "Tỷ trọng từng loại tài sản trong tổng giá trị",
  "dash.exposure": "Theo loại tiền",
  "dash.exposure_hint":
    "Cột “quy đổi” mới so sánh được giữa các dòng; cột số lượng là số tiền gốc theo từng loại tiền.",
  "dash.exposure_amount": "Số tiền gốc",
  "dash.exposure_in_base": "Quy đổi",
  "dash.history": "Diễn biến tài sản",
  "dash.history_empty":
    "Chưa có dữ liệu lịch sử. Bấm “Ghi lại hôm nay” để lưu mốc đầu tiên.",
  "dash.history_mixed_base":
    "Các mốc bên dưới được ghi bằng nhiều loại tiền tệ khác nhau nên không vẽ chung một đường.",
  "dash.rates": "Tỷ giá đang dùng",
  "dash.rate_stale": "Tỷ giá tạm tính",
  "dash.rate_as_of": "Ngày {date}",
  "dash.unconverted": "Chưa tính vào tổng",
  "dash.unconverted_hint":
    "Tổng ở trên không bao gồm các mục này, nên con số thực tế sẽ cao hơn.",
  "dash.snapshot": "Ghi lại hôm nay",
  "dash.snapshot_done": "Đã ghi lại giá trị hôm nay",
  "dash.refresh_done": "Đã cập nhật {count} mã",
  "dash.refresh_failed": "Không lấy được giá: {list}",
  "dash.empty_title": "Chưa có tài sản nào",
  "dash.empty_body":
    "Bắt đầu bằng cách thêm một vị thế ở trang Danh mục, hoặc ghi số dư tiền mặt ở trang Tiền mặt.",
  "dash.count_assets": "{count} vị thế",
  "dash.count_cash": "{count} khoản tiền mặt",
  "dash.count_deposits": "{count} khoản tiết kiệm",
  "dash.count_gold": "{count} khoản vàng",
  "dash.allocation_share": "Tỷ trọng",
  "dash.history_first": "Mốc đã ghi",
  "dash.history_single":
    "Mới có một mốc được ghi nên chưa vẽ thành đường. Ghi thêm một mốc nữa để thấy tài sản tăng hay giảm.",

  // -- positions ------------------------------------------------------------
  "hold.title": "Danh mục",
  "hold.add": "Thêm vị thế",
  "hold.search": "Tìm kiếm",
  "hold.search_placeholder": "Tìm theo mã hoặc tên",
  "hold.count": "Số vị thế",
  "hold.total": "Tổng giá trị",
  "hold.symbol": "Mã",
  "hold.kind": "Loại",
  "hold.quantity": "Khối lượng",
  "hold.price": "Giá",
  "hold.price_date": "Ngày giá",
  "hold.value": "Giá trị",
  "hold.cost": "Giá vốn",
  "hold.gain": "Lãi/lỗ",
  "hold.gain_pct": "Lãi/lỗ %",
  "hold.actions": "Thao tác",
  "hold.price_now": "Lấy giá mới",
  "hold.delete_confirm": "Xoá vị thế {symbol}?",
  "hold.delete_title": "Xoá vị thế",
  "hold.delete_action": "Xoá vị thế này",
  "hold.none_title": "Danh mục đang trống",
  "hold.none_body":
    "Thêm cổ phiếu, quỹ hoặc coin đầu tiên. Giá sẽ được lấy tự động từ thị trường.",
  "hold.none_filtered": "Không có vị thế nào khớp với bộ lọc hiện tại.",

  // -- the position form ----------------------------------------------------
  "form.add_title": "Thêm vị thế",
  "form.edit_title": "Sửa vị thế",
  "form.symbol_hint":
    "Ví dụ: AAPL, VIC.VN, VWCE.DE, BTC-USD. Gõ để tìm, hoặc nhập thẳng mã.",
  "form.name": "Tên",
  "form.kind": "Loại tài sản",
  "form.quantity": "Khối lượng",
  "form.cost_basis": "Tổng giá vốn",
  "form.cost_basis_hint":
    "Tổng số tiền đã bỏ ra, không phải giá mỗi đơn vị. Bỏ trống nếu không nhớ — khi đó sẽ không hiện được lãi/lỗ.",
  "form.currency": "Tiền tệ của giá vốn",
  "form.currency_hint": "Chỉ hỗ trợ VNĐ và USD.",
  "form.note": "Ghi chú",
  "form.required": "Bắt buộc",
  "form.save_failed": "Không lưu được",

  // -- instrument picker ----------------------------------------------------
  "pick.search": "Tìm mã",
  "pick.placeholder": "Nhập tên hoặc mã, ví dụ Apple hoặc VIC.VN",
  "pick.searching": "Đang tìm…",
  "pick.no_results": "Không tìm thấy mã nào",
  "pick.degraded":
    "Không kết nối được nguồn tìm kiếm. Bạn vẫn có thể nhập thẳng mã ở ô trên.",

  // -- cash -----------------------------------------------------------------
  "cash.title": "Tiền mặt",
  "cash.add": "Thêm khoản tiền mặt",
  "cash.manual_note":
    "Tiền mặt là số dư bạn tự ghi lại. Khi tiền biến động, sửa trực tiếp vào ô số dư — chỉ một thao tác.",
  "cash.name": "Tên",
  "cash.balance": "Số dư",
  "cash.balance_at": "Ghi ngày",
  "cash.note": "Ghi chú",
  "cash.value_in_base": "Quy đổi",
  "cash.subtotal": "Tổng theo loại tiền",
  "cash.edit_title": "Sửa khoản tiền mặt",
  "cash.delete_confirm": "Xoá khoản tiền mặt {name}?",
  "cash.delete_title": "Xoá khoản tiền mặt",
  "cash.delete_action": "Xoá khoản này",
  "cash.edit_balance": "Sửa số dư",
  "cash.balance_saved": "Đã lưu số dư",
  "cash.none_title": "Chưa có khoản tiền mặt nào",
  "cash.none_body":
    "Thêm tài khoản ngân hàng hoặc ví đầu tiên, kèm số dư hiện tại.",
  "cash.total": "Tổng quy đổi",

  // -- savings (term deposits) ---------------------------------------------
  "dep.title": "Tiết kiệm",
  "dep.add": "Thêm khoản tiết kiệm",
  "dep.note":
    "Tiền gửi có kỳ hạn: lãi được tính theo số ngày thực gửi trên nền 365 ngày, đơn giản, không ghép lãi trước hạn — đúng như ngân hàng trả.",
  "dep.bank": "Ngân hàng / tên khoản",
  "dep.principal": "Số tiền gốc",
  "dep.rate": "Lãi suất (%/năm)",
  "dep.rate_unit": "%/năm",
  "dep.rate_hint": "Ghi đúng như hợp đồng, ví dụ 6,5 cho 6,5% một năm.",
  "dep.start_date": "Ngày gửi",
  "dep.maturity_date": "Ngày đáo hạn",
  "dep.maturity_hint":
    "Để trống nếu là tiền gửi không kỳ hạn: không có ngày kết thúc và lãi vẫn tiếp tục được tính.",
  "dep.demand": "Không kỳ hạn",
  "dep.demand_hint": "Không có ngày đáo hạn, lãi tiếp tục tính mỗi ngày.",
  "dep.term_days": "{days} ngày",
  "dep.days_accrued": "Số ngày đã tính lãi",
  "dep.days_remaining": "Còn lại",
  "dep.interest_accrued": "Lãi đã tích luỹ",
  "dep.interest_at_maturity": "Lãi khi đáo hạn",
  "dep.value": "Giá trị hôm nay",
  "dep.value_at_maturity": "Giá trị khi đáo hạn",
  "dep.value_in_base": "Quy đổi",
  "dep.matured": "Đã đáo hạn",
  "dep.matured_hint":
    "Lãi đã dừng lại ở ngày đáo hạn. Bạn cần quyết định tất toán hay gửi lại.",
  "dep.accruing": "Đang tích luỹ",
  "dep.roll": "Gửi lại",
  "dep.roll_title": "Tất toán và gửi lại",
  "dep.roll_hint":
    "Lãi sẽ được cộng vào gốc thành khoản mới. Mặc định giữ nguyên ngân hàng, lãi suất và độ dài kỳ hạn.",
  "dep.roll_new_principal": "Gốc mới",
  "dep.roll_new_rate": "Lãi suất mới (%/năm)",
  "dep.roll_new_maturity": "Ngày đáo hạn mới",
  "dep.roll_done": "Đã gửi lại khoản tiết kiệm",
  "dep.withdraw": "Tất toán",
  "dep.withdraw_title": "Tất toán khoản tiết kiệm",
  "dep.withdraw_hint":
    "Khoản tiết kiệm sẽ được đóng lại và số tiền chuyển thành một khoản tiền mặt, trong cùng một bước.",
  "dep.withdraw_account": "Ghi vào khoản tiền mặt",
  "dep.withdraw_amount": "Số tiền nhận được",
  "dep.withdraw_done": "Đã tất toán {amount}",
  "dep.edit_title": "Sửa khoản tiết kiệm",
  "dep.delete_confirm": "Xoá khoản tiết kiệm {name}?",
  "dep.none_title": "Chưa có khoản tiết kiệm nào",
  "dep.none_body":
    "Thêm một khoản gửi có kỳ hạn để theo dõi lãi tích luỹ theo từng ngày.",
  "dep.subtotal": "Theo loại tiền",
  "dep.projection": "Diễn biến đến ngày đáo hạn",
  "dep.projection_empty": "Khoản không kỳ hạn không có ngày đáo hạn để vẽ tới.",
  "dep.rate_invalid": "Lãi suất phải từ 0 đến 100",
  "dep.dates_invalid": "Ngày đáo hạn phải sau ngày gửi",

  // -- gold (Vietnamese, priced by the shop) --------------------------------
  "gold.title": "Vàng",
  "gold.note":
    "Vàng trong nước không theo giá thế giới: vàng miếng SJC và vàng nhẫn có mức chênh riêng. Nên app lấy giá niêm yết của Bảo Tín Minh Châu — giá mua và giá bán — rồi quy về giá mỗi chỉ.",
  "gold.add": "Thêm vàng",
  "gold.edit_title": "Sửa khoản vàng",
  "gold.holding": "Tên khoản",
  "gold.product": "Loại vàng",
  "gold.product_hint":
    "Chọn đúng dòng sản phẩm bạn đang giữ. Giá sẽ bám theo dòng đó, không phải theo một mức chung.",
  "gold.quantity": "Số lượng",
  "gold.unit": "Đơn vị",
  "gold.unit.chi": "chỉ",
  "gold.unit.luong": "lượng",
  "gold.unit.gram": "gram",
  "gold.unit.ounce": "ounce",
  "gold.pricing": "Lấy giá nào",
  "gold.pricing_hint":
    "“Giá shop mua” là số tiền bạn thực nhận nếu bán hôm nay. “Giá shop bán” là giá bạn phải trả để mua — dùng giá này thì vàng vừa mua đã thấy lãi, nên mặc định là giá shop mua.",
  "gold.pricing.buy": "Giá shop mua",
  "gold.pricing.sell": "Giá shop bán",
  "gold.shop_price": "Giá shop niêm yết",
  "gold.price_per_unit": "Giá mỗi {unit}",
  "gold.value": "Giá trị",
  "gold.cost": "Giá vốn",
  "gold.gain": "Lãi/lỗ",
  "gold.price_date": "Ngày giá",
  "gold.product_gone":
    "Dòng sản phẩm này không còn trong bảng giá của shop. Hãy chọn lại loại vàng — app không tự gán sang dòng khác vì như vậy là định giá sai mà không nói.",
  "gold.shop_down": "Chưa lấy được bảng giá vàng",
  "gold.shop_down_hint":
    "Không kết nối được tới bảng giá của Bảo Tín Minh Châu, nên các khoản vàng chưa được định giá và không được cộng vào tổng.",
  "gold.source_note":
    "Giá do Bảo Tín Minh Châu niêm yết, quy đổi về một chỉ. Vàng trong nước có mức chênh so với giá thế giới, nên đây là giá trong nước chứ không phải giá thế giới.",
  "gold.no_products": "Không có dòng vàng nào khớp",
  "gold.search_products": "Tìm loại vàng",
  "gold.none_title": "Chưa có khoản vàng nào",
  "gold.none_body":
    "Thêm số vàng bạn đang giữ — theo chỉ hoặc theo lượng — rồi chọn đúng dòng sản phẩm để app bám giá.",
  "gold.delete_confirm": "Xoá khoản vàng {name}?",
  "gold.total": "Tổng vàng",
  "gold.weight": "Khối lượng",

  // -- market ---------------------------------------------------------------
  "market.prices": "Giá đã lưu",
  "market.prices_note":
    "“Ngày giá” là ngày mà con số thuộc về — phiên giao dịch với chứng khoán niêm yết, hoặc ngày chốt NAV với quỹ mở; “lấy lúc” là lần cuối hỏi nguồn. Giá cũ vẫn dùng được, miễn là biết nó cũ.",
  "market.symbol": "Mã",
  "market.price": "Giá",
  "market.currency_of_quote": "Loại tiền của giá",
  "market.close_date": "Ngày giá",
  "market.fetched_at": "Lấy lúc",
  "market.row_error": "Lỗi khi lấy giá",
  "market.source_market": "Giá sàn",
  "market.source_fund": "NAV quỹ",
  "market.source_note":
    "“Giá sàn” là giá đóng cửa của một chứng khoán niêm yết. “NAV quỹ” là giá trị tài sản ròng mỗi chứng chỉ quỹ, do công ty quản lý quỹ công bố mỗi ngày — quỹ mở không niêm yết nên không có giá sàn.",
  "market.rates": "Tỷ giá",
  "market.rates_note":
    "“feed” là tỷ giá thật lấy từ nguồn; “seed” là con số tạm dùng khi chưa có mạng.",
  "market.base": "Tiền tệ gốc",
  "market.rate": "Tỷ giá",
  "market.source": "Nguồn",
  "market.source_feed": "Nguồn thật",
  "market.source_seed": "Tạm tính",
  "market.source_other": "Khác",
  "market.seed_warning":
    "Đang dùng tỷ giá tạm tính. Hãy bấm “Cập nhật tỷ giá” khi có mạng.",
  "market.refresh_prices": "Cập nhật giá",
  "market.refresh_rates": "Cập nhật tỷ giá",
  "market.refresh_done": "Đã cập nhật {count} mục",
  "market.refresh_failed": "Không lấy được giá: {list}",
  "market.refresh_error": "Nguồn tỷ giá báo lỗi",
  "market.rate_date": "Ngày tỷ giá",
  "market.stale": "Cũ",
  "market.nothing_cached": "Chưa có giá nào được lưu.",
  "market.no_rates": "Chưa có tỷ giá nào được lưu.",

  // -- settings -------------------------------------------------------------
  "set.title": "Cài đặt",
  "set.language": "Ngôn ngữ",
  "set.language_hint": "Đổi ngôn ngữ áp dụng ngay, không cần tải lại trang.",
  "set.base_currency": "Tiền tệ hiển thị",
  "set.base_currency_hint":
    "Mọi con số sẽ được quy đổi sang loại tiền này. Các mốc lịch sử đã ghi vẫn giữ nguyên loại tiền lúc ghi.",
  "set.about": "Thông tin",
  "set.version": "Phiên bản",
  "set.database": "Tệp dữ liệu",
  "set.database_hint": "Sao lưu tệp này là sao lưu toàn bộ dữ liệu của bạn.",
  "set.danger": "Xoá dữ liệu",
  "set.danger_hint":
    "Xoá toàn bộ vị thế, số dư tiền mặt và các mốc đã ghi. Cài đặt và giá đã lưu vẫn giữ lại. Không hoàn tác được.",
  "set.wipe": "Xoá toàn bộ dữ liệu",
  "set.wipe_confirm_title": "Xoá toàn bộ dữ liệu?",
  "set.wipe_confirm_body":
    "Toàn bộ vị thế, số dư tiền mặt và lịch sử sẽ bị xoá vĩnh viễn. Hãy sao lưu tệp dữ liệu trước nếu bạn chưa chắc.",
  "set.wipe_done": "Đã xoá {count} mục",
  "set.scope": "Phạm vi",
  "set.scope_tracks":
    "Ứng dụng theo dõi: cổ phiếu, quỹ, coin và tiền mặt — với hai loại tiền VNĐ và USD.",
  "set.scope_does_not":
    "Ứng dụng không có: mục tiêu tài chính, tư vấn, nợ, thu chi, hay bất kỳ loại tiền nào khác.",
};
