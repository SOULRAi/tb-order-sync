import pytest

from cli.setup import parse_tencent_sheet_reference, resolve_link_selection


def test_parse_tencent_sheet_reference_from_full_url():
    file_id, sheet_id = parse_tencent_sheet_reference(
        "https://docs.qq.com/sheet/DWmlsQUVEcWlyTHlE?tab=000001"
    )
    assert file_id == "DWmlsQUVEcWlyTHlE"
    assert sheet_id == "000001"


def test_parse_tencent_sheet_reference_from_raw_file_id():
    file_id, sheet_id = parse_tencent_sheet_reference("DWnV5Q1dqQ0VrcVBn")
    assert file_id == "DWnV5Q1dqQ0VrcVBn"
    assert sheet_id == ""


def test_parse_tencent_sheet_reference_invalid_url():
    file_id, sheet_id = parse_tencent_sheet_reference("https://docs.qq.com/")
    assert file_id == ""
    assert sheet_id == ""


def test_resolve_link_selection_open_all():
    assert resolve_link_selection("1", 3) == [0, 1, 2]


def test_resolve_link_selection_skip():
    assert resolve_link_selection("0", 3) == []


def test_resolve_link_selection_open_single_item():
    assert resolve_link_selection("3", 3) == [1]


def test_resolve_link_selection_rejects_invalid_number():
    with pytest.raises(ValueError):
        resolve_link_selection("9", 2)
