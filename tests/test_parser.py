"""Tests for utils.parser."""

import pytest
from utils.parser import parse_number, normalize_order_no


class TestParseNumber:
    def test_int(self):
        assert parse_number(650) == 650.0

    def test_float(self):
        assert parse_number(12.5) == 12.5

    def test_string_int(self):
        assert parse_number("650") == 650.0

    def test_string_float(self):
        assert parse_number("650.0") == 650.0

    def test_string_with_spaces(self):
        assert parse_number("  12.5  ") == 12.5

    def test_none(self):
        assert parse_number(None) is None

    def test_empty_string(self):
        assert parse_number("") is None

    def test_whitespace_only(self):
        assert parse_number("   ") is None

    def test_chinese_text(self):
        assert parse_number("没报价") is None

    def test_mixed_text(self):
        assert parse_number("abc123") is None

    def test_currency_symbol(self):
        # First version: strict mode, currency symbols are not parsed
        assert parse_number("¥650") is None

    def test_zero(self):
        assert parse_number(0) == 0.0

    def test_negative(self):
        assert parse_number("-10.5") == -10.5

    def test_string_zero(self):
        assert parse_number("0") == 0.0


class TestNormalizeOrderNo:
    def test_basic(self):
        assert normalize_order_no("SF12345") == "SF12345"

    def test_trim_spaces(self):
        assert normalize_order_no("  SF12345  ") == "SF12345"

    def test_none(self):
        assert normalize_order_no(None) == ""

    def test_empty(self):
        assert normalize_order_no("") == ""

    def test_numeric(self):
        assert normalize_order_no(12345) == "12345"

    def test_preserves_characters(self):
        assert normalize_order_no("SF-2024-001") == "SF-2024-001"
