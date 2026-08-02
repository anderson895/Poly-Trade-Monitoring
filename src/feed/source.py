"""Pagpili ng market data source: Binance o Coinbase.

Hinaharangan ng Binance ang mga US IP (HTTP 451), kaya sa US-based VPS ay
hindi kumokonekta ang feed at hindi gumagana ang bot. Dito pinipili kung
aling feed ang gagamitin, at sa "auto" ay sinusubukan muna ang Binance
bago bumalik sa Coinbase.

MAHALAGA: ang Polymarket daily BTC market ay nagse-settle base sa Binance
BTCUSDT. Ang Coinbase BTC-USD ay karaniwang may kaunting spread dito, kaya
bahagyang iba ang "Price to Beat" kapag Coinbase ang source. Binance pa rin
ang tama kung naabot; ang Coinbase ay para sa kapag hindi talaga kaya.
"""
from __future__ import annotations

import logging
from typing import Union

import httpx

from src.feed.binance import BinanceFeed
from src.feed.coinbase_market import CoinbaseMarketFeed

filelog = logging.getLogger("polytrade.feed.source")

BINANCE_PING_URL = "https://api.binance.com/api/v3/ping"
PROBE_TIMEOUT = 8.0

SOURCES = ("auto", "binance", "coinbase")
SOURCE_LABELS = {"binance": "Binance", "coinbase": "Coinbase"}

MarketFeed = Union[BinanceFeed, CoinbaseMarketFeed]


async def binance_reachable() -> bool:
    """Naaabot ba ang Binance REST mula sa host na ito?

    Ang geo-block ay HTTP 451, pero ibang deployment ay nagbabalik ng 403
    o basta nagti-timeout — lahat ay itinuturing na hindi maabot.
    """
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as client:
            resp = await client.get(BINANCE_PING_URL)
    except Exception as e:
        filelog.info("Binance probe failed (%s: %s) — Coinbase ang gagamitin",
                     type(e).__name__, e)
        return False
    if resp.status_code == 200:
        return True
    filelog.warning(
        "Binance probe returned HTTP %s%s — Coinbase ang gagamitin",
        resp.status_code,
        " (geo-blocked na region)" if resp.status_code == 451 else "",
    )
    return False


async def resolve_source(setting: str) -> str:
    """Isalin ang setting ("auto"/"binance"/"coinbase") sa aktwal na source."""
    source = (setting or "auto").lower()
    if source not in SOURCES:
        source = "auto"
    if source != "auto":
        return source
    return "binance" if await binance_reachable() else "coinbase"


def make_feed(source: str, **callbacks) -> MarketFeed:
    """Buuin ang feed para sa naresolbang source. Pareho ang callbacks."""
    if source == "coinbase":
        return CoinbaseMarketFeed(**callbacks)
    return BinanceFeed(**callbacks)
