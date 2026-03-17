"""
services/exchange_rate_service.py
Fetches exchange rates from open.er-api.com (free, no key required).
Caches to SQLite and falls back to cache on API failure.
"""
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional

import requests

from database import db_handler
from models.cost_config import ExchangeRate
from utils.logger import get_logger

log = get_logger(__name__)

# API base URL (free tier — 1500 req/month, ~50/day)
_API_URL = "https://open.er-api.com/v6/latest/USD"

# Supported currencies and their approximate VND rates (offline fallback)
_FALLBACK_RATES_VND: Dict[str, float] = {
    "USD": 25_400.0,
    "JPY":  170.0,
    "CNY": 3_500.0,
    "EUR": 27_500.0,
    "GBP": 32_000.0,
    "KRW":   18.5,
    "THB":   710.0,
}

# Cache TTL
_CACHE_TTL_MINUTES = 5

# Thread lock for thread-safe rate updates
_lock = threading.Lock()

# In-memory cache: {currency -> ExchangeRate}
_mem_cache: Dict[str, ExchangeRate] = {}


def _is_stale(rate: ExchangeRate) -> bool:
    try:
        updated = datetime.fromisoformat(rate.updated_at)
        return datetime.now() - updated > timedelta(minutes=_CACHE_TTL_MINUTES)
    except Exception:
        return True


def _fetch_usd_rates() -> Optional[Dict[str, float]]:
    """Fetch all rates relative to USD from API. Returns {currency: rate_vs_usd}."""
    try:
        log.info("Fetching exchange rates from API…")
        resp = requests.get(_API_URL, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        if data.get("result") == "success":
            log.info("Exchange rates fetched OK — base %s", data.get("base_code"))
            return data["rates"]
    except requests.RequestException as e:
        log.warning("Exchange rate API error: %s — using cache/fallback", e)
    return None


def _usd_rate_to_vnd(rates_vs_usd: Dict[str, float], currency: str) -> Optional[float]:
    """Convert a rate-vs-USD entry to VND-per-currency."""
    # rates_vs_usd = {USD: 1, VND: 25200, JPY: 149, ...}
    vnd_per_usd = rates_vs_usd.get("VND")
    rate_per_usd = rates_vs_usd.get(currency)
    if vnd_per_usd and rate_per_usd and rate_per_usd != 0:
        return vnd_per_usd / rate_per_usd
    return None


def get_rate(currency: str, spread_pct: float = 2.0) -> ExchangeRate:
    """Return ExchangeRate for the given currency, using cache / API / fallback."""
    with _lock:
        # 1. Memory cache
        mem = _mem_cache.get(currency)
        if mem and not _is_stale(mem):
            return mem

        # 2. Try DB cache
        db_row = db_handler.get_cached_rate(currency)
        if db_row:
            cached_rate = ExchangeRate(
                currency=currency,
                market_rate=db_row["market_rate"],
                bank_rate=db_row["bank_rate"],
                spread_pct=db_row["spread_pct"],
                updated_at=db_row["updated_at"],
            )
            if not _is_stale(cached_rate):
                _mem_cache[currency] = cached_rate
                return cached_rate

        # 3. Try live API
        api_rates = _fetch_usd_rates()
        if api_rates:
            market = _usd_rate_to_vnd(api_rates, currency)
            if market:
                rate = ExchangeRate.from_market(currency, market, spread_pct)
                _mem_cache[currency] = rate
                db_handler.save_rate(currency, market, rate.bank_rate, spread_pct)
                return rate

        # 4. Absolute fallback
        market = _FALLBACK_RATES_VND.get(currency, 0.0)
        log.warning("Using hardcoded fallback rate for %s: %s", currency, market)
        rate = ExchangeRate.from_market(currency, market, spread_pct)
        _mem_cache[currency] = rate
        return rate


def refresh_all(currencies: list[str], spread_pct: float = 2.0) -> Dict[str, ExchangeRate]:
    """Refresh rates for a list of currencies. Returns dict of results."""
    api_rates = _fetch_usd_rates()
    result: Dict[str, ExchangeRate] = {}
    for cur in currencies:
        if api_rates:
            market = _usd_rate_to_vnd(api_rates, cur)
            if market:
                rate = ExchangeRate.from_market(cur, market, spread_pct)
                with _lock:
                    _mem_cache[cur] = rate
                db_handler.save_rate(cur, market, rate.bank_rate, spread_pct)
                result[cur] = rate
                continue
        # Fallback
        result[cur] = get_rate(cur, spread_pct)
    return result
