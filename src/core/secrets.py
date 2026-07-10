"""Secure secrets storage via Windows Credential Manager (keyring).

Ang mga sensitive credentials ay dito naka-store, hindi sa file o DB:
- Binance API key (read-only)
- Polymarket private key
- Polymarket funder/proxy address (hindi ganoon ka-sensitive pero isama na)
"""
from __future__ import annotations

from typing import Optional

import keyring

SERVICE = "PolyTradeBot"

KEY_BINANCE_API = "binance_api_key"
KEY_PM_PRIVATE = "polymarket_private_key"
KEY_PM_FUNDER = "polymarket_funder_address"

ALL_KEYS = (KEY_BINANCE_API, KEY_PM_PRIVATE, KEY_PM_FUNDER)


def get_secret(name: str) -> Optional[str]:
    return keyring.get_password(SERVICE, name)


def set_secret(name: str, value: str) -> None:
    if value:
        keyring.set_password(SERVICE, name, value)
    else:
        delete_secret(name)


def delete_secret(name: str) -> None:
    try:
        keyring.delete_password(SERVICE, name)
    except keyring.errors.PasswordDeleteError:
        pass  # wala namang naka-store


def mask(value: Optional[str]) -> str:
    """Pang-display sa UI: huwag kailanman ipakita ang buong secret."""
    if not value:
        return "(not set)"
    if len(value) <= 8:
        return "••••••••"
    return value[:4] + "••••••••" + value[-4:]
