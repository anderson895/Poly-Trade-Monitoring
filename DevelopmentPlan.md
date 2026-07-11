# Development Plan — Polymarket Trading Bot (Desktop)

> Based sa `details.txt` — isang desktop application na nag-a-automate ng **Mean Reversion / "Rubber Band" Strategy** sa daily BTC Up/Down markets ng Polymarket, gamit ang Binance bilang read-only price feed.

---

## 1. Project Overview

| Item | Detail |
|---|---|
| **App Type** | Desktop application (Windows-first) |
| **Purpose** | Automated trading sa Polymarket daily BTC Up/Down contracts |
| **Strategy** | Mean Reversion — bumibili ng murang out-of-the-money shares (15¢–25¢) kapag na-stretch ang BTC price nang 1.5%–2.5% mula sa Daily Open (00:00 UTC), tapos nagbebenta kapag nag-revert ang presyo pabalik sa open |
| **Data Source** | Binance API — **read-only** (BTC price/candles lang) |
| **Trading Venue** | Polymarket CLOB (Central Limit Order Book) |
| **Wallet/Funds** | USDC sa Polygon network |

### UI Flow (mula sa details.txt)
1. Buksan ang desktop app
2. Makikita ang **connection status** (Internet, Binance, Polymarket)
3. Editable settings: **API Key, Private Key, Risk (USDC)**
4. Click **START** para paandarin ang bot
5. Automatic monitoring ng BTC price
6. Kapag na-meet ang entry condition → **BUY**
7. Kapag naabot ang profit target → **SELL**
8. Lahat ng trades at logs → **dashboard**
9. Click **STOP** para ihinto

---

## 2. Tech Stack ⭐

### **Python + PySide6 (Qt)**

Ito ang pinaka-praktikal para sa project na ito. Bakit:

| Component | Technology | Rationale |
|---|---|---|
| **Language** | Python 3.11+ | Ang **official Polymarket client (`py-clob-client`)** ay Python — first-class support, laging updated |
| **Polymarket** | `py-clob-client` | Official CLOB client: order placement, order book, positions |
| **Binance feed** | `websockets` / `python-binance` | Real-time BTC price via WebSocket stream (`btcusdt@kline_1m`) — mas mabilis at walang rate-limit issues vs REST polling |
| **Desktop UI** | **PySide6 (Qt for Python)** | Native-feel desktop UI, official Qt bindings (LGPL — libre for commercial), may `QThread` para hindi mag-freeze ang UI habang tumatakbo ang bot |
| **Async engine** | `asyncio` + `qasync` | Sabay na WebSocket streams + UI events sa iisang event loop |
| **Local storage** | SQLite (`sqlite3` built-in) | Trade history, logs, settings — walang external DB na kailangan |
| **Secrets** | `keyring` (Windows Credential Manager) | Para HINDI naka-plaintext ang Private Key sa disk |
| **Charts (optional)** | `pyqtgraph` | Mabilis na real-time BTC price chart sa dashboard |
| **Packaging** | PyInstaller | Single `.exe` para madaling i-distribute |

**Pros:** Isang language lang end-to-end, official Polymarket SDK, pinakamabilis i-develop, malaking ecosystem para sa trading/quant (pandas, numpy kung kailangan ng indicators).
**Cons:** Medyo malaki ang packaged `.exe` (~80–150 MB), hindi kasing-ganda ng web-based UI out of the box.

> **Bakit ito ang stack:** Para sa trading bot, ang pinaka-importante ay ang **reliability ng exchange integration**, hindi ang gandang UI. Ang Python ang may pinaka-mature na Polymarket tooling (`py-clob-client` ay official at actively maintained), at isang developer lang kayang mag-ship nito end-to-end.

---

## 3. Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Desktop App (PySide6)               │
│                                                      │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────┐  │
│  │ Dashboard  │  │  Settings   │  │ Trades/Logs  │  │
│  │  status,   │  │ (API keys,  │  │   viewer     │  │
│  │  price,    │  │  risk USDC) │  │              │  │
│  │  START/STOP│  └─────────────┘  └──────────────┘  │
│  └─────┬──────┘                                      │
│        │ signals/slots (Qt)                          │
│  ┌─────▼──────────────────────────────────────────┐  │
│  │           Bot Engine (asyncio, QThread)        │  │
│  │                                                │  │
│  │  ┌──────────┐  ┌───────────┐  ┌────────────┐  │  │
│  │  │ Binance  │→ │ Strategy  │→ │ Polymarket │  │  │
│  │  │ WS feed  │  │ (Mean     │  │ Executor   │  │  │
│  │  │ (BTC/USDT│  │ Reversion)│  │ (py-clob-  │  │  │
│  │  │  klines) │  │           │  │  client)   │  │  │
│  │  └──────────┘  └───────────┘  └────────────┘  │  │
│  │         │             │              │        │  │
│  │  ┌──────▼─────────────▼──────────────▼─────┐  │  │
│  │  │        SQLite (trades, logs, state)      │  │  │
│  │  └──────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────┘  │
│  Secrets: Windows Credential Manager (keyring)       │
└──────────────────────────────────────────────────────┘
```

### Core Modules

| Module | Responsibility |
|---|---|
| `feed/binance.py` | WebSocket connection sa Binance, BTC price stream, daily open tracking (00:00 UTC), reconnect logic |
| `strategy/mean_reversion.py` | Entry/exit rules (see §4), pure logic — walang I/O para madaling i-test |
| `execution/polymarket.py` | Market discovery (daily BTC Up/Down), order placement/cancel, position tracking via `py-clob-client` |
| `core/engine.py` | Orchestrator — pinagdudugtong ang feed → strategy → execution; START/STOP state machine |
| `core/risk.py` | Position sizing (Risk USDC cap), max trades per day, kill-switch |
| `storage/db.py` | SQLite: trades, logs, settings |
| `ui/` | PySide6 windows: dashboard, settings dialog, trade log table |

---

## 4. Strategy Logic — AS IMPLEMENTED (v1.1.0)

> Source of truth: `src/strategy/mean_reversion.py` (pure rules),
> `src/strategy/filters.py` (death-trap vetoes), `src/core/engine.py`
> (monitoring loop). Lahat ng kondisyon dito ay may unit tests.

### Monitoring loop

Ang bot ay sumusuri **sa BAWAT price tick** (~1/segundo mula sa Binance
WebSocket) habang RUNNING. Ang sinusuri ay depende kung may hawak na
position o wala:

```
price tick → stretch = (price − period_open) / period_open × 100
   │
   ├─ WALANG position → ENTRY CHECKLIST (lahat dapat TRUE bago bumili)
   └─ MAY position    → EXIT CHECKLIST (unang tumama ang mananaig)
```

### ENTRY CHECKLIST (BUY) — sunud-sunod, lahat dapat pumasa

| # | Kondisyon | Default (Daily) | Saan naka-code |
|---|---|---|---|
| 1 | Bot state = RUNNING (naka-START) | — | `engine._handle_price` |
| 2 | May sapat na data (period open + share price) | — | `evaluate_entry` |
| 3 | **Hindi Economic Data Day** (manual toggle sa Settings, auto-expire kinabukasan) | naka-off | `engine._evaluate_strategy` |
| 4 | **Wala pang trade sa kasalukuyang market period** (1 trade kada period; nagre-reset bawat bagong period) | max 1 | `engine._reset_daily_counter` |
| 5 | **Nasa entry window**: lumipas na ang 16.7% ng period pero hindi pa 50% | 4h–12h mula 00:00 UTC | `evaluate_entry` |
| 6 | **Stretch sa loob ng band**: \|stretch\| ≥ minimum AT ≤ maximum (lampas sa max = momentum day / death trap → SKIP) | 1.5%–2.5% | `evaluate_entry` |
| 7 | **OTM share price sa 15¢–25¢** — Paper: estimated mula sa stretch (`0.50 − 0.15×\|stretch\|/scale`); Live: totoong **best ASK** ng target side mula sa CLOB order book (refresh kada 5s) | 0.15–0.25 | `evaluate_entry` |
| 8 | **Volume HINDI escalating**: recent 3h avg volume < 2.0× ng prior 20h baseline (institutional momentum veto) | 2.0× | `filters.is_volume_escalating` |
| 9 | **Coinbase premium HINDI exploding**: \|Coinbase − Binance\| < 0.15% sa direksyon ng stretch (aggressive US spot buying veto); fail-open kung walang Coinbase data | ±0.15% | `filters.is_premium_exploding` |

**Kapag pumasa lahat** → BUY:
- **Side**: DOWN kung pumped (+stretch), UP kung dumped (−stretch) — mean reversion
- **Size**: `Risk USDC ÷ share price` shares (default $200 → ~1,000 shares sa 20¢)
- Paper: instant simulated fill; Live: **limit order** sa best ask via `py-clob-client`
- Naka-record sa SQLite + naka-persist ang position (para sa restart resume)

### EXIT CHECKLIST (SELL) — bawat tick habang may position; unang tumama ang mananaig

| # | Kondisyon | Default | Resulta |
|---|---|---|---|
| 1 | **Profit target**: share price ≥ entry × (1 + target) | +100% (20¢ → 40¢) | SELL, kita |
| 2 | **Stop loss**: share price ≤ entry × (1 − stop) | −50% (20¢ → 10¢) | SELL, cut loss |
| 3 | **End-of-period force exit**: lumipas na ang 97.9% ng period — HINDING-HINDI hinihintay ang settlement | 23.5h sa daily | SELL sa kahit anong presyo |

- Paper: modeled price mula sa stretch; Live: **best BID** ng hawak na side
- Kapag nag-fail ang live order → ERROR log + pulang alert banner (hindi tahimik)

### Per-Timeframe Scaling (v1.1.0 — Market Timeframe setting)

Ang mga kondisyon sa itaas ay DAILY-calibrated; awtomatikong nagsi-scale
sa napiling Polymarket market (`scale_config_for_timeframe`): mga oras =
parehong **fraction ng period**, stretch = **sqrt-of-time** volatility:

| Timeframe | Entry window | Stretch band | Force exit | Bagong market kada |
|---|---|---|---|---|
| **Daily** | 4h–12h | 1.50%–2.50% | 23.5h | araw (00:00 UTC) |
| **4 Hours** | 40–120 min | 0.61%–1.02% | 235 min | 4 oras |
| **1 Hour** | 10–30 min | 0.31%–0.51% | 58.8 min | oras |
| **15 Minutes** | 2.5–7.5 min | 0.15%–0.26% | 14.7 min | 15 min (:00/:15/:30/:45) |

- Profit target, stop loss, at 15¢–25¢ share gate: HINDI nagbabago
  (magkapareho ang share-price dynamics ng lahat ng markets)
- Sa Live mode, awtomatikong lumilipat sa bagong market bawat period
  (rollover sa `_live_price_loop`); ginagarantiya ng force exit na flat
  bago mag-rollover
- Ang "1 trade" allowance ay **kada period** (hindi kada araw)

---

## 5. Development Phases

### Phase 1 — Foundation ✅ DONE (2026-07-11)
- [x] Project scaffold: Python venv, PySide6, project structure
- [x] Binance WebSocket feed: real-time BTC price + daily open (00:00 UTC) tracking
- [x] Connection status indicators (Internet / Binance / Polymarket)
- [x] Settings UI: API Key, Private Key, Risk USDC — stored via `keyring`
- [x] SQLite schema: trades, logs, settings

> ✅ **Phase 1 finding — RESOLVED (2026-07-11):** Ang Polymarket endpoints ay dating hindi ma-reach dahil sa **ISP DNS poisoning** (bina-blackhole ng ISP DNS ang `*.polymarket.com`). Naresolba via **in-app DoH resolver** (`src/core/netdns.py`) — DNS-over-HTTPS (Cloudflare/Google) para sa Polymarket hosts lamang, system DNS pa rin ang iba. Kumpirmado sa smoke tests: lahat ng 3 endpoints (clob, gamma-api, polymarket.com) ay `200 OK` na. *(Paalala pa rin: i-verify ang legality/compliance sa inyong jurisdiction bago mag-live.)*

### Phase 2 — Strategy & Paper Trading ✅ DONE (2026-07-11)
- [x] Mean reversion strategy module (pure functions + 18 unit tests, all passing)
- [x] **Paper trading mode** — buong strategy loop pero simulated fills lang ⚠️ *critical: i-validate muna ang strategy bago gumamit ng totoong pera*
- [x] Dashboard: live BTC price, % from daily open, strategy state, START/STOP, PAPER MODE badge
- [x] Trade log table + log viewer sa UI (Trades/Logs tabs)

> **Phase 2 notes:**
> - Dahil blocked ang Polymarket order book, ang paper mode ay gumagamit ng **estimated share pricing** mula sa BTC stretch: `price = clamp(0.50 − 0.15×|stretch%|, 0.03, 0.50)` — calibrated sa reference examples (2% stretch ≈ 20¢). Papalitan ito ng totoong CLOB prices sa Phase 3.
> - Default profit target ay **+100%** (hindi +150%) — sa pricing model, ang full reversion mula 1.9% stretch ay ~+130% lang, kaya hindi kailanman maaabot ang +150% nang maaga. Configurable ito sa `StrategyConfig`.

### Phase 3 — Live Execution ⚠️ CODE DONE, MOCKED TESTING LANG (2026-07-11)
- [x] Polymarket integration: daily BTC Up/Down market discovery (Gamma API), order book reading
- [x] Order placement via `py-clob-client` (limit orders — huwag market orders sa illiquid books)
- [x] Position tracking + exit logic (profit target sell-back sa order book)
- [x] Risk controls: max position = Risk USDC, max trades/day, kill-switch sa STOP
- [x] Trading Mode selector sa Settings (Paper/Live), auto-fallback sa Paper kapag hindi makakonekta
- [x] Live USDC balance display + error logging sa `data/app.log` (may full tracebacks)
- [x] ~~I-verify ang Gamma API slug pattern~~ ✅ VERIFIED (2026-07-11) — ang tamang slug ay **`bitcoin-up-or-down-on-{month}-{day}-{year}`** (may year suffix; ang lumang pattern na walang year ay retained bilang fallback). Live-tested: nahanap ang "Bitcoin Up or Down on July 11?" + tama ang UP/DOWN token mapping. May discovery scripts sa `tests/verify_gamma_slug.py` at `tests/discover_gamma_*.py`
- [x] ~~signature_type hardcoded~~ ✅ DONE (2026-07-11) — "Polymarket Sign-up Method" dropdown na sa Settings (Email/Magic = 1, MetaMask = 2); wala nang code change kahit anong wallet ang user
- [ ] **HINDI PA NA-VE-VERIFY ang order placement na may totoong pera** — mag-test gamit ang napakaliit na USDC (~$5–10). *Kailangan ng user ang Private Key + Funder Address + USDC. Tingnan ang step.txt (end-user guide).*

### Phase 4 — Hardening & Packaging (Week 4–5)
- [x] ~~Reconnect/resume logic~~ ✅ DONE (2026-07-11) — WebSocket auto-reconnect (dati na); **position resume sa app restart**: naka-persist ang open position sa SQLite, nire-restore sa START kung same UTC day + same mode; stale (ibang araw) = discarded na may WARN; naiwang LIVE position habang PAPER mode = malakas na ERROR alert; 8 unit tests (`tests/test_resume.py`)
- [x] ~~Death-trap filter: volume escalation detection~~ ✅ DONE (2026-07-11) — hourly Binance volumes, recent 3h avg vs prior 20h baseline, blocks entry kapag ≥2× (configurable sa Settings); 7 unit tests
- [x] ~~Death-trap filter: economic calendar toggle~~ ✅ DONE (2026-07-11) — manual checkbox sa Settings, naka-store ang petsa kaya auto-expire kinabukasan
- [x] ~~Death-trap filter: Coinbase premium check~~ ✅ DONE (2026-07-11) — Coinbase spot vs Binance kada 60s, direction-aware veto sa ±0.15% (configurable); fail-open kung walang Coinbase data
- [x] ~~Error handling + alerting sa UI~~ ✅ DONE (2026-07-11) — dismissible red alert banner sa main window tuwing ERROR (failed BUY/SELL orders ay naka-wrap na sa try/except at nagla-log ng ERROR); full tracebacks pa rin sa `data/app.log`
- [x] ~~PyInstaller packaging~~ ✅ DONE (2026-07-11) — **onedir** `dist/PolyTradePro/` (mas mabilis magbukas kaysa onefile), build gamit ang **venv313/Python 3.13**; ang `data/` ay sa tabi ng exe via `src/core/paths.py`; buong build command at gotchas sa README
- [ ] End-to-end testing sa maliit na real USDC amount — *kailangan ng user ang keys + USDC (may creds na sa Credential Manager; 0 pa ang balance)*

### Phase 5 — Released + Post-Release Features ✅ (2026-07-11)

**Releases (GitHub):**
- **v1.0.0** — unang release: buong Paper/Live bot, dark UI, packaged exe
- **v1.1.0** — **Market Timeframe selector** (Daily/4H/1H/15M) na may
  auto-scaled strategy at live market rollover (tingnan ang Section 4)

**Mga feature na naidagdag lampas sa orihinal na plano:**
- [x] Trading-app style chart: line + candlestick w/ volume (finplot),
      Binance-style Time filters (1s→All, YTD), hover crosshair, price
      badge, auto-follow, 2h history prefill, live chart kahit STOPPED
- [x] Buong English na propesyonal na UI
- [x] Collapsible sidebar (icon-only, naka-persist)
- [x] Credential verification sa Save Settings + agad na balance card
      update nang hindi nag-i-START
- [x] Cash-style Paper Balance: bumababa pagka-BUY, bumabalik ang
      proceeds + PnL pagka-SELL
- [x] Mode-aware Settings form; Reset = strategy values lang
- [x] Live balance refresh loop (60s / 10s retry)
- [x] E2E paper buy→sell simulation test; **74 unit tests total**

---

## 6. Security Notes ⚠️

1. **🚨 URGENT: May naka-expose na Binance API key sa `details.txt` (line 22).** Kahit read-only pa ito, **i-revoke/regenerate agad** sa Binance dashboard dahil nakasulat na ito sa plaintext file. Huwag na huwag ilalagay sa code o sa anumang text file ang keys.
2. **Private Key handling** — ito ang susi sa USDC funds. Dapat:
   - Naka-store sa **Windows Credential Manager** (via `keyring`), hindi sa file/DB
   - Hindi lumalabas sa logs kahit kailan
   - Masked sa UI (`••••••••`)
3. **Binance key = read-only permissions lang** — walang trading/withdrawal permission na i-e-enable.
4. **Risk cap enforcement sa code level** — hindi lang UI validation; ang engine mismo ang dapat mag-reject ng orders na lampas sa Risk USDC.
5. Kung gagawing git repo: `details.txt` at anumang secrets file → `.gitignore` agad.

---

## 7. Key Risks & Open Questions

| Risk / Question | Notes |
|---|---|
| **Polymarket liquidity** | Daily BTC markets ay may manipis na order book minsan — limit orders + slippage checks required |
| **Strategy validation** | Ang "over 90% of candles have wicks" claim ay dapat i-backtest muna gamit historical data bago mag-live |
| **Market discovery** | Nagbabago araw-araw ang daily BTC Up/Down market IDs — kailangan ng automatic discovery via Polymarket Gamma API |
| **Geo-restrictions** | Polymarket may jurisdiction restrictions — responsibility ng user na i-verify ang compliance |
| **Partial fills** | Paano ang handling kung partial lang ang fill ng entry/exit order? (Phase 3 design decision) |
| **Multiple positions?** | Isang position lang ba per day, o pwedeng mag-re-enter? (I-clarify sa Phase 2) |

---

## 8. Suggested Project Structure

```
PolyTradeMonitoring/
├── src/
│   ├── main.py                 # App entry point
│   ├── core/
│   │   ├── engine.py           # Bot orchestrator / state machine
│   │   └── risk.py             # Position sizing, limits, kill-switch
│   ├── feed/
│   │   └── binance.py          # BTC price WebSocket feed
│   ├── strategy/
│   │   └── mean_reversion.py   # Entry/exit logic (pure, testable)
│   ├── execution/
│   │   ├── polymarket.py       # py-clob-client wrapper
│   │   └── paper.py            # Paper-trading executor
│   ├── storage/
│   │   └── db.py               # SQLite access
│   └── ui/
│       ├── dashboard.py        # Main window
│       ├── settings.py         # API keys / risk settings dialog
│       └── trades_view.py      # Trade history + logs
├── tests/
│   └── test_mean_reversion.py
├── requirements.txt
└── DevelopmentPlan.md          # (this file)
```
