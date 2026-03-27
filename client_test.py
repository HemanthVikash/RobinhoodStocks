"""
Simple client probe for Robinhood P&L API.

Usage:
  python client_test.py
  python client_test.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
from typing import Iterable

import requests


DEFAULT_BASE_URL = "http://localhost:8000"
TABS = ["1D", "1W", "1M", "3M", "YTD", "ALL"]
ENDPOINTS = ["/api/ping", "/api/portfolio", "/api/contributions"]


def classify_status(status_code: int) -> str:
    if status_code == 200:
        return "AVAILABLE"
    if status_code in {400, 404, 422}:
        return "INVALID_REQUEST"
    if status_code >= 500:
        return "UNAVAILABLE"
    return "UNKNOWN"


def endpoint_report_rows(endpoint: str, tabs: Iterable[str]) -> list[dict[str, str]]:
    return [{"endpoint": endpoint, "tab": tab} for tab in tabs]


def _print_response(endpoint: str, tab: str | None, response: requests.Response) -> None:
    payload = ""
    try:
        body = response.json()
        if isinstance(body, dict) and "detail" in body:
            payload = f" detail={body['detail']}"
    except ValueError:
        pass

    label = classify_status(response.status_code)
    tab_text = f" tab={tab}" if tab is not None else ""
    print(f"{label:15} status={response.status_code} endpoint={endpoint}{tab_text}{payload}")


def run_probe(base_url: str) -> int:
    failures = 0
    timeout_seconds = 8

    print(f"Probing {base_url}")
    print("-" * 72)

    for endpoint in ENDPOINTS:
        if endpoint == "/api/ping":
            url = f"{base_url}{endpoint}"
            try:
                response = requests.get(url, timeout=timeout_seconds)
                _print_response(endpoint, None, response)
            except requests.RequestException as exc:
                failures += 1
                print(f"UNAVAILABLE      status=ERR endpoint={endpoint} detail={exc}")
            continue

        for tab in TABS:
            url = f"{base_url}{endpoint}"
            try:
                response = requests.get(url, params={"tab": tab}, timeout=timeout_seconds)
                _print_response(endpoint, tab, response)
                if response.status_code >= 500:
                    failures += 1
            except requests.RequestException as exc:
                failures += 1
                print(
                    f"UNAVAILABLE      status=ERR endpoint={endpoint} tab={tab} detail={exc}"
                )

    print("-" * 72)
    print(f"Probe complete. failing_checks={failures}")
    return 1 if failures else 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe API endpoint availability")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Base URL for the running API server (default: http://localhost:8000)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    raise SystemExit(run_probe(args.base_url.rstrip("/")))
