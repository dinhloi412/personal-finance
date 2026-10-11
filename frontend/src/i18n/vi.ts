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
  "app.tagline": "Cổ phiếu, quỹ, coin, tiền mặt và tiết kiệm",
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
  "action.sell": "Bán",
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
  "dash.unrealized": "Chưa thực hiện",
  "dash.realized": "Lãi/lỗ đã thực hiện",
  "dash.realized_count": "{count} lệnh đã bán",
  "dash.realized_unknown": "Chưa tính được vì có lệnh bán thiếu giá vốn",
  "dash.total_gain": "Tổng lãi/lỗ",
  "dash.total_gain_pct": "Tỷ lệ tổng",
  "dash.total_hint": "Chưa thực hiện + đã thực hiện",
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

  // -- selling a position ---------------------------------------------------
  "sell.title": "Bán {symbol}",
  "sell.quantity": "Khối lượng bán",
  "sell.quantity_hint": "Đang giữ {quantity}. Bán một phần hoặc toàn bộ.",
  "sell.too_many": "Không thể bán nhiều hơn số đang giữ.",
  "sell.all": "Bán toàn bộ",
  "sell.proceeds": "Số tiền nhận được",
  "sell.proceeds_hint":
    "Tổng tiền thực nhận bằng {currency}, không phải giá mỗi đơn vị.",
  "sell.market_hint": "Giá thị trường của phần này: {amount}",
  "sell.sold_on": "Ngày bán",
  "sell.cost_note":
    "Giá vốn được trừ theo đúng tỷ lệ phần đã bán, không phải toàn bộ giá vốn.",
  "sell.no_cost":
    "Vị thế này chưa ghi giá vốn, nên lãi/lỗ của lệnh bán sẽ không tính được. Lệnh bán vẫn được ghi lại.",
  "sell.confirm": "Xác nhận bán",
  "sell.failed": "Không ghi được lệnh bán",
  "sell.done": "Đã ghi nhận lệnh bán {symbol}",

  // -- what has been sold ---------------------------------------------------
  "hold.realized_title": "Đã bán",
  "hold.realized_hint":
    "Lãi/lỗ đã chốt. Vẫn được giữ lại kể cả khi vị thế đã bán hết.",
  "hold.sold_on": "Ngày bán",
  "hold.proceeds": "Tiền nhận",
  "hold.cost_removed": "Giá vốn đã trừ",
  "hold.delete_sale_title": "Xoá lệnh bán",
  "hold.delete_sale_confirm":
    "Lệnh bán {symbol} ngày {date} sẽ bị xoá khỏi lịch sử. Vị thế đã bán sẽ không được khôi phục.",
  "hold.delete_sale_action": "Xoá lệnh bán này",

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
  "form.invalid": "Không hợp lệ",
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
  "cash.pot": "Tiền mặt {currency}",
  "cash.title": "Tiền mặt",
  "move.from": "Trừ từ",
  "move.to": "Cộng vào",
  "move.amount": "Số tiền {currency}",
  "move.amount_hint":
    "Số tiền thực sự rời khỏi (hoặc vào) tài khoản. Sửa được nếu ngân hàng báo khác.",
  "move.edit_note": "Sửa tổng giá vốn sẽ trừ/cộng phần chênh lệch vào tài khoản đã trả cho khoản này.",
  "move.done_out": "Đã trừ {amount} từ {account}",
  "move.done_in": "Đã cộng {amount} vào {account}",
  "move.balance_after": "Số dư còn {amount}",
  "move.skipped": "Không trừ/cộng tiền mặt lần này",
  "move.skip.link_off": "Chế độ nối tiền mặt đang tắt.",
  "move.skip.no_amount": "Không có giá vốn nên không có gì để trừ.",
  "move.skip.no_account":
    "Chưa có sổ tiền mặt nào. Mở trang Tiền mặt để tạo.",
  "move.skip.no_rate":
    "Không có tỷ giá giữa hai loại tiền này, nên không tự quy đổi được.",
  "move.skip.nothing_paid":
    "Khoản này chưa từng được chi từ tiền mặt, nên không hoàn lại gì.",
  "cash.move_log": "Lịch sử giao dịch",
  "cash.move_log_hint":
    "Mỗi dòng là một lần tiền vào hoặc ra khỏi một sổ, kèm lý do. Số dư ở trên là kết quả của những dòng này cộng với số bạn tự sửa.",
  "cash.move_log_empty": "Chưa có giao dịch nào.",
  "cash.move_account":
    "Sổ",
  "cash.move_all":
    "Cả hai sổ",
  "cash.move_what": "Nội dung",
  "cash.move_date": "Ngày",
  "cash.move_amount": "Số tiền",
  "cash.move_history": "Lịch sử",
  "move.action.buy": "Mua {name}",
  "move.action.sell": "Bán {name}",
  "move.action.open": "Gửi tiết kiệm {name}",
  "move.action.close": "Tất toán {name}",
  "move.action.adjust": "Điều chỉnh {name}",
  "move.action.refund": "Hoàn tiền {name}",
  "cash.manual_note":
    "Mỗi loại tiền có đúng một sổ, và đó là số dư bạn tự ghi lại. Khi tiền biến động, sửa trực tiếp vào ô số dư — hoặc để các giao dịch tự cộng/trừ khi bạn bật chế độ nối tiền mặt.",
  "cash.name":
    "Tên sổ",
  "cash.balance": "Số dư",
  "cash.balance_at": "Ghi ngày",
  "cash.note": "Ghi chú",
  "cash.value_in_base": "Quy đổi",
  "cash.subtotal": "Tổng theo loại tiền",
  "cash.edit_title":
    "Sửa sổ tiền mặt",
  "cash.edit_balance": "Sửa số dư",
  "cash.add_entry": "Nạp / rút tiền",
  "cash.entry_title": "Nạp hoặc rút tiền",
  "cash.entry_hint":
    "Ghi lại tiền vào hoặc ra khỏi sổ này — lương, hoá đơn, tiền người khác trả. Không phải giao dịch đầu tư, nên chỉ cần một lý do, không phân loại.",
  "cash.entry_direction": "Chiều tiền",
  "cash.entry_in": "Cộng vào sổ",
  "cash.entry_out": "Trừ khỏi sổ",
  "cash.entry_amount": "Số tiền",
  "cash.entry_date": "Ngày",
  "cash.entry_reason": "Lý do",
  "cash.entry_reason_hint": "Ví dụ: Lương tháng 10, Tiền nhà, Bán xe.",
  "cash.entry_done_in": "Đã cộng {amount} vào {name}",
  "cash.entry_done_out": "Đã trừ {amount} khỏi {name}",
  "cash.entry_failed": "Không ghi được",
  "cash.adjust_line": "Điều chỉnh số dư",
  "move.action.in": "Nạp tiền",
  "move.action.out": "Rút tiền",
  "cash.balance_saved": "Đã lưu số dư",
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
    "“Giá shop bán” là giá thị trường — đúng con số báo chí đưa, và cùng cách tính với mọi tài sản khác trong app (giá bạn phải trả để mua). “Giá shop mua” là số tiền bạn thực nhận nếu bán hôm nay; chênh lệch giữa hai giá là chi phí thật.",
  "gold.pricing.buy": "Giá shop mua vào",
  "gold.pricing.sell": "Giá shop bán ra (= giá thị trường)",
  "gold.shop_price_per": "Giá shop niêm yết / {unit}",
  "gold.luong_note": "{luong} ₫ một lượng (= 10 chỉ)",
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
  "set.cash_linked": "Tự trừ và cộng vào tiền mặt",
  "set.cash_linked_hint":
    "Khi bật, mỗi thao tác ở Danh mục, Tiết kiệm và Vàng sẽ tự trừ hoặc cộng vào sổ tiền mặt đúng loại tiền của giao dịch, và để lại một dòng lịch sử. Để tắt trong lúc nhập dữ liệu ban đầu: khi đó tiền mặt và tài sản là hai con số bạn tự nhập, không liên quan tới nhau.",
  "set.cash_linked_on": "Đang bật",
  "set.cash_linked_off": "Đang tắt",
  "set.cash_linked_note":
    "Chỉ áp dụng cho thao tác từ lúc bật trở đi. Dữ liệu đã nhập trước đó không bị thay đổi.",
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
