"""
Robinhood P&L API Server
Requires: pip install fastapi uvicorn robin_stocks pyotp

Run: python server.py
"""

import robin_stocks.robinhood as r
from robin_stocks.robinhood.helper import request_get
import pyotp
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from collections import defaultdict
import getpass
import logging
from pathlib import Path
import sys
import uvicorn

log = logging.getLogger("rh-server")
logging.basicConfig(level=logging.INFO)
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST_DIR = BASE_DIR / "robinhood-app" / "dist"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Tab → Robinhood span/interval mapping ────────────────────────────────────

TAB_MAP = {
    "1D":  ("day",    "5minute"),
    "1W":  ("week",   "10minute"),
    "1M":  ("month",  "day"),
    "3M":  ("3month", "week"),
    "YTD": ("year",   "week"),
    "ALL": ("5year",  "month"),
}

PORTFOLIO_APPROX_WARNING = (
    "Showing approximate values because authoritative Robinhood portfolio history is unavailable"
)
CONTRIBUTIONS_APPROX_WARNING = (
    "Top movers are approximate and based on current open stock positions"
)

# ─── Login (run once at startup) ──────────────────────────────────────────────

def login():
    print("=== Robinhood API Server ===\n")
    email    = input("Email: ").strip()
    password = getpass.getpass("Password: ")
    mfa_code = None

    use_mfa = input("Use 2FA? (y/n): ").strip().lower()
    if use_mfa == "y":
        secret = getpass.getpass("TOTP secret (blank to enter code manually): ").strip()
        if secret:
            mfa_code = pyotp.TOTP(secret).now()
        else:
            mfa_code = input("Enter 2FA code: ").strip()

    result = r.login(username=email, password=password,
                     mfa_code=mfa_code, store_session=True)
    if not result:
        print("Login failed.")
        sys.exit(1)
    print("\nLogged in. Starting server on http://localhost:8000\n")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _points_to_equity_values(points: list) -> list[float]:
    out = []
    for pt in points:
        if not isinstance(pt, dict):
            continue
        val = (
            pt.get("adjusted_close_equity")
            or pt.get("close_equity")
            or pt.get("adjusted_open_equity")
            or pt.get("open_equity")
        )
        if val is None:
            continue
        try:
            out.append(round(float(val), 2))
        except (TypeError, ValueError):
            continue
    return out


def _equity_history_from_response(hist) -> list[float]:
    """Parse only authoritative portfolio historical payload shape."""
    if not hist:
        return []
    if not isinstance(hist, dict):
        return []
    rows = hist.get("equity_historicals")
    if not isinstance(rows, list) or not rows:
        return []
    vals = _points_to_equity_values(rows)
    return vals if len(vals) >= 2 else []


def _log_history_probe(source: str, span: str, interval: str, hist, parsed: list[float]) -> None:
    hist_type = type(hist).__name__ if hist is not None else "NoneType"
    has_rows = isinstance(hist, dict) and isinstance(hist.get("equity_historicals"), list)
    raw_rows = len(hist.get("equity_historicals", [])) if isinstance(hist, dict) else 0
    parsed_rows = len(parsed)
    log.info(
        "history_source=%s span=%s interval=%s hist_type=%s has_rows=%s raw_rows=%d parsed_rows=%d",
        source,
        span,
        interval,
        hist_type,
        has_rows,
        raw_rows,
        parsed_rows,
    )


def _equity_history(span: str, interval: str) -> list[float]:
    payload = {"interval": interval, "span": span, "bounds": "regular"}

    try:
        purl = r.load_portfolio_profile(info="url")
        if isinstance(purl, str) and "/portfolios/" in purl:
            pid = purl.rstrip("/").split("/")[-1]
            if pid:
                url = f"https://api.robinhood.com/portfolios/historicals/{pid}/"
                hist = request_get(url, "regular", payload)
                series = _equity_history_from_response(hist)
                _log_history_probe("direct_portfolio_historicals", span, interval, hist, series)
                if series:
                    return series
    except Exception:
        log.exception(
            "history_source=direct_portfolio_historicals span=%s interval=%s error=request_failed",
            span,
            interval,
        )

    hist = r.get_historical_portfolio(span=span, interval=interval, bounds="regular")
    series = _equity_history_from_response(hist)
    _log_history_probe("robin_stocks_get_historical_portfolio", span, interval, hist, series)
    if series:
        return series
    log.warning(
        "authoritative_history_unavailable span=%s interval=%s",
        span,
        interval,
    )
    return []


def _load_positions() -> tuple[list[str], dict[str, float]]:
    positions = r.get_open_stock_positions()
    if not positions:
        return [], {}
    symbols: list[str] = []
    shares_map: dict[str, float] = {}
    for pos in positions:
        url = pos.get("instrument")
        if not url:
            continue
        inst = r.get_instrument_by_url(url)
        symbol = inst.get("symbol")
        if symbol:
            symbols.append(symbol)
            shares_map[symbol] = float(pos.get("quantity", 0))
    return symbols, shares_map


def _fetch_stock_historicals(symbols: list[str], span: str, interval: str) -> dict[str, list]:
    if not symbols:
        return {}
    hist_data = r.get_stock_historicals(symbols, span=span, interval=interval, bounds="regular")
    if not hist_data:
        return {}
    by_symbol: dict[str, list] = defaultdict(list)
    for item in hist_data:
        sym = item.get("symbol")
        if sym:
            by_symbol[sym].append(item)
    return by_symbol


def _get_live_prices(symbols: list[str]) -> dict[str, float]:
    prices = r.get_latest_price(symbols)
    out: dict[str, float] = {}
    for sym, price in zip(symbols, prices):
        if price is not None:
            try:
                out[sym] = float(price)
            except (TypeError, ValueError):
                continue
    return out


def _synthesize_equity_history(span: str, interval: str) -> list[float]:
    symbols, shares_map = _load_positions()
    if not symbols:
        return []
    by_symbol = _fetch_stock_historicals(symbols, span, interval)
    if not by_symbol:
        return []
    live_prices = _get_live_prices(symbols)

    max_len = max(len(pts) for pts in by_symbol.values())
    equity_curve: list[float] = []
    for i in range(max_len):
        total = 0.0
        for symbol, pts in by_symbol.items():
            if i < len(pts):
                price = float(pts[i].get("close_price") or pts[i].get("open_price") or 0)
            else:
                price = float(pts[-1].get("close_price") or pts[-1].get("open_price") or 0)
            total += price * shares_map.get(symbol, 0)
        equity_curve.append(round(total, 2))

    live_total = sum(
        live_prices.get(sym, 0) * shares_map.get(sym, 0)
        for sym in by_symbol
    )
    equity_curve.append(round(live_total, 2))
    return equity_curve


def _contributions(span: str, interval: str) -> list[dict]:
    symbols, shares_map = _load_positions()
    if not symbols:
        return []
    by_symbol = _fetch_stock_historicals(symbols, span, interval)
    if not by_symbol:
        return []
    live_prices = _get_live_prices(symbols)

    results = []
    for symbol, pts in by_symbol.items():
        if len(pts) < 2:
            continue
        shares = shares_map.get(symbol, 0)
        start_price = float(pts[0].get("close_price") or pts[0].get("open_price") or 0)
        end_price = live_prices.get(symbol)
        if end_price is None:
            end_price = float(pts[-1].get("close_price") or pts[-1].get("open_price") or 0)
        results.append({
            "s": symbol,
            "c": round((end_price - start_price) * shares, 2),
        })

    results.sort(key=lambda x: abs(x["c"]), reverse=True)
    return results


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/api/portfolio")
def portfolio(tab: str = Query("1D")):
    if tab not in TAB_MAP:
        raise HTTPException(400, f"Unknown tab: {tab}")
    span, interval = TAB_MAP[tab]
    history = _equity_history(span, interval)
    is_approximate = False
    warning = None
    if not history:
        history = _synthesize_equity_history(span, interval)
        if history:
            is_approximate = True
            warning = PORTFOLIO_APPROX_WARNING
            log.warning(
                "using_approximate_portfolio_history span=%s interval=%s",
                span,
                interval,
            )
    if not history:
        raise HTTPException(502, "Authoritative Robinhood portfolio history unavailable")
    return {
        "history":       history,
        "current_value": history[-1],
        "start_value":   history[0],
        "is_approximate": is_approximate,
        "warning": warning,
    }


@app.get("/api/contributions")
def contributions(tab: str = Query("1D")):
    if tab not in TAB_MAP:
        raise HTTPException(400, f"Unknown tab: {tab}")
    span, interval = TAB_MAP[tab]
    contribs = _contributions(span, interval)
    return {
        "contributions": contribs,
        "is_approximate": True,
        "warning": CONTRIBUTIONS_APPROX_WARNING,
    }


@app.get("/api/ping")
def ping():
    return {"ok": True}


if FRONTEND_DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST_DIR), html=True), name="frontend")
else:
    log.warning(
        "frontend_dist_missing path=%s ui_routes_disabled=true",
        FRONTEND_DIST_DIR,
    )


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    login()
    uvicorn.run(app, host="0.0.0.0", port=8000)
