"""Settings page — Bot Settings panel (per mockup).

Secrets -> Windows Credential Manager (keyring); numbers -> SQLite.
May 👁 toggle ang secret fields; blank = keep current value.
"""
from __future__ import annotations

import datetime as dt

import qtawesome as qta
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core import secrets
from src.storage.db import Database
from src.ui import theme
from src.ui.widgets import Card

DEFAULTS = {
    "risk_usdc": 20.0,
    "min_stretch_pct": 1.5,
    "max_stretch_pct": 2.5,
    "profit_target_pct": 100.0,
    "volume_spike_mult": 2.0,
    "premium_threshold_pct": 0.15,
    "paper_start_usdc": 1000.0,
}


def _secret_field(current_key: str) -> tuple[QHBoxLayout, QLineEdit]:
    edit = QLineEdit()
    edit.setEchoMode(QLineEdit.EchoMode.Password)
    edit.setPlaceholderText(f"Currently: {secrets.mask(secrets.get_secret(current_key))}")

    eye = QToolButton()
    eye.setIcon(qta.icon("fa6s.eye", color=theme.MUTED))
    eye.setCheckable(True)

    def _toggle(show: bool) -> None:
        edit.setEchoMode(
            QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password
        )
        eye.setIcon(
            qta.icon("fa6s.eye-slash" if show else "fa6s.eye", color=theme.MUTED)
        )

    eye.toggled.connect(_toggle)
    row = QHBoxLayout()
    row.addWidget(edit)
    row.addWidget(eye)
    return row, edit


def _spin(value: float, suffix: str, maximum: float = 100_000.0) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setRange(0.01, maximum)
    box.setDecimals(2)
    box.setSuffix(f" {suffix}")
    box.setValue(value)
    return box


class SettingsPage(QWidget):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self._db = db

        title = QLabel("Bot Settings")
        title.setProperty("accent", True)
        g = self._db.get_setting

        form = QVBoxLayout()
        form.setSpacing(6)

        def add_field(label: str, widget_or_layout) -> None:
            lab = QLabel(label)
            lab.setProperty("muted", True)
            form.addWidget(lab)
            if isinstance(widget_or_layout, QHBoxLayout):
                form.addLayout(widget_or_layout)
            else:
                form.addWidget(widget_or_layout)

        # --- Trading mode ---------------------------------------------------
        self._mode = QComboBox()
        self._mode.addItems(["Paper (simulated — walang totoong pera)",
                             "Live (TOTOONG PERA — Polymarket)"])
        self._mode.setCurrentIndex(1 if g("trading_mode", "paper") == "live" else 0)
        add_field("Trading Mode", self._mode)

        mode_warn = QLabel(
            "Ang LIVE mode ay nangangailangan ng: Polymarket access sa network, "
            "Private Key + Funder Address, at USDC balance. Kapag hindi makakonekta, "
            "awtomatikong babalik sa Paper mode."
        )
        mode_warn.setProperty("muted", True)
        mode_warn.setWordWrap(True)
        form.addWidget(mode_warn)

        # --- Secrets ------------------------------------------------------
        binance_row, self._binance_key = _secret_field(secrets.KEY_BINANCE_API)
        add_field("Binance API Key (read-only)", binance_row)

        pm_row, self._pm_private = _secret_field(secrets.KEY_PM_PRIVATE)
        add_field("Polymarket Private Key", pm_row)

        self._pm_funder = QLineEdit()
        self._pm_funder.setPlaceholderText(
            secrets.get_secret(secrets.KEY_PM_FUNDER) or "0x… (Polymarket profile address)"
        )
        add_field("Funder / Proxy Address", self._pm_funder)

        # --- Numbers ------------------------------------------------------
        self._risk = _spin(float(g("risk_usdc", DEFAULTS["risk_usdc"])), "USDC")
        add_field("Risk Per Trade (USDC)", self._risk)

        self._min_stretch = _spin(
            float(g("min_stretch_pct", DEFAULTS["min_stretch_pct"])), "%", 10.0
        )
        add_field("Entry Stretch Band (%)", self._min_stretch)

        self._max_stretch = _spin(
            float(g("max_stretch_pct", DEFAULTS["max_stretch_pct"])), "%", 10.0
        )
        add_field("Max Stretch — Death Trap Limit (%)", self._max_stretch)

        self._profit = _spin(
            float(g("profit_target_pct", DEFAULTS["profit_target_pct"])), "%", 1000.0
        )
        add_field("Take Profit (%)", self._profit)

        self._volume_mult = _spin(
            float(g("volume_spike_mult", DEFAULTS["volume_spike_mult"])), "× baseline", 10.0
        )
        add_field("Volume Spike Filter — block entry kapag lampas (×)", self._volume_mult)

        self._premium = _spin(
            float(g("premium_threshold_pct", DEFAULTS["premium_threshold_pct"])), "%", 5.0
        )
        add_field("Coinbase Premium Filter — block entry kapag lampas (±%)", self._premium)

        self._econ_day = QCheckBox(
            "Economic Data Day — block entries TODAY (Fed meeting, CPI, atbp.)"
        )
        self._econ_day.setChecked(
            g("econ_block_date") == dt.datetime.now(dt.timezone.utc).date().isoformat()
        )
        form.addWidget(self._econ_day)

        self._paper_start = _spin(
            float(g("paper_start_usdc", DEFAULTS["paper_start_usdc"])), "USDC"
        )
        add_field("Paper Starting Balance (USDC)", self._paper_start)

        # --- Buttons ------------------------------------------------------
        save_btn = QPushButton("  Save Settings")
        save_btn.setIcon(qta.icon("fa6s.floppy-disk", color=theme.TEXT))
        reset_btn = QPushButton("  Reset")
        reset_btn.setIcon(qta.icon("fa6s.rotate", color="white"))
        reset_btn.setObjectName("accentBtn")
        save_btn.clicked.connect(self._save)
        reset_btn.clicked.connect(self._reset)

        btn_row = QHBoxLayout()
        btn_row.addWidget(save_btn, stretch=1)
        btn_row.addWidget(reset_btn)

        self._status = QLabel("")
        self._status.setProperty("muted", True)

        note = QLabel(
            "Secrets are stored in Windows Credential Manager, never in files.\n"
            "Leave a secret field blank to keep its current value."
        )
        note.setProperty("muted", True)
        note.setWordWrap(True)

        panel = Card()
        panel_col = QVBoxLayout(panel)
        panel_col.setContentsMargins(16, 14, 16, 14)
        panel_col.addWidget(title)
        panel_col.addLayout(form)
        panel_col.addLayout(btn_row)
        panel_col.addWidget(self._status)
        panel_col.addWidget(note)

        root = QVBoxLayout(self)
        root.addWidget(panel)
        root.addStretch()

    # ------------------------------------------------------------------ save

    def _save(self) -> None:
        if self._binance_key.text().strip():
            secrets.set_secret(secrets.KEY_BINANCE_API, self._binance_key.text().strip())
            self._binance_key.clear()
        if self._pm_private.text().strip():
            secrets.set_secret(secrets.KEY_PM_PRIVATE, self._pm_private.text().strip())
            self._pm_private.clear()
        if self._pm_funder.text().strip():
            secrets.set_secret(secrets.KEY_PM_FUNDER, self._pm_funder.text().strip())

        self._db.set_setting(
            "trading_mode", "live" if self._mode.currentIndex() == 1 else "paper"
        )
        self._db.set_setting("risk_usdc", self._risk.value())
        self._db.set_setting("min_stretch_pct", self._min_stretch.value())
        self._db.set_setting("max_stretch_pct", self._max_stretch.value())
        self._db.set_setting("profit_target_pct", self._profit.value())
        self._db.set_setting("volume_spike_mult", self._volume_mult.value())
        self._db.set_setting("premium_threshold_pct", self._premium.value())
        # Econ day: itinatabi ang PETSA para awtomatikong mag-expire bukas
        today = dt.datetime.now(dt.timezone.utc).date().isoformat()
        self._db.set_setting("econ_block_date", today if self._econ_day.isChecked() else "")
        self._db.set_setting("paper_start_usdc", self._paper_start.value())
        self._status.setText("Settings saved ✓")

    def _reset(self) -> None:
        self._mode.setCurrentIndex(0)  # laging Paper ang default
        self._risk.setValue(DEFAULTS["risk_usdc"])
        self._min_stretch.setValue(DEFAULTS["min_stretch_pct"])
        self._max_stretch.setValue(DEFAULTS["max_stretch_pct"])
        self._profit.setValue(DEFAULTS["profit_target_pct"])
        self._volume_mult.setValue(DEFAULTS["volume_spike_mult"])
        self._premium.setValue(DEFAULTS["premium_threshold_pct"])
        self._econ_day.setChecked(False)
        self._paper_start.setValue(DEFAULTS["paper_start_usdc"])
        self._status.setText("Defaults restored — click Save Settings to apply")
