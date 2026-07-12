# PolyTrade Pro — Polymarket Trading Bot

A Windows desktop trading bot for Polymarket's **daily BTC Up/Down markets**, powered by a **Mean Reversion ("Rubber Band")** strategy. Binance provides the read-only BTC price feed; trades execute on Polymarket's on-chain order book (Polygon network).

Supports **Paper mode** (fully simulated, no real money) and **Live mode** (real USDC on Polymarket).

---

## Features

- 📈 **Live BTC chart** — line and candlestick views with volume bars, Binance-style time filters (1s · 15m · 1H · 4H · 1D · 1W · YTD · All), hover crosshair with exact price/time, auto-follow, and 2-hour history prefill on launch
- 🤖 **Automated strategy** — 1.5%–2.5% stretch entry inside the 4–12h window of the market period, 15¢–25¢ share price gate, profit target / stop loss / end-of-period exits, one trade per market period. The daily market is anchored to **12:00 PM ET** (its real settlement anchor), not 00:00 UTC
- ⏱️ **Market Timeframes** — Daily / 4H / 1H / 15M Polymarket markets, with strategy timings and stretch thresholds auto-scaled per timeframe and automatic market rollover each period
- 🛡️ **"Death trap" filters** — volume escalation veto, Coinbase premium veto, and a manual Economic Data Day block
- 📊 **Full dashboard** — connection status (Internet / Binance / Polymarket), bot status, live balance, trades table, statistics (win rate, PnL), and logs
- 🔐 **Secure secrets** — private keys stored in Windows Credential Manager, never in files; credential verification on save
- 🔁 **Resilience** — WebSocket auto-reconnect, position resume after restart, automatic fallback to Paper mode when Live setup fails, in-app DoH resolver that bypasses ISP DNS poisoning of Polymarket domains
- 🖥️ **Polished UI** — dark theme, collapsible sidebar, error alert banner, pointer cursors, mode-aware settings form

---

## Technology Stack

### Core
| Technology | Purpose |
|---|---|
| **Python 3.13** | Application language (single venv for dev and build) |
| **PySide6 (Qt 6)** | Desktop UI framework (official Qt for Python) |
| **qasync** | Bridges the Qt event loop with `asyncio` so WebSockets and UI run on one loop |
| **SQLite** (built-in `sqlite3`) | Local storage for trades, logs, and settings |

### Charting
| Technology | Purpose |
|---|---|
| **pyqtgraph** | High-performance real-time line chart (price, crosshair, price badge) |
| **finplot** | Candlestick + volume chart (lazy-loaded when the Candles view is selected) |
| **pandas / NumPy** | OHLCV data handling for the candlestick chart |
| **QtAwesome** | Font Awesome icons throughout the UI |

### Networking & Data
| Technology | Purpose |
|---|---|
| **websockets** | Binance combined stream (`miniTicker` + `kline_1m`) for live prices and candles |
| **httpx** | Async REST calls (Binance klines/history, Polymarket Gamma API, connection checks) |
| **truststore** | TLS verification via the native Windows certificate store |
| **Custom DoH resolver** | DNS-over-HTTPS (Cloudflare/Google) scoped to `*.polymarket.com` — defeats ISP DNS poisoning by patching `socket.getaddrinfo` |

### Web3 / Blockchain
| Technology | Purpose |
|---|---|
| **py-clob-client-v2** | Official Polymarket CLOB V2 client — order signing and placement (the V2 exchange, live since Apr 2026, rejects the legacy client). Supports Magic proxy, MetaMask, and Deposit Wallet accounts |
| **Polygon network** | The Ethereum L2 where Polymarket markets and USDC live |
| **USDC** | Settlement currency (ERC-20 stablecoin) |
| **Cryptographic order signing** | Orders are signed with the user's wallet private key (EIP-712 style); API credentials are derived from the key — no username/password |
| **Polymarket Gamma API** | BTC Up/Down market discovery for every timeframe (daily markets are named by their noon-ET settlement date; 15m/4h by UTC period start; 1h by ET hour) |

### Security & Packaging
| Technology | Purpose |
|---|---|
| **keyring** (Windows Credential Manager) | Encrypted storage for the private key and funder address |
| **PyInstaller** | Packaging into a distributable Windows app (`dist/PolyTradePro/`) |
| **Pillow** (dev-only) | Icon asset generation (`tests/make_icon.py`, `tests/make_arrows.py`) |

---

## Getting Started

### Option A — Download the release (end users)
1. Download the latest `PolyTradePro-vX.Y.Z.zip` from the [Releases page](https://github.com/anderson895/Poly-Trade-Monitoring/releases)
2. Extract the folder and run `PolyTradePro.exe` inside
3. The app starts in **Paper mode** (no real money). See `step.txt` for the Live-mode setup guide

### Option B — Run from source (developers)
```powershell
python -m venv venv   # Python 3.13
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m src.main    # or double-click run.bat
```

Requirements: Windows 10/11, internet connection.

---

## Testing Guide

### STEP 1 — Unit tests (offline, ~2 seconds)

```powershell
.\venv\Scripts\python.exe -m pytest tests -v
```

**Expected: 84 passed.** Coverage:

| Test file | What it verifies |
|---|---|
| `test_mean_reversion.py` | Entry/exit rules: entry window (4–12h into the period), stretch band, share price gate, profit target, stop loss, end-of-period exit |
| `test_timeframes.py` | Per-timeframe scaling, period anchors (daily = noon ET, DST-aware), market slug builders |
| `test_filters.py` | Death-trap guards: volume escalation and Coinbase premium vetoes |
| `test_polymarket.py` | Market discovery (slug patterns) and live executor logic (CLOB V2) |
| `test_netdns.py` | The DoH resolver (ISP DNS-poisoning bypass) |
| `test_resume.py` | Position resume after restart (restore / stale-period / mode-mismatch rules) |
| `test_paper_e2e.py` | **Full engine buy→sell simulation** — pump → BUY at ~20¢ → reversion → SELL at profit target, plus stop-loss and trade-limit cycles |

### STEP 2 — Smoke tests (require internet)

```powershell
.\venv\Scripts\python.exe -m tests.smoke_phase1      # DB + Binance REST/WS + status endpoints
.\venv\Scripts\python.exe -m tests.smoke_volumes     # live hourly-volume filter check
.\venv\Scripts\python.exe -m tests.check_polymarket  # Polymarket endpoint reachability
.\venv\Scripts\python.exe -m tests.verify_live_creds # credential check (read-only, no orders)
```

### STEP 3 — Open the app and verify the UI

1. The window opens maximized with the robot icon
2. Within ~15 seconds all three status cards turn green: **Internet / Binance (BTC) / Polymarket**
3. **Bot Status: STOPPED**, and the chart is already full (2-hour history prefill) and moving — the chart is live even before START
4. Past trades and logs persist across restarts (SQLite)

### STEP 4 — Settings

1. **Risk Per Trade** defaults to 200 USDC
2. In **Live** mode the form shows Private Key / Funder Address / Wallet Type; in **Paper** mode those are hidden
3. Saving triggers an automatic **credential verification** with the result (and live balance) shown inline, and the dashboard balance card updates immediately — no START needed
4. **Reset** restores strategy defaults only; it does not touch Trading Mode or Wallet Type

### STEP 5 — Paper run

1. Select **Paper** mode → Save → **START BOT**
2. Verify: status RUNNING, uptime counting, strategy status line updating (e.g., `WATCHING — stretch +0.12% < 1.5% minimum`)
3. **STOP BOT** returns to STOPPED; the chart keeps streaming

> The bot trades rarely by design — entries require a genuine stretch from
> the period strike inside the entry window (on Daily: ~1.7–2.3% within
> 4–12h after noon ET; scaled down on shorter timeframes). A day with no
> trades is normal, not a bug — the Recent Logs show exactly which
> condition is not met (`Watching: stretch +0.05% < 0.153% minimum`).

### STEP 6 — Buy/sell logic check (any time, no waiting)

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_paper_e2e.py -v
```

Simulates a full trading day through the real engine: entry gating, a BUY at ~20¢, holding, a SELL at the +100% profit target with correct PnL, a stop-loss cycle, and the one-trade-per-day limit. **Expected: 3 passed.**

### STEP 7 — Live mode (REAL money — start small)

1. Settings → **Live**, paste the Polymarket **Private Key** and **Funder Address**, pick the **Wallet Type**, set **Risk to 5–10 USDC** for the first run → Save
   - **Accounts created after April 2026** are Deposit Wallet accounts: pick *"Deposit Wallet (accounts after Apr 2026)"* and use the **"Address (For API use only)"** shown in your polymarket.com settings as the Funder Address. The account must have completed at least one trade on the website (this deploys the wallet and its approvals).
   - Older accounts: *Email/Google (Magic)* or *MetaMask* with the classic proxy address.
2. The inline check should report the credentials as valid along with your USDC balance — if it shows **0.00** while you have funds, the Funder Address or Wallet Type is wrong
3. **START BOT** → expect `LIVE mode ready — market: Bitcoin Up or Down ...` and your real balance on the dashboard
4. If anything fails, the bot automatically falls back to Paper mode with a red alert — it will never spend money silently
5. After the first live trade, cross-check the order and PnL against polymarket.com → Portfolio

> **Optional plumbing check before waiting for a real setup:** `.\venv\Scripts\python.exe -m tests.live_e2e_order` places a tiny (~$3) real BUY and sells it back immediately (with a confirmation prompt) to verify the whole order path — expected cost is just the spread (~$0.05–0.30).

---

## Building the Executable (PyInstaller)

**Build with the Python 3.13 venv (`venv`)** — do not use Python 3.10.0: it has a CPython bug (bpo-45757) that crashes PyInstaller's scanner on pandas/Pillow:

```powershell
.\venv\Scripts\python.exe -m PyInstaller --noconfirm --onedir --windowed --name PolyTradePro --paths . --icon icon.ico --add-data "icon_square.png;." --add-data "assets;assets" --exclude-module PyQt6 --collect-submodules finplot src\main.py
```

First-time setup of the build venv:
```powershell
& "C:\Program Files\Python313\python.exe" -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
.\venv\Scripts\python.exe -m pip uninstall -y PyQt6 PyQt6-Qt6 PyQt6_sip
```

Output: **`dist/PolyTradePro/`** (~200 MB). Delete `dist/PolyTradePro/data` (test artifacts) before zipping the folder for distribution. The app creates its own `data/` (database + logs) next to the exe on first run.

### Build gotchas (all required)
- **`--collect-submodules finplot`** — finplot registers a pandas plotting backend (`finplot.pdplot`) via a dynamic import that PyInstaller cannot see; without this flag the Candles view crashes in the packaged app
- **PyQt6 conflict** — installing finplot pulls in PyQt6; uninstall it from the build venv and keep `--exclude-module PyQt6` (PyInstaller refuses two Qt bindings, and QtAwesome may bind to the wrong one at runtime)
- **Do not build with the Python 3.10.0 venv** — CPython bug bpo-45757 causes an `IndexError` in PyInstaller's module scanner
- **Explorer shows a stale icon after a rebuild?** That's the Windows icon cache — run `ie4uinit.exe -show`, rename the exe, or restart Explorer

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Polymarket card shows Disconnected | Some ISPs DNS-poison `*.polymarket.com`. The app ships a built-in DoH resolver (`src/core/netdns.py`) that bypasses this. Run `tests.check_polymarket` to inspect reachability |
| App won't open | Run from a terminal to see the error: `.\venv\Scripts\python.exe -m src.main` |
| Runtime errors | Check **`data\app.log`** — every error is logged there with a full traceback (attach it when reporting issues) |
| Bot is RUNNING but never trades | Read the strategy status line under the chart — it states exactly what it's waiting for (entry window, stretch, share price, or an active death-trap veto) |
| `BLOCKED — volume escalating…` | Intentional: the volume death-trap guard is refusing momentum days |
| Balance shows `…` in Live mode | Transient network hiccup; the balance loop retries every 10s and refreshes every 60s |

---

## Project Structure

```
src/
  main.py            # Entry point (Qt + asyncio via qasync, DoH install)
  core/              # Bot engine, connection monitor, secrets, DoH resolver, paths, logging
  feed/              # Binance WebSocket/REST feed, Coinbase feed (premium filter)
  strategy/          # Mean reversion rules + death-trap filters (pure, fully unit-tested)
  execution/         # PaperExecutor (simulated), LiveExecutor (Polymarket CLOB), position resume
  storage/           # SQLite (trades, logs, settings, open position)
  ui/                # PySide6 UI: dashboard, charts, settings, trades, logs, stats, theme
tests/               # 61 unit tests + smoke tests + verification utilities
assets/              # UI icon assets (spinbox +/−, dropdown chevron)
data/                # SQLite DB + app.log (auto-created, gitignored)
run.bat              # Dev launcher
```

---

## Disclaimer

This software places real-money trades on Polymarket when Live mode is enabled. Use Paper mode until you have validated the strategy yourself. Trading involves risk of loss; nothing here is financial advice. Verifying that Polymarket is legal in your jurisdiction is your responsibility.
