import pytest

from client_test import classify_status, endpoint_report_rows


def test_classify_status_available():
    assert classify_status(200) == "AVAILABLE"


@pytest.mark.parametrize("status_code", [501, 502, 503, 500])
def test_classify_status_unavailable(status_code):
    assert classify_status(status_code) == "UNAVAILABLE"


@pytest.mark.parametrize("status_code", [400, 404, 422])
def test_classify_status_invalid(status_code):
    assert classify_status(status_code) == "INVALID_REQUEST"


def test_endpoint_report_rows_includes_all_tabs():
    tabs = ["1D", "1W", "1M", "3M", "YTD", "ALL"]
    rows = endpoint_report_rows("/api/portfolio", tabs)
    assert len(rows) == len(tabs)
    assert rows[0]["endpoint"] == "/api/portfolio"
    assert rows[0]["tab"] == "1D"
    assert rows[-1]["tab"] == "ALL"
