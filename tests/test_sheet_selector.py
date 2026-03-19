from utils.sheet_selector import SheetInfo, extract_year_month, select_latest_month_sheet


def test_extract_year_month_supports_month_only_title():
    assert extract_year_month("测试 3月毛利率") == (0, 3)


def test_extract_year_month_supports_year_month_title():
    assert extract_year_month("2026年04月客户退款") == (2026, 4)


def test_extract_year_month_supports_separator_formats():
    assert extract_year_month("2026-03 毛利率") == (2026, 3)
    assert extract_year_month("2026/11 客户退款") == (2026, 11)


def test_select_latest_month_sheet_by_keyword():
    sheets = [
        SheetInfo(sheet_id="000001", title="2月毛利率", index=0),
        SheetInfo(sheet_id="000002", title="3月毛利率", index=1),
        SheetInfo(sheet_id="000003", title="4月毛利率", index=2),
    ]

    selected = select_latest_month_sheet(sheets, keyword="毛利率")

    assert selected.sheet_id == "000003"
    assert selected.title == "4月毛利率"


def test_select_latest_month_sheet_prefers_year_aware_titles_across_years():
    sheets = [
        SheetInfo(sheet_id="000011", title="2025年12月毛利率", index=0),
        SheetInfo(sheet_id="000012", title="2026年1月毛利率", index=1),
        SheetInfo(sheet_id="000013", title="12月毛利率", index=2),
    ]

    selected = select_latest_month_sheet(sheets, keyword="毛利率")

    assert selected.sheet_id == "000012"
    assert selected.title == "2026年1月毛利率"
