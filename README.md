# PolyTrade Pro — Polymarket Trading Bot

Desktop trading bot para sa daily BTC Up/Down markets ng Polymarket, gamit ang
**Mean Reversion / "Rubber Band"** strategy. Binance (read-only) ang BTC price
feed. May **PAPER mode** (simulated, walang totoong pera) at **LIVE mode**
(totoong USDC sa Polymarket).

---

## Requirements

- Windows 10/11
- Python 3.10 (naka-setup na sa `venv\`)
- Internet connection

Kung kailangan i-install ulit ang dependencies:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## Paano I-test — Step by Step

### STEP 1: Patakbuhin ang Automated Unit Tests (offline, walang internet na kailangan)

Ito ang pinakamabilis na check na tama ang strategy logic:

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_mean_reversion.py tests\test_filters.py tests\test_polymarket.py tests\test_netdns.py tests\test_resume.py -v
```

**Expected:** lahat PASS (57 tests). Sinasaklaw nito:

| Test file | Ano ang tine-test |
|---|---|
| `test_mean_reversion.py` | Entry/exit rules: entry window (4–12h UTC), stretch band (1.5%–2.5%), share price range (15¢–25¢), profit target, stop loss, EOD exit |
| `test_filters.py` | Death trap guards: volume escalation veto at Coinbase premium veto |
| `test_polymarket.py` | Polymarket market parsing at live executor logic |
| `test_netdns.py` | In-app DoH resolver (bypass sa ISP DNS blocking) |
| `test_resume.py` | Position resume sa app restart (restore/stale/mode-mismatch rules) |

### STEP 2: Smoke Tests (kailangan ng internet)

Chine-check nito na maabot ang mga totoong endpoints:

```powershell
# DB + Binance REST + status endpoints + WebSocket stream
.\venv\Scripts\python.exe -m tests.smoke_phase1

# Hourly volume fetch + escalation check sa totoong Binance data
.\venv\Scripts\python.exe -m tests.smoke_volumes

# Alin sa mga Polymarket endpoints ang reachable sa network mo
.\venv\Scripts\python.exe -m tests.check_polymarket
```

**Expected:** mga `[OK]` lines. Kung may `[FAIL]` sa polymarket, tingnan ang
Troubleshooting sa baba.

### STEP 3: Buksan ang App at I-check ang UI

Double-click ang **`run.bat`** (o patakbuhin: `.\venv\Scripts\python.exe -m src.main`)

I-verify ang mga sumusunod pagbukas:

1. ✅ Bubukas nang maximized ang window na "PolyTrade Pro"
2. ✅ Sa loob ng ~15 segundo, magiging **berde/Connected** ang 3 status cards:
   **Internet**, **Binance (BTC)**, **Polymarket**
3. ✅ **Bot Status: STOPPED** (pula) — hindi pa tumatakbo ang bot
4. ✅ **Paper Balance** ay may laman (default: 1,000 USDC + accumulated PnL)
5. ✅ Makikita ang mga **dating trades** sa Trades page at **logs** sa Logs page
   (persisted sa SQLite kahit isara mo ang app)

### STEP 4: I-test ang Settings

1. Pumunta sa **Settings** (sidebar)
2. I-verify na **200 USDC** ang "Risk Per Trade"
3. Subukang i-type ang Polymarket Private Key → click
   **Save Settings** → dapat lumabas ang "Settings saved ✓"
4. Isara at buksan ulit ang app → dapat naka-save pa rin ang values
   (secrets ay nasa Windows Credential Manager, hindi sa files)
5. I-click ang **👁** icon → dapat magpakita/magtago ang secret text

### STEP 5: I-test ang Bot sa PAPER Mode (walang totoong pera)

1. Sa Settings, siguraduhing **Paper** ang Trading Mode → Save
2. I-click ang **▶ START BOT** sa baba
3. I-verify:
   - ✅ **Bot Status: RUNNING** (berde)
   - ✅ Gumagalaw ang **BTC price** at chart real-time
   - ✅ Umaandar ang **Uptime** timer
   - ✅ May log na *"Bot STARTED [PAPER MODE]"*
   - ✅ Makikita ang **Daily open (00:00 UTC)** sa logs at bands sa chart
   - ✅ Sa ilalim ng chart, makikita ang strategy status, hal.:
     - `WATCHING — stretch +0.45% < 1.5% minimum` (normal kapag maliit ang galaw)
     - `WATCHING — waiting for entry window (4h-12h UTC)` (kapag maaga pa)
4. I-click ang **⏹ STOP BOT** → dapat bumalik sa STOPPED at may log na
   *"Bot STOPPED"*

> **Tandaan:** Sa totoong kondisyon lang bibili ang bot (stretch 1.5%–2.5%
> mula sa daily open, sa loob ng 4–12h UTC window, share price 15¢–25¢).
> Karaniwang **walang trade sa isang araw** kung walang malaking galaw ang BTC
> — normal ito, hindi bug.

### STEP 6 (Optional): I-test ang Buy/Sell Logic ng Bot (Paper)

**Paraan A — Automated E2E test (anumang oras, ~2 segundo):**

```powershell
.\venv\Scripts\python.exe -m pytest tests\test_paper_e2e.py -v
```

Sine-simulate nito ang buong mean-reversion na araw sa TOTOONG engine code:
- BTC pumped +2.0% sa loob ng entry window → **bibili** ng DOWN sa ~20¢ ($200)
- Bumalik ang presyo (reversion) → +105% ang share → **magbebenta** (profit)
- Kasama rin: stop-loss cycle, 1-trade-per-day limit, at DB recording

**Expected:** 3 passed. Kung pasado ito, gumagana ang buy→sell logic.

**Paraan B — Totoong paper validation (hintayin ang tamang araw):**

Iwanan lang ang bot na naka-START sa Paper mode. Sa araw na ang BTC ay
gumalaw ng **~1.7%–2.3%** mula sa daily open sa loob ng **12:00 PM–8:00 PM
PH time**, kusang bibili ang bot — makikita mo sa Trades page, logs, at
Statistics. Ito ang tunay na validation ng strategy bago mag-live.

> **Bakit hindi puwedeng "pilitin" via Settings:** may share-price gate ang
> strategy (15¢–25¢ ang OTM share) na nakatali sa laki ng stretch — kaya
> kahit ibaba mo ang Entry Stretch Band, hindi papasok ang bot hangga't
> walang tunay na ~1.7%+ na galaw. Sadya ito (disiplina ng strategy);
> gamitin ang Paraan A para sa mabilis na logic check.

### STEP 7 (Optional, TOTOONG PERA): I-test ang LIVE Mode

⚠️ **Babala:** Gagamit ito ng totoong USDC sa Polymarket account mo.
Mag-test muna nang matagal sa Paper mode.

1. Sa Settings:
   - Trading Mode → **Live**
   - Ilagay ang **Polymarket Private Key** at **Funder / Proxy Address**
   - Magsimula sa **maliit na Risk** (hal. 5–10 USDC) para sa unang live test
   - Save Settings
2. START BOT
3. I-verify:
   - ✅ Log na *"LIVE mode ready — market: Bitcoin Up or Down..."*
   - ✅ Magiging **"Account Balance (LIVE)"** ang balance card na nagpapakita
     ng totoong USDC mo
   - ✅ `[LIVE]` tag sa bottom bar
4. Kung pumalya ang koneksyon, **awtomatikong babalik sa PAPER mode**
   (may log na "Live setup failed ... falling back to PAPER mode") —
   hindi ito magba-buy nang hindi mo alam

---

## Checklist ng Buong Test (quick reference)

```
[ ] STEP 1: pytest — 57/57 passed
[ ] STEP 2: smoke tests — lahat [OK]
[ ] STEP 3: app opens; 3 status cards Connected; dating trades/logs visible
[ ] STEP 4: settings save + persist; secrets masked; 200 USDC risk default
[ ] STEP 5: START/STOP; price + chart gumagalaw; strategy status nag-a-update
[ ] STEP 6: (optional) forced paper trade — buy, sell, PnL, stats OK
[ ] STEP 7: (optional) live mode connect + totoong balance
```

---

## Bagong Features (2026-07-11)

- **Position resume** — kapag na-restart ang app habang may open position,
  awtomatiko itong nire-restore sa pag-START (kung same UTC day at same mode).
  Kapag stale na (ibang araw), dini-discard na may WARN log. Kapag may naiwang
  LIVE position pero Paper mode ka na, may malakas na ERROR alert.
- **Error alert banner** — pulang banner sa taas ng window tuwing may ERROR
  (failed BUY/SELL order, live setup failure). Dismissible via ✕.
- **Single .exe packaging** — tingnan sa baba.

## Pag-package (PyInstaller)

### Recommended: folder build (onedir) — MABILIS magbukas (~2s)

**Gamitin ang `venv313` (Python 3.13) sa pag-build** — ang lumang venv ay
Python 3.10.0 na may CPython bug (bpo-45757) na nagpapa-crash sa PyInstaller
kapag siniscan ang pandas/Pillow:

```powershell
.\venv313\Scripts\python.exe -m PyInstaller --noconfirm --onedir --windowed --name PolyTradePro --paths . --icon icon.ico --add-data "icon_square.png;." --add-data "assets;assets" --exclude-module PyQt6 src\main.py
```

Kung wala pa ang `venv313`:
```powershell
& "C:\Program Files\Python313\python.exe" -m venv venv313
.\venv313\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
.\venv313\Scripts\python.exe -m pip uninstall -y PyQt6 PyQt6-Qt6 PyQt6_sip
```

- Output: **`dist\PolyTradePro\`** folder (~177 MB) — i-zip ang BUONG folder
  para i-distribute; ang user ay magpapatakbo ng `PolyTradePro.exe` sa loob.
- Gagawa ito ng sariling `data\` folder (database + logs) sa loob ng
  app folder. Ang secrets ay nasa Windows Credential Manager — hindi kasama.

### Alternative: single .exe (onefile) — HUWAG gamitin kung ayaw ng mabagal

```powershell
.\venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --name PolyTradePro --paths . --icon icon.ico --add-data "icon_square.png;." --add-data "assets;assets" --exclude-module PIL src\main.py
```

- Isang file lang (~72 MB) PERO **10–60 segundo bago magbukas** kada launch
  (self-extraction + antivirus scan) — kaya hindi ito ang recommended.

### Mga paalala sa build

- **⚠️ PyQt6 conflict**: ang pag-install ng finplot ay nagdadala ng PyQt6 —
  i-uninstall ito sa build venv (`pip uninstall PyQt6 PyQt6-Qt6 PyQt6_sip`)
  at panatilihin ang `--exclude-module PyQt6`; hindi sinusuportahan ng
  PyInstaller ang dalawang Qt bindings, at nagba-bind pa ang qtawesome sa
  maling Qt kapag naiwan ito.
- **⚠️ HUWAG mag-build gamit ang lumang venv (Python 3.10.0)** — may CPython
  bug (bpo-45757) na nagpapa-IndexError sa PyInstaller scanner kapag
  siniscan ang pandas/Pillow.
- **Icon sa Explorer mukhang luma/walang icon pagkatapos ng rebuild?**
  Icon cache lang iyon ng Windows — patakbuhin ang `ie4uinit.exe -show`,
  o i-rename ang exe, o i-restart ang Explorer.

## Troubleshooting

| Problema | Solusyon |
|---|---|
| **Polymarket card = Disconnected** | Ang ilang ISP (hal. PLDT/Converge) ay bina-block ang polymarket.com via DNS poisoning. May built-in DoH resolver ang app (`src/core/netdns.py`) na dapat mag-bypass dito. Patakbuhin ang `.\venv\Scripts\python.exe -m tests.check_polymarket` para makita kung alin ang reachable. |
| **Hindi bumubukas ang app** | Patakbuhin sa terminal para makita ang error: `.\venv\Scripts\python.exe -m src.main` |
| **May error habang tumatakbo** | Tingnan ang **`data\app.log`** — lahat ng errors ay naka-log doon (pwedeng i-attach bilang error report) |
| **Walang trade kahit RUNNING** | Normal — basahin ang strategy status sa ilalim ng chart; sasabihin nito kung bakit naghihintay (entry window, stretch, share price, o na-block ng death trap filter) |
| **"BLOCKED — volume escalating..."** | Death trap guard ito, sinasadya — hindi papasok ang bot sa momentum days |

---

## Project Structure

```
src/
  main.py            # Entry point
  core/              # Engine, connection monitor, secrets, DoH resolver, logging
  feed/              # Binance WebSocket feed (read-only), Coinbase (premium filter)
  strategy/          # Mean reversion logic + death trap filters (pure, walang I/O)
  execution/         # PaperExecutor (simulated) at LiveExecutor (Polymarket CLOB)
  storage/           # SQLite (trades, logs, settings)
  ui/                # PySide6 UI (dashboard, settings, trades, logs, stats)
tests/               # Unit tests + smoke tests
data/                # SQLite DB + app.log (auto-created)
run.bat              # Double-click launcher
```
