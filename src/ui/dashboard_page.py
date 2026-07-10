"""Dashboard page: status cards, BTC chart with bands, recent logs."""
from __future__ import annotations

import datetime as dt

import qtawesome as qta
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QColor

from src.storage.db import Database
from src.ui import theme
from src.ui.chart import PriceChart
from src.ui.widgets import Card, StatCard, StatusCard

DEFAULT_PAPER_START = 1000.0

LEVEL_COLORS = {
    "INFO": theme.GREEN,
    "TRADE": theme.ACCENT,
    "WARN": theme.AMBER,
    "ERROR": theme.RED,
}


class DashboardPage(QWidget):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self._db = db
        self._live_mode = False

        # ---- Status cards row -------------------------------------------
        self.cards = {
            "internet": StatusCard("fa6s.globe", "Internet", "#3b82f6"),
            "binance": StatusCard("fa6b.bitcoin", "Binance (BTC)", "#f7931a"),
            "polymarket": StatusCard("fa6s.cube", "Polymarket", "#8b5cf6"),
        }
        self.bot_card = StatCard("Bot Status", "STOPPED")
        self.bot_card.set_value("STOPPED", theme.RED)
        self.balance_card = StatCard("Paper Balance", "—", "Simulated (walang totoong pera)")

        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        for card in self.cards.values():
            cards_row.addWidget(card, stretch=1)
        cards_row.addWidget(self.bot_card, stretch=1)
        cards_row.addWidget(self.balance_card, stretch=1)

        # ---- Chart panel --------------------------------------------------
        chart_title = QLabel("BTC Price (USDT)")
        chart_title.setProperty("accent", True)
        self._price_label = QLabel("$ —")
        self._price_label.setProperty("h1", True)
        self._pct_label = QLabel("")
        self._pct_label.setStyleSheet(f"color: {theme.MUTED}; font-size: 15px")

        price_row = QHBoxLayout()
        price_row.addWidget(self._price_label)
        price_row.addWidget(self._pct_label)
        price_row.addStretch()

        self.chart = PriceChart()

        self._strategy_label = QLabel("Strategy: idle (press START BOT)")
        self._strategy_label.setProperty("muted", True)
        self._strategy_label.setWordWrap(True)

        chart_panel = Card()
        chart_col = QVBoxLayout(chart_panel)
        chart_col.setContentsMargins(14, 12, 14, 12)
        chart_col.addWidget(chart_title)
        chart_col.addLayout(price_row)
        chart_col.addWidget(self.chart, stretch=1)
        chart_col.addWidget(self._strategy_label)

        # ---- Recent logs panel --------------------------------------------
        logs_title = QLabel("Recent Logs")
        logs_title.setProperty("accent", True)
        clear_btn = QPushButton(" Clear")
        clear_btn.setIcon(qta.icon("fa6s.trash-can", color=theme.MUTED))
        clear_btn.clicked.connect(self._clear_logs)

        logs_head = QHBoxLayout()
        logs_head.addWidget(logs_title)
        logs_head.addStretch()
        logs_head.addWidget(clear_btn)

        self._log_list = QListWidget()
        self._log_list.setMaximumHeight(150)

        logs_panel = Card()
        logs_col = QVBoxLayout(logs_panel)
        logs_col.setContentsMargins(14, 12, 14, 12)
        logs_col.addLayout(logs_head)
        logs_col.addWidget(self._log_list)

        # ---- Layout --------------------------------------------------------
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.addLayout(cards_row)
        root.addWidget(chart_panel, stretch=1)
        root.addWidget(logs_panel)

        self._load_recent_logs()
        self.refresh_balance()

    # ------------------------------------------------------------------ slots

    def update_price(self, price: float) -> None:
        self._price_label.setText(f"${price:,.2f}")
        self.chart.add_point(price)

    def update_stretch(self, pct: float) -> None:
        color = theme.GREEN if pct >= 0 else theme.RED
        self._pct_label.setText(f"{pct:+.2f}%")
        self._pct_label.setStyleSheet(f"color: {color}; font-size: 15px; font-weight: bold")

    def set_daily_open(self, open_price: float) -> None:
        entry_pct = float(self._db.get_setting("min_stretch_pct", 1.5))
        self.chart.set_bands(open_price, entry_pct)

    def set_connection(self, name: str, up: bool) -> None:
        key = "binance" if name == "binance_ws" else name
        if key in self.cards:
            self.cards[key].set_state(up)

    def set_bot_state(self, state: str) -> None:
        running = state == "RUNNING"
        self.bot_card.set_value(state, theme.GREEN if running else theme.RED)

    def set_strategy_status(self, text: str) -> None:
        self._strategy_label.setText(f"Strategy: {text}")

    def refresh_balance(self) -> None:
        if self._live_mode:
            return  # sa live mode, ang engine ang nagpapadala ng totoong balance
        start = float(self._db.get_setting("paper_start_usdc", DEFAULT_PAPER_START))
        balance = start + self._db.total_pnl()
        color = theme.GREEN if balance >= start else theme.RED
        self.balance_card.set_value(f"{balance:,.2f} USDC", color)

    def set_mode(self, mode: str) -> None:
        self._live_mode = mode == "LIVE"
        if self._live_mode:
            self.balance_card.set_title("Account Balance (LIVE)")
            self.balance_card.set_sub("Totoong USDC sa Polymarket")
            self.balance_card.set_value("…", theme.AMBER)
        else:
            self.balance_card.set_title("Paper Balance")
            self.balance_card.set_sub("Simulated (walang totoong pera)")
            self.refresh_balance()

    def set_live_balance(self, balance: float) -> None:
        self.balance_card.set_value(f"{balance:,.2f} USDC", theme.GREEN)

    def add_log(self, level: str, message: str) -> None:
        ts = dt.datetime.now().strftime("%H:%M:%S")
        self._insert_log_item(ts, level, message, prepend=True)

    # ---------------------------------------------------------------- helpers

    def _load_recent_logs(self) -> None:
        for row in self._db.recent_logs(limit=50):
            self._insert_log_item(row["ts"][11:19], row["level"], row["message"])

    def _insert_log_item(
        self, ts: str, level: str, message: str, prepend: bool = False
    ) -> None:
        item = QListWidgetItem(f"●  [{ts}]  {message}")
        item.setForeground(QColor(LEVEL_COLORS.get(level, theme.TEXT)))
        if prepend:
            self._log_list.insertItem(0, item)
        else:
            self._log_list.addItem(item)

    def _clear_logs(self) -> None:
        self._db.clear_logs()
        self._log_list.clear()
