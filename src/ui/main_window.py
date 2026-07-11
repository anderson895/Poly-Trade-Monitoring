"""PolyTrade Pro main window — sidebar + pages + bottom bar (per mockup)."""
from __future__ import annotations

import asyncio
import datetime as dt

import qtawesome as qta
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QToolButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.engine import BotEngine
from src.storage.db import Database
from src.ui import theme
from src.ui.alert_banner import AlertBanner
from src.ui.dashboard_page import DashboardPage
from src.ui.settings_page import SettingsPage
from src.ui.widgets import Card

APP_VERSION = "1.0.0"


# ---------------------------------------------------------------- sub-pages


class TradesPage(QWidget):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self._db = db
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Time", "Market", "Side", "Action", "Price", "Size (USDC)", "PnL"]
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        root = QVBoxLayout(self)
        title = QLabel("Trades")
        title.setProperty("accent", True)
        root.addWidget(title)
        root.addWidget(self.table, stretch=1)
        self.reload()

    def reload(self) -> None:
        self.table.setRowCount(0)
        for row in self._db.recent_trades(limit=200):
            r = self.table.rowCount()
            self.table.insertRow(r)
            pnl = row["pnl"]
            values = [
                row["ts"][11:19], row["market"], row["side"], row["action"],
                f"{row['price']:.2f}", f"{row['size']:.2f}",
                "" if pnl is None else f"{pnl:+.2f}",
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                if col == 6 and pnl is not None:
                    item.setForeground(QColor(theme.GREEN if pnl >= 0 else theme.RED))
                self.table.setItem(r, col, item)


class LogsPage(QWidget):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self._db = db
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Time", "Level", "Message"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        root = QVBoxLayout(self)
        title = QLabel("Logs")
        title.setProperty("accent", True)
        root.addWidget(title)
        root.addWidget(self.table, stretch=1)

        for row in self._db.recent_logs(limit=500):
            self._add_row(row["ts"][11:19], row["level"], row["message"])

    def add_log(self, level: str, message: str) -> None:
        self._add_row(dt.datetime.now().strftime("%H:%M:%S"), level, message, prepend=True)

    def _add_row(self, ts: str, level: str, message: str, prepend: bool = False) -> None:
        r = 0 if prepend else self.table.rowCount()
        self.table.insertRow(r)
        for col, val in enumerate([ts, level, message]):
            self.table.setItem(r, col, QTableWidgetItem(val))


class StatsPage(QWidget):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self._db = db
        title = QLabel("Statistics")
        title.setProperty("accent", True)

        self._labels: dict[str, QLabel] = {}
        panel = Card()
        col = QVBoxLayout(panel)
        col.setContentsMargins(16, 14, 16, 14)
        for key in ("Closed Trades", "Wins", "Losses", "Win Rate", "Total PnL"):
            lab = QLabel(f"{key}: —")
            lab.setStyleSheet("font-size: 15px")
            self._labels[key] = lab
            col.addWidget(lab)

        root = QVBoxLayout(self)
        root.addWidget(title)
        root.addWidget(panel)
        root.addStretch()
        self.refresh()

    def refresh(self) -> None:
        stats = self._db.trade_stats()
        pnl = self._db.total_pnl()
        closed = stats["closed"]
        win_rate = (stats["wins"] / closed * 100) if closed else 0.0
        self._labels["Closed Trades"].setText(f"Closed Trades: {closed}")
        self._labels["Wins"].setText(f"Wins: {stats['wins']}")
        self._labels["Losses"].setText(f"Losses: {stats['losses']}")
        self._labels["Win Rate"].setText(f"Win Rate: {win_rate:.0f}%")
        color = theme.GREEN if pnl >= 0 else theme.RED
        self._labels["Total PnL"].setText(f"Total PnL: {pnl:+,.2f} USDC")
        self._labels["Total PnL"].setStyleSheet(f"font-size: 15px; color: {color}")


class AboutPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        title = QLabel("PolyTrade Pro")
        title.setProperty("h1", True)
        body = QLabel(
            f"Polymarket Trading Bot — v{APP_VERSION}\n\n"
            "Strategy: Mean Reversion (\"Rubber Band\") on daily BTC Up/Down markets.\n"
            "Data: Binance (read-only BTC price feed).\n\n"
            "Paper mode simulates every trade with no real money.\n"
            "Switch to Live mode in Settings to trade with real USDC on Polymarket."
        )
        body.setProperty("muted", True)
        root = QVBoxLayout(self)
        root.addWidget(title)
        root.addWidget(body)
        root.addStretch()


# --------------------------------------------------------------- bottom bar


class BottomBar(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setProperty("card", True)

        strat_title = QLabel("Strategy")
        strat_title.setProperty("muted", True)
        strat_value = QLabel("Mean Reversion")
        strat_value.setStyleSheet("font-weight: bold")
        strat_col = QVBoxLayout()
        strat_col.setSpacing(1)
        strat_col.addWidget(strat_title)
        strat_col.addWidget(strat_value)

        market_title = QLabel("Market")
        market_title.setProperty("muted", True)
        self.market_label = QLabel("BTC (Binance) → Polymarket [PAPER]")
        self.market_label.setStyleSheet("font-weight: bold")
        market_col = QVBoxLayout()
        market_col.setSpacing(1)
        market_col.addWidget(market_title)
        market_col.addWidget(self.market_label)

        self.start_btn = QPushButton("  START BOT")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.setIcon(qta.icon("fa6s.play", color="white"))
        self.stop_btn = QPushButton("  STOP BOT")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setIcon(qta.icon("fa6s.stop", color=theme.RED))
        self.stop_btn.setEnabled(False)

        up_title = QLabel("Uptime")
        up_title.setProperty("muted", True)
        self.uptime_label = QLabel("00:00:00")
        self.uptime_label.setStyleSheet("font-weight: bold; font-size: 15px")
        up_col = QVBoxLayout()
        up_col.setSpacing(1)
        up_col.addWidget(up_title)
        up_col.addWidget(self.uptime_label)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 10, 16, 10)
        row.addLayout(strat_col)
        row.addSpacing(24)
        row.addLayout(market_col)
        row.addStretch()
        row.addWidget(self.start_btn)
        row.addSpacing(8)
        row.addWidget(self.stop_btn)
        row.addStretch()
        row.addLayout(up_col)


# -------------------------------------------------------------- main window


class MainWindow(QMainWindow):
    PAGES = [
        ("fa6s.house", "Dashboard"),
        ("fa6s.gear", "Settings"),
        ("fa6s.file-lines", "Logs"),
        ("fa6s.chart-line", "Trades"),
        ("fa6s.chart-pie", "Statistics"),
        ("fa6s.circle-info", "About"),
    ]

    def __init__(self, engine: BotEngine, db: Database) -> None:
        super().__init__()
        self._engine = engine
        self._db = db
        self.setWindowTitle("PolyTrade Pro — Polymarket Trading Bot")
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(theme.STYLESHEET)

        # ---- Sidebar (collapsible) ---------------------------------------
        self._brand_icon = QLabel()
        self._brand_icon.setPixmap(
            qta.icon("fa6s.cube", color=theme.ACCENT).pixmap(28, 28)
        )
        self._brand = QLabel("PolyTrade Pro")
        self._brand.setProperty("h2", True)

        self._sidebar_btn = QToolButton()
        self._sidebar_btn.setIcon(qta.icon("fa6s.bars", color=theme.MUTED))
        self._sidebar_btn.setIconSize(QSize(18, 18))
        self._sidebar_btn.setToolTip("Toggle sidebar")
        self._sidebar_btn.clicked.connect(self._toggle_sidebar)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(8)
        brand_row.addWidget(self._brand_icon)
        brand_row.addWidget(self._brand, stretch=1)
        brand_row.addWidget(self._sidebar_btn)

        self._brand_sub = QLabel("Polymarket Trading Bot")
        self._brand_sub.setProperty("muted", True)

        self._nav = QListWidget()
        self._nav.setObjectName("sidebar")
        self._nav.setIconSize(QSize(18, 18))
        # Walang horizontal scrollbar kailanman — ito ang gumugulo sa
        # collapsed mode (nag-i-scroll at nagki-clip ang icons)
        self._nav.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        for icon_name, label in self.PAGES:
            icon = qta.icon(icon_name, color=theme.MUTED, color_selected="#c7d2fe")
            item = QListWidgetItem(icon, label)
            item.setToolTip(label)  # kapaki-pakinabang kapag collapsed
            self._nav.addItem(item)
        self._nav.setCurrentRow(0)
        self._nav.setFixedWidth(190)

        self._version = QLabel(f"v{APP_VERSION}")
        self._version.setProperty("muted", True)

        # Naka-QWidget container ang sidebar para deterministic ang lapad —
        # kapag nag-collapse, lumiliit ito at ang BODY ang nagse-stretch
        self._sidebar = QWidget()
        side_col = QVBoxLayout(self._sidebar)
        side_col.setContentsMargins(14, 14, 0, 14)
        side_col.addLayout(brand_row)
        side_col.addWidget(self._brand_sub)
        side_col.addSpacing(14)
        side_col.addWidget(self._nav, stretch=1)
        side_col.addWidget(self._version)
        self._sidebar.setFixedWidth(204)

        # I-restore ang huling sidebar state (collapsed/expanded)
        self._sidebar_collapsed = False
        if str(db.get_setting("sidebar_collapsed", "0")) == "1":
            self._sidebar_collapsed = True
            self._apply_sidebar(True)

        # ---- Pages -------------------------------------------------------
        self.dash = DashboardPage(db)
        self.settings = SettingsPage(db)
        self.logs = LogsPage(db)
        self.trades = TradesPage(db)
        self.stats = StatsPage(db)

        self._stack = QStackedWidget()
        for page in (self.dash, self.settings, self.logs, self.trades, self.stats, AboutPage()):
            self._stack.addWidget(page)
        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)

        # ---- Bottom bar ----------------------------------------------------
        self.bottom = BottomBar()
        self.bottom.start_btn.clicked.connect(self._on_start)
        self.bottom.stop_btn.clicked.connect(self._on_stop)

        # ---- Alert banner (errors/failed orders) ---------------------------
        self.alert = AlertBanner()

        # ---- Layout --------------------------------------------------------
        content = QVBoxLayout()
        content.setContentsMargins(10, 14, 14, 14)
        content.addWidget(self.alert)
        content.addWidget(self._stack, stretch=1)
        content.addWidget(self.bottom)

        root = QHBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._sidebar)
        root.addLayout(content, stretch=1)

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)

        # Pointer (hand) cursor sa LAHAT ng clickable elements — walang
        # QSS "cursor" property ang Qt kaya programmatic ito
        self._apply_pointer_cursors(container)

        # ---- Uptime timer ----------------------------------------------------
        self._uptime_secs = 0
        self._uptime_timer = QTimer(self)
        self._uptime_timer.setInterval(1000)
        self._uptime_timer.timeout.connect(self._tick_uptime)

        # ---- Engine wiring -----------------------------------------------------
        engine.priceUpdated.connect(self.dash.update_price)
        engine.historyLoaded.connect(self.dash.load_history)
        engine.klineUpdated.connect(self.dash.update_candle)
        engine.rangeHistoryLoaded.connect(self.dash.load_range_history)
        self.dash.rangeRequested.connect(engine.fetch_range_history)
        # Pag-Save sa Settings: agad mag-update ang balance card + bottom
        # bar ayon sa napiling mode — hindi na hinihintay ang START
        self.settings.modeSaved.connect(self._on_mode)
        self.settings.liveBalanceChecked.connect(self.dash.set_live_balance)
        engine.stretchUpdated.connect(self.dash.update_stretch)
        engine.connectionChanged.connect(self.dash.set_connection)
        engine.stateChanged.connect(self._on_state)
        engine.strategyStatus.connect(self.dash.set_strategy_status)
        engine.modeChanged.connect(self._on_mode)
        engine.liveBalance.connect(self.dash.set_live_balance)
        engine.tradeExecuted.connect(self._on_trade)
        engine.logAdded.connect(self.dash.add_log)
        engine.logAdded.connect(self.logs.add_log)
        engine.logAdded.connect(self._on_log_alert)

    def _apply_pointer_cursors(self, container: QWidget) -> None:
        """Hand cursor sa bawat button, dropdown, checkbox, at nav item."""
        from PySide6.QtWidgets import QCheckBox, QComboBox

        for cls in (QPushButton, QToolButton, QComboBox, QCheckBox):
            for widget in container.findChildren(cls):
                widget.setCursor(Qt.CursorShape.PointingHandCursor)
        self._nav.viewport().setCursor(Qt.CursorShape.PointingHandCursor)

    # ---------------------------------------------------------------- sidebar

    def _toggle_sidebar(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        self._apply_sidebar(self._sidebar_collapsed)
        self._db.set_setting(
            "sidebar_collapsed", "1" if self._sidebar_collapsed else "0"
        )

    def _apply_sidebar(self, collapsed: bool) -> None:
        """Collapsed = icon-only (may tooltips); expanded = buo.

        Ang buong sidebar container ang nagbabago ng lapad — kaya ang
        body/content ang awtomatikong nagse-stretch sa natirang espasyo.
        """
        for widget in (self._brand_icon, self._brand, self._brand_sub,
                       self._version):
            widget.setVisible(not collapsed)
        for i, (_icon, label) in enumerate(self.PAGES):
            self._nav.item(i).setText("" if collapsed else label)
        self._nav.setFixedWidth(48 if collapsed else 190)
        self._sidebar.setFixedWidth(62 if collapsed else 204)
        # I-apply ang collapsed QSS variant (mas maliit na item padding)
        self._nav.setProperty("collapsed", collapsed)
        self._nav.style().unpolish(self._nav)
        self._nav.style().polish(self._nav)

    # ------------------------------------------------------------------ slots

    def _on_start(self) -> None:
        self._engine.start()

    def _on_stop(self) -> None:
        asyncio.create_task(self._engine.stop())

    def _on_state(self, state: str) -> None:
        running = state == "RUNNING"
        self.dash.set_bot_state(state)
        self.bottom.start_btn.setEnabled(not running)
        self.bottom.stop_btn.setEnabled(running)
        if running:
            self._uptime_secs = 0
            self._uptime_timer.start()
        else:
            self._uptime_timer.stop()

    def _on_mode(self, mode: str) -> None:
        self.dash.set_mode(mode)
        self.bottom.market_label.setText(f"BTC (Binance) → Polymarket [{mode}]")

    def _on_log_alert(self, level: str, message: str) -> None:
        if level == "ERROR":
            self.alert.show_error(message)

    def _on_trade(self) -> None:
        self.trades.reload()
        self.stats.refresh()
        self.dash.refresh_balance()

    def _tick_uptime(self) -> None:
        self._uptime_secs += 1
        h, rem = divmod(self._uptime_secs, 3600)
        m, s = divmod(rem, 60)
        self.bottom.uptime_label.setText(f"{h:02d}:{m:02d}:{s:02d}")
