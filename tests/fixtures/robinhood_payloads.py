import pytest
from fastapi.testclient import TestClient

from server import app


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def all_tabs() -> list[str]:
    return ["1D", "1W", "1M", "3M", "YTD", "ALL"]


@pytest.fixture
def valid_history() -> list[float]:
    return [100.25, 101.75, 99.5]


@pytest.fixture
def disabled_contributions_message() -> str:
    return "Contributions are disabled because no authoritative Robinhood source is configured"


@pytest.fixture
def approximate_warning_message() -> str:
    return "Showing approximate values because authoritative Robinhood portfolio history is unavailable"


@pytest.fixture
def approximate_contributions_warning() -> str:
    return "Top movers are approximate and based on current open stock positions"
