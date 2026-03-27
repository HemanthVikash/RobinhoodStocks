import pytest

import server


@pytest.mark.parametrize("tab", ["NOPE", "MAX", ""])
def test_portfolio_rejects_invalid_tab(api_client, tab):
    response = api_client.get("/api/portfolio", params={"tab": tab})
    assert response.status_code == 400
    assert "Unknown tab" in response.json()["detail"]


@pytest.mark.parametrize("tab", ["NOPE", "MAX", ""])
def test_contributions_rejects_invalid_tab(api_client, tab):
    response = api_client.get("/api/contributions", params={"tab": tab})
    assert response.status_code == 400
    assert "Unknown tab" in response.json()["detail"]


@pytest.mark.parametrize("tab", ["1D", "1W", "1M", "3M", "YTD", "ALL"])
def test_portfolio_uses_approximate_when_authoritative_missing(
    api_client, monkeypatch, tab, approximate_warning_message
):
    monkeypatch.setattr(server, "_equity_history", lambda span, interval: [])
    monkeypatch.setattr(server, "_synthesize_equity_history", lambda span, interval: [95.0, 96.25, 97.5])
    response = api_client.get("/api/portfolio", params={"tab": tab})
    assert response.status_code == 200
    assert response.json() == {
        "history": [95.0, 96.25, 97.5],
        "current_value": 97.5,
        "start_value": 95.0,
        "is_approximate": True,
        "warning": approximate_warning_message,
    }


@pytest.mark.parametrize("tab", ["1D", "1W", "1M", "3M", "YTD", "ALL"])
def test_portfolio_uses_authoritative_history(api_client, monkeypatch, tab, valid_history):
    monkeypatch.setattr(server, "_equity_history", lambda span, interval: valid_history)
    response = api_client.get("/api/portfolio", params={"tab": tab})
    assert response.status_code == 200
    assert response.json() == {
        "history": valid_history,
        "current_value": valid_history[-1],
        "start_value": valid_history[0],
        "is_approximate": False,
        "warning": None,
    }


@pytest.mark.parametrize("tab", ["1D", "1W", "1M", "3M", "YTD", "ALL"])
def test_portfolio_fails_when_neither_authoritative_nor_approximate_available(
    api_client, monkeypatch, tab
):
    monkeypatch.setattr(server, "_equity_history", lambda span, interval: [])
    monkeypatch.setattr(server, "_synthesize_equity_history", lambda span, interval: [])
    response = api_client.get("/api/portfolio", params={"tab": tab})
    assert response.status_code == 502
    assert response.json()["detail"] == "Authoritative Robinhood portfolio history unavailable"


@pytest.mark.parametrize("tab", ["1D", "1W", "1M", "3M", "YTD", "ALL"])
def test_contributions_use_approximate_for_all_tabs(
    api_client, monkeypatch, tab, approximate_contributions_warning
):
    monkeypatch.setattr(server, "_contributions", lambda span, interval: [{"s": "AAPL", "c": 10.5}])
    response = api_client.get("/api/contributions", params={"tab": tab})
    assert response.status_code == 200
    assert response.json() == {
        "contributions": [{"s": "AAPL", "c": 10.5}],
        "is_approximate": True,
        "warning": approximate_contributions_warning,
    }
